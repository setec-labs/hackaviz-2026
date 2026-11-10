import math
import unittest

from pydantic import ValidationError

from hackaviz_2026.routing import Journey, ReportRequest, ReportResponse, Scenario
from scenario_fixture import make_scenario


class RoutingModelTests(unittest.TestCase):
    def test_scenario_round_trip_preserves_the_journey(self) -> None:
        scenario = make_scenario()
        self.assertEqual(Scenario.model_validate_json(scenario.model_dump_json()), scenario)
        self.assertEqual(scenario.journey.coordinates[-1], (2.36, 48.86))
        self.assertEqual(scenario.journey.legs[0].point_range, (0, 2))
        self.assertEqual(ReportRequest(scenario=scenario).scenario, scenario)

    def test_required_metadata_and_safe_identifiers(self) -> None:
        for field in ("id", "name", "description", "type", "origin", "departure_time", "journey"):
            payload = make_scenario().model_dump(mode="json")
            del payload[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Scenario.model_validate(payload)
        for field, value in [
            ("id", "../outside"), ("id", "a\\b"), ("id", ""), ("id", "a" * 129),
            ("name", " "), ("description", ""), ("type", " "),
        ]:
            payload = make_scenario().model_dump(mode="json")
            payload[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                Scenario.model_validate(payload)
        payload = make_scenario().model_dump(mode="json")
        payload["unknown"] = True
        with self.assertRaises(ValidationError):
            Scenario.model_validate(payload)

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
            payload = make_scenario().journey.model_dump(mode="json")
            payload[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                Journey.model_validate(payload)
        payload = make_scenario().journey.model_dump(mode="json")
        payload["coordinates"].append([2.36, 48.86])
        payload["offsets_s"] = [0, 60, 59]
        payload["legs"][0]["point_range"] = [0, 3]
        with self.assertRaises(ValidationError):
            Journey.model_validate(payload)

    def test_invalid_ranges_and_leg_times(self) -> None:
        for point_range in ([0, 0], [1, 2], [0, 3], [0, 1], [-1, 2], [False, 2], [0.5, 2]):
            payload = make_scenario().journey.model_dump(mode="json")
            payload["legs"][0]["point_range"] = point_range
            with self.subTest(point_range=point_range), self.assertRaises(ValidationError):
                Journey.model_validate(payload)
        for field, value in [
            ("start_time", "2026-11-08T02:00:01+01:00"),
            ("end_time", "2026-11-08T01:59:00+01:00"),
            ("end_time", "2026-11-08T02:00:59+01:00"),
        ]:
            payload = make_scenario().journey.model_dump(mode="json")
            payload["legs"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                Journey.model_validate(payload)

    def test_times_require_a_timezone_and_consistent_departure(self) -> None:
        payload = make_scenario().model_dump(mode="json")
        payload["departure_time"] = "2026-11-08T02:00:00"
        with self.assertRaises(ValidationError):
            Scenario.model_validate(payload)
        payload["departure_time"] = "2026-11-08T02:00:01+01:00"
        with self.assertRaises(ValidationError):
            Scenario.model_validate(payload)

    def test_report_bounds_and_no_implicit_metrics(self) -> None:
        scenario = make_scenario()
        for value in (0.0, 1.0):
            ReportResponse(
                scenario_id=scenario.id, position=scenario.origin,
                person_count=0, anxiety_index=value,
            )
        for value in (-0.01, 1.01, math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ReportResponse(
                    scenario_id=scenario.id, position=scenario.origin,
                    person_count=0, anxiety_index=value,
                )
        for count in (-1, 1.5, True):
            with self.subTest(count=count), self.assertRaises(ValidationError):
                ReportResponse.model_validate({
                    "scenario_id": scenario.id, "position": scenario.origin,
                    "person_count": count, "anxiety_index": 0.5,
                })
        with self.assertRaises(ValidationError):
            ReportResponse.model_validate({"scenario_id": scenario.id, "position": scenario.origin})
