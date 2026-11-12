import math
import unittest

from pydantic import ValidationError

from hackaviz_2026.routing import (
    Journey,
    JourneyReport,
    ReportRequest,
    Scenario,
    ScenarioDocument,
    ScenarioSummary,
)
from scenario_fixture import make_document_payload, make_journey, make_scenario


class ScenarioModelTests(unittest.TestCase):
    def test_document_metadata_is_optional_until_the_pipeline_exports_it(self) -> None:
        document = ScenarioDocument.model_validate(make_document_payload(with_metadata=False))
        self.assertIsNone(document.name)
        self.assertIsNone(document.description)
        self.assertEqual(len(document.journeys), 2)
        for field, value in [("name", " "), ("description", "")]:
            payload = make_document_payload()
            payload[field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ScenarioDocument.model_validate(payload)

    def test_document_requires_valid_unique_journeys(self) -> None:
        cases = {
            "no journeys": {"journeys": []},
            "duplicate ids": {"journeys": [make_journey("j-1"), make_journey("j-1")]},
            "unknown field": {"unknown": True},
            "naive departure": {"departure_time": "2026-11-08T02:00:00"},
            "journey before departure": {"departure_time": "2026-11-08T02:00:01+01:00"},
        }
        for label, override in cases.items():
            with self.subTest(case=label), self.assertRaises(ValidationError):
                ScenarioDocument.model_validate({**make_document_payload(), **override})
        for field in ("origin", "departure_time", "journeys"):
            payload = make_document_payload()
            del payload[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ScenarioDocument.model_validate(payload)

    def test_destination_population_is_optional_and_non_negative(self) -> None:
        journey = make_journey()
        self.assertIsNone(Journey.model_validate(journey).destination.population)
        journey["destination"]["population"] = 12
        self.assertEqual(Journey.model_validate(journey).destination.population, 12)
        for population in (-1, 1.5, True):
            journey["destination"]["population"] = population
            with self.subTest(population=population), self.assertRaises(ValidationError):
                Journey.model_validate(journey)

    def test_scenario_round_trip_and_summary_fields(self) -> None:
        scenario = make_scenario()
        self.assertEqual(Scenario.model_validate_json(scenario.model_dump_json()), scenario)
        summary = ScenarioSummary.model_validate(scenario.model_dump(exclude={"journeys"}))
        self.assertEqual(summary.journey_count, 2)
        payload = scenario.model_dump(mode="json")
        payload["journey_count"] = 3
        with self.assertRaises(ValidationError):
            Scenario.model_validate(payload)

    def test_scenario_ids_are_safe_and_case_sensitive(self) -> None:
        self.assertEqual(make_scenario("AccorHotel-Arena").id, "AccorHotel-Arena")
        for scenario_id in ("../outside", "a\\b", "", "-a", "a.b", "a" * 129):
            payload = make_scenario().model_dump(mode="json")
            payload["id"] = scenario_id
            with self.subTest(scenario_id=scenario_id), self.assertRaises(ValidationError):
                Scenario.model_validate(payload)


class JourneyModelTests(unittest.TestCase):
    def test_invalid_coordinates_and_offsets(self) -> None:
        cases = [
            ("coordinates", []),
            ("coordinates", [[181, 48.85], [2.36, 48.86]]),
            ("coordinates", [[2.35, -91], [2.36, 48.86]]),
            ("coordinates", [[2.35, math.nan], [2.36, 48.86]]),
            ("coordinates", [[2.35], [2.36, 48.86]]),
            ("offsets_s", [0]),
            ("offsets_s", [0, -1]),
            ("offsets_s", [1, 60]),
            ("offsets_s", [0, math.inf]),
        ]
        for field, value in cases:
            payload = make_journey()
            payload[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                Journey.model_validate(payload)

    def test_invalid_ranges_modes_and_leg_times(self) -> None:
        for point_range in ([0, 0], [1, 2], [0, 3], [0, 1], [-1, 2], [False, 2], [0.5, 2]):
            payload = make_journey()
            payload["legs"][0]["point_range"] = point_range
            with self.subTest(point_range=point_range), self.assertRaises(ValidationError):
                Journey.model_validate(payload)
        for field, value in [
            ("mode", "bike"),
            ("start_time", "2026-11-08T02:00:01+01:00"),
            ("end_time", "2026-11-08T01:59:00+01:00"),
            ("end_time", "2026-11-08T02:00:59+01:00"),
        ]:
            payload = make_journey()
            payload["legs"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                Journey.model_validate(payload)


class ReportModelTests(unittest.TestCase):
    def test_report_request_takes_only_a_scenario_id(self) -> None:
        self.assertEqual(ReportRequest(scenario_id="Metropolis").scenario_id, "Metropolis")
        for payload in ({}, {"scenario_id": "../x"}, {"scenario_id": "a", "extra": 1}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ReportRequest.model_validate(payload)

    def test_journey_report_bounds(self) -> None:
        base = {"journey_id": "j-1", "position": {"latitude": 48.0, "longitude": 2.0}, "person_count": 0}
        for value in (0.0, 1.0):
            JourneyReport.model_validate({**base, "anxiety_index": value})
        for value in (-0.01, 1.01, math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                JourneyReport.model_validate({**base, "anxiety_index": value})
        for count in (-1, 1.5, True):
            with self.subTest(count=count), self.assertRaises(ValidationError):
                JourneyReport.model_validate({**base, "person_count": count, "anxiety_index": 0.5})


if __name__ == "__main__":
    unittest.main()
