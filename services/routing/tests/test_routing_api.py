import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from hackaviz_2026.routing import JourneyReport, ReportResponse, Scenario
from routing.main import app, get_routing_service
from routing.providers import UnimplementedReportProvider
from routing.repository import ScenarioRepository
from routing.service import RoutingService
from scenario_fixture import make_document_payload, make_scenario, write_document


class TestReportProvider:
    async def report(self, scenario: Scenario) -> ReportResponse:
        journeys = []
        for journey in scenario.journeys:
            longitude, latitude = journey.coordinates[-1]
            journeys.append(JourneyReport(
                journey_id=journey.journey_id,
                position={"latitude": latitude, "longitude": longitude},
                person_count=7,
                anxiety_index=0.75,
            ))
        return ReportResponse(scenario_id=scenario.id, journeys=journeys)


class RoutingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.service = RoutingService(ScenarioRepository(self.directory), UnimplementedReportProvider())
        app.dependency_overrides[get_routing_service] = lambda: self.service
        self.addCleanup(app.dependency_overrides.clear)
        get_routing_service.cache_clear()
        self.addCleanup(get_routing_service.cache_clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def write(self, scenario_id: str = "Test-Scenario", with_metadata: bool = True) -> Path:
        return write_document(
            self.directory, scenario_id, json.dumps(make_document_payload(with_metadata)),
        )

    def test_empty_directory_and_sorted_summaries(self) -> None:
        response = self.client.get("/scenarios")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.write("b")
        self.write("a")
        (self.directory / "notes.txt").write_text("Not a scenario", encoding="utf-8")
        (self.directory / "empty").mkdir()
        response = self.client.get("/scenarios")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], ["a", "b"])
        self.assertEqual(set(response.json()[0]), {
            "id", "name", "description", "metadata_generated", "origin", "departure_time", "journey_count",
        })
        self.assertEqual(response.json()[0]["journey_count"], 2)
        self.assertFalse(response.json()[0]["metadata_generated"])

    def test_get_scenario_returns_every_journey(self) -> None:
        self.write()
        response = self.client.get("/scenarios/Test-Scenario")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), make_scenario("Test-Scenario").model_dump(mode="json"))

    def test_missing_metadata_is_derived_from_the_data_and_flagged(self) -> None:
        self.write("CHU-Avicenne", with_metadata=False)
        with self.assertLogs("routing.repository", level="WARNING"):
            response = self.client.get("/scenarios/CHU-Avicenne")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["metadata_generated"])
        self.assertEqual(body["name"], "CHU Avicenne")
        self.assertEqual(body["description"], "Départ le 08/11/2026 à 02:00 : 2 trajets vers 2 destinations.")

    def test_unchanged_files_are_read_once(self) -> None:
        path = self.write()
        self.assertEqual(self.client.get("/scenarios").status_code, 200)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("cache miss")):
            self.assertEqual(self.client.get("/scenarios/Test-Scenario").status_code, 200)
        payload = make_document_payload()
        payload["name"] = "Nom modifié et plus long"
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(self.client.get("/scenarios/Test-Scenario").json()["name"], payload["name"])

    def test_missing_scenario_and_invalid_id(self) -> None:
        self.assertEqual(self.client.get("/scenarios/unknown").status_code, 404)
        for scenario_id in ("invalid.name", "a%5Cb", "a" * 129):
            with self.subTest(scenario_id=scenario_id):
                self.assertEqual(self.client.get(f"/scenarios/{scenario_id}").status_code, 422)

    def test_missing_directory_is_not_an_empty_catalogue(self) -> None:
        self.service = RoutingService(
            ScenarioRepository(self.directory / "missing"), UnimplementedReportProvider(),
        )
        with self.assertLogs("routing.repository", level="ERROR"):
            self.assertEqual(self.client.get("/scenarios").status_code, 503)
        with self.assertLogs("routing.repository", level="ERROR"):
            self.assertEqual(self.client.get("/scenarios/unknown").status_code, 503)

    def test_unreadable_directory_and_file_are_reported(self) -> None:
        self.write()
        with patch.object(Path, "iterdir", side_effect=PermissionError("Test failure")):
            with self.assertLogs("routing.repository", level="ERROR"):
                self.assertEqual(self.client.get("/scenarios").status_code, 503)
        with patch.object(Path, "read_bytes", side_effect=PermissionError("Test failure")):
            with self.assertLogs("routing.repository", level="ERROR"):
                self.assertEqual(self.client.get("/scenarios/Test-Scenario").status_code, 503)

    def test_invalid_files_and_folder_names_are_not_skipped(self) -> None:
        for content in ("{", "{}", json.dumps({**make_document_payload(), "journeys": []})):
            write_document(self.directory, "invalid", content)
            with self.subTest(content=content):
                for endpoint in ("/scenarios", "/scenarios/invalid"):
                    with self.assertLogs("routing.repository", level="ERROR"):
                        self.assertEqual(self.client.get(endpoint).status_code, 503)
        (self.directory / "invalid" / "journeys.json").unlink()
        self.write("bad.name")
        with self.assertLogs("routing.repository", level="ERROR"):
            self.assertEqual(self.client.get("/scenarios").status_code, 503)

    def test_report_is_explicitly_unimplemented(self) -> None:
        self.write()
        response = self.client.post("/report", json={"scenario_id": "Test-Scenario"})
        self.assertEqual(response.status_code, 501)
        self.assertNotIn("journeys", response.json())
        self.assertIn("not implemented", response.json()["detail"])
        with self.assertRaises(NotImplementedError):
            asyncio.run(UnimplementedReportProvider().report(make_scenario()))
        self.assertEqual(self.client.post("/report", json={"scenario_id": "unknown"}).status_code, 404)

    def test_report_provider_is_replaceable_and_response_is_typed(self) -> None:
        self.write()
        self.service = RoutingService(ScenarioRepository(self.directory), TestReportProvider())
        response = self.client.post("/report", json={"scenario_id": "Test-Scenario"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "scenario_id": "Test-Scenario",
            "journeys": [
                {"journey_id": journey_id, "position": {"latitude": 48.86, "longitude": 2.36},
                 "person_count": 7, "anxiety_index": 0.75}
                for journey_id in ("j-1", "j-2")
            ],
        })

    def test_invalid_report_requests(self) -> None:
        for payload in ({}, {"scenario_id": "a.b"}, {"scenario_id": "a", "extra": 1}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/report", json=payload).status_code, 422)

    def test_openapi_declares_request_response_and_error_models(self) -> None:
        schema = self.client.get("/openapi.json").json()
        for path, method in [("/scenarios", "get"), ("/scenarios/{scenario_id}", "get"), ("/report", "post")]:
            operation = schema["paths"][path][method]
            self.assertIn("schema", operation["responses"]["200"]["content"]["application/json"])
            self.assertIn("422", operation["responses"])
        self.assertIn("requestBody", schema["paths"]["/report"]["post"])
        properties = schema["components"]["schemas"]["JourneyReport"]["properties"]
        self.assertEqual(properties["person_count"]["minimum"], 0)
        self.assertEqual(properties["anxiety_index"]["minimum"], 0)
        self.assertEqual(properties["anxiety_index"]["maximum"], 1)

    def test_cors_allows_the_frontend_dev_server(self) -> None:
        response = self.client.options("/scenarios", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        })
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:5173")

    def test_environment_configures_the_data_directory(self) -> None:
        app.dependency_overrides.clear()
        self.write()
        with patch.dict(os.environ, {"ROUTING_SCENARIOS_DIR": str(self.directory)}):
            self.assertEqual(self.client.get("/scenarios/Test-Scenario").status_code, 200)

    def test_empty_directory_configuration_is_rejected(self) -> None:
        app.dependency_overrides.clear()
        with patch.dict(os.environ, {"ROUTING_SCENARIOS_DIR": " "}):
            self.assertEqual(self.client.get("/scenarios").status_code, 503)


if __name__ == "__main__":
    unittest.main()
