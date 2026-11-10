import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from hackaviz_2026.models import Position
from hackaviz_2026.routing import ReportResponse, Scenario
from routing.main import app, get_routing_service
from routing.providers import UnimplementedReportProvider
from routing.repository import ScenarioRepository
from routing.service import RoutingService
from scenario_fixture import make_scenario


class TestReportProvider:
    async def report(self, scenario: Scenario) -> ReportResponse:
        longitude, latitude = scenario.journey.coordinates[-1]
        return ReportResponse(
            scenario_id=scenario.id,
            position=Position(latitude=latitude, longitude=longitude),
            person_count=7,
            anxiety_index=0.75,
        )


class RoutingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.service = RoutingService(ScenarioRepository(self.directory), UnimplementedReportProvider())
        app.dependency_overrides[get_routing_service] = lambda: self.service
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def write_scenario(self, scenario_id: str = "test-hospital") -> Scenario:
        scenario = make_scenario(scenario_id)
        (self.directory / f"{scenario.id}.json").write_text(
            scenario.model_dump_json(indent=2), encoding="utf-8",
        )
        return scenario

    def test_empty_directory_and_sorted_metadata(self) -> None:
        response = self.client.get("/scenarios")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.write_scenario("b")
        self.write_scenario("a")
        (self.directory / "notes.txt").write_text("Not a scenario", encoding="utf-8")
        response = self.client.get("/scenarios")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], ["a", "b"])
        self.assertEqual(set(response.json()[0]), {"id", "name", "description", "type"})

    def test_get_scenario_preserves_the_complete_payload(self) -> None:
        scenario = self.write_scenario()
        response = self.client.get(f"/scenarios/{scenario.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), scenario.model_dump(mode="json"))

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
        self.write_scenario()
        with patch.object(Path, "iterdir", side_effect=PermissionError("Test failure")):
            with self.assertLogs("routing.repository", level="ERROR"):
                self.assertEqual(self.client.get("/scenarios").status_code, 503)
        with patch.object(Path, "read_bytes", side_effect=PermissionError("Test failure")):
            with self.assertLogs("routing.repository", level="ERROR"):
                self.assertEqual(self.client.get("/scenarios/test-hospital").status_code, 503)

    def test_invalid_json_and_filename_mismatch_are_not_skipped(self) -> None:
        path = self.directory / "invalid.json"
        for content in ("{", "{}", make_scenario("other").model_dump_json()):
            path.write_text(content, encoding="utf-8")
            with self.subTest(content=content):
                for endpoint in ("/scenarios", "/scenarios/invalid"):
                    with self.assertLogs("routing.repository", level="ERROR"):
                        self.assertEqual(self.client.get(endpoint).status_code, 503)

    def test_report_is_explicitly_unimplemented_without_a_data_directory(self) -> None:
        self.service = RoutingService(
            ScenarioRepository(self.directory / "missing"), UnimplementedReportProvider(),
        )
        scenario = make_scenario()
        response = self.client.post("/report", json={"scenario": scenario.model_dump(mode="json")})
        self.assertEqual(response.status_code, 501)
        self.assertNotIn("person_count", response.json())
        self.assertIn("not implemented", response.json()["detail"])
        with self.assertRaises(NotImplementedError):
            asyncio.run(UnimplementedReportProvider().report(scenario))

    def test_report_provider_is_replaceable_and_response_is_typed(self) -> None:
        self.service = RoutingService(ScenarioRepository(self.directory), TestReportProvider())
        scenario = make_scenario()
        response = self.client.post("/report", json={"scenario": scenario.model_dump(mode="json")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "scenario_id": scenario.id,
            "position": {"latitude": 48.86, "longitude": 2.36},
            "person_count": 7,
            "anxiety_index": 0.75,
        })

    def test_invalid_report_and_non_finite_numbers(self) -> None:
        for payload in ({}, {"scenario": {}}, {"scenario": make_scenario().model_dump(mode="json"), "extra": 1}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/report", json=payload).status_code, 422)
        body = '{"scenario":' + make_scenario().model_dump_json().replace("48.85", "1e999") + "}"
        response = self.client.post("/report", content=body, headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)
        self.assertTrue(response.json()["detail"])

    def test_openapi_declares_request_response_and_error_models(self) -> None:
        schema = self.client.get("/openapi.json").json()
        for path, method in [("/scenarios", "get"), ("/scenarios/{scenario_id}", "get"), ("/report", "post")]:
            operation = schema["paths"][path][method]
            self.assertIn("schema", operation["responses"]["200"]["content"]["application/json"])
            self.assertIn("422", operation["responses"])
        self.assertIn("requestBody", schema["paths"]["/report"]["post"])
        properties = schema["components"]["schemas"]["ReportResponse"]["properties"]
        self.assertEqual(properties["person_count"]["minimum"], 0)
        self.assertEqual(properties["anxiety_index"]["minimum"], 0)
        self.assertEqual(properties["anxiety_index"]["maximum"], 1)

    def test_environment_configures_the_data_directory(self) -> None:
        app.dependency_overrides.clear()
        self.write_scenario()
        with patch.dict(os.environ, {"ROUTING_SCENARIOS_DIR": str(self.directory)}):
            self.assertEqual(self.client.get("/scenarios/test-hospital").status_code, 200)

    def test_empty_directory_configuration_is_rejected(self) -> None:
        app.dependency_overrides.clear()
        with patch.dict(os.environ, {"ROUTING_SCENARIOS_DIR": " "}):
            self.assertEqual(self.client.get("/scenarios").status_code, 503)
