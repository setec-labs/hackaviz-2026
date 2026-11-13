import asyncio
import csv
import math
import tempfile
import unittest
from datetime import timezone
from pathlib import Path

from httpx import Response
from fastapi.testclient import TestClient
from pydantic import ValidationError

from hackaviz_2026.journey_safety import JourneySafetyRequest, SafetyWeights
from hackaviz_2026.models import Position
from hackaviz_2026.routing import JourneyLeg
from safety.main import app, get_indicator_service
from safety.providers import IndicatorDataError, IndicatorUnavailableError
from safety.ridership import DEFAULT_RIDERSHIP_CSV, RidershipIndicatorProvider, normalize_ridership
from safety.service import IndicatorService
from test_api import FailingProvider, FixedProvider


def journey() -> dict:
    return {
        "journey_id": "j1",
        "destination": {"name": "Destination", "latitude": 48.9, "longitude": 2.4},
        "start_time": "2026-11-08T00:00:00+01:00",
        "end_time": "2026-11-08T00:20:00+01:00",
        "coordinates": [[2.3, 48.8], [2.4, 48.9]],
        "offsets_s": [0, 600],
        "legs": [
            {
                "mode": "walk_access",
                "start_time": "2026-11-08T00:00:00+01:00",
                "end_time": "2026-11-08T00:10:00+01:00",
                "from_stop": "ORIGIN", "to_stop": "A", "point_range": [0, 1],
            },
            {
                "mode": "transit",
                "start_time": "2026-11-08T00:10:00+01:00",
                "end_time": "2026-11-08T00:20:00+01:00",
                "from_stop": "A", "to_stop": "B", "gtfs_trip_id": "T", "point_range": [1, 2],
            },
        ],
    }


class RidershipFixture:
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "ridership.csv"
        self.leg = JourneyLeg.model_validate(journey()["legs"][1])
        self.write_rows(20)

    def write_rows(self, *values: object) -> None:
        fields = [
            "gtfs_trip_id", "from_stop", "to_stop", "start_time", "end_time",
            "estimated_validations_per_service_adjusted",
        ]
        with self.path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for value in values:
                writer.writerow({
                    **{key: getattr(self.leg, key) for key in fields[:-1]},
                    fields[-1]: value,
                })


class RidershipTests(RidershipFixture, unittest.TestCase):
    def test_inversion_and_invalid_scores(self) -> None:
        for raw, expected in [(0, 1), (20, 0.8), (100, 0)]:
            self.assertAlmostEqual(normalize_ridership(raw), expected)
        for raw in (-1, 101, math.nan, math.inf):
            with self.subTest(raw=raw), self.assertRaises(IndicatorDataError):
                normalize_ridership(raw)

    def test_exact_arc_matching_timezones_and_cached_loading(self) -> None:
        provider = RidershipIndicatorProvider(self.path)
        self.assertAlmostEqual(asyncio.run(provider.evaluate_arc(self.leg)), 0.8)
        self.path.unlink()
        utc_leg = self.leg.model_copy(update={
            "start_time": self.leg.start_time.astimezone(timezone.utc),
        })
        self.assertAlmostEqual(asyncio.run(provider.evaluate_arc(utc_leg)), 0.8)
        for update in ({"gtfs_trip_id": "other"}, {"from_stop": "other"}, {
            "end_time": self.leg.end_time.replace(minute=21),
        }):
            with self.subTest(update=update), self.assertRaises(IndicatorUnavailableError):
                asyncio.run(provider.evaluate_arc(self.leg.model_copy(update=update)))

    def test_invalid_missing_and_conflicting_sources(self) -> None:
        for values in [("",), ("nan",), (101,), (20, 30)]:
            with self.subTest(values=values):
                self.write_rows(*values)
                with self.assertRaises(IndicatorDataError):
                    asyncio.run(RidershipIndicatorProvider(self.path).evaluate_arc(self.leg))
        for content in ("", "wrong,columns\n1,2\n"):
            self.path.write_text(content)
            with self.assertRaises(IndicatorDataError):
                asyncio.run(RidershipIndicatorProvider(self.path).evaluate_arc(self.leg))
        self.path.unlink()
        with self.assertRaises(IndicatorDataError):
            asyncio.run(RidershipIndicatorProvider(self.path).evaluate_arc(self.leg))

    def test_delivered_csv_loads(self) -> None:
        provider = RidershipIndicatorProvider(DEFAULT_RIDERSHIP_CSV)
        self.assertGreater(len(provider._load()), 0)


class JourneySafetyApiTests(RidershipFixture, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(app.dependency_overrides.clear)
        self.service = IndicatorService(
            (FixedProvider("lighting", 0.2),), RidershipIndicatorProvider(self.path),
        )
        app.dependency_overrides[get_indicator_service] = lambda: self.service

    def post(self, payload: dict) -> Response:
        return self.client.post("/journey-safety", json={
            "weights": {"lighting": 0.5, "ridership": 0.5}, **payload,
        })

    def test_weight_changes_global_score_not_local_values(self) -> None:
        for weights, expected in [
            ({"lighting": 0.5, "ridership": 0.5}, 0.5),
            ({"lighting": 0.25, "ridership": 0.75}, 0.65),
            ({"lighting": 1, "ridership": 0}, 0.2),
        ]:
            with self.subTest(weights=weights):
                response = self.post({"journeys": [journey()], "weights": weights})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["weights"], {**weights, "population_density": 0})
                result = response.json()["journeys"][0]
                self.assertEqual(result["values"], [0.2, 0.8])
                self.assertAlmostEqual(result["score"], expected)

    def test_density_overlaps_lighting_and_three_weights_control_only_the_global_score(self) -> None:
        self.service = IndicatorService((
            FixedProvider("lighting", 0.2), FixedProvider("population_density", 1),
        ), RidershipIndicatorProvider(self.path))
        response = self.client.post("/journey-safety", json={"journeys": [journey()]})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["journeys"][0]
        self.assertEqual(result["values"], [0.6, 0.8])
        self.assertAlmostEqual(result["score"], 2 / 3)
        self.assertEqual({item["indicator_id"]: item["value"] for item in result["indicators"]}, {
            "lighting": 0.2, "ridership": 0.8, "population_density": 1,
        })
        self.assertAlmostEqual(sum(response.json()["weights"].values()), 1)
        waiting = journey()
        waiting["legs"][0]["mode"] = "wait"
        response = self.post({
            "journeys": [waiting],
            "weights": {"lighting": 0.1, "ridership": 0.2, "population_density": 0.7},
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["journeys"][0]
        self.assertEqual(result["values"], [0.6, 0.8])
        self.assertAlmostEqual(result["score"], 0.88)

    def test_density_missing_data_zero_weight_errors_and_transit_exclusion(self) -> None:
        self.service = IndicatorService((
            FixedProvider("lighting", 0.2),
            FailingProvider("population_density", 0.6, IndicatorUnavailableError("No density")),
        ), RidershipIndicatorProvider(self.path))
        data = journey()
        data["coordinates"][0][0] = -1
        response = self.post({
            "journeys": [data],
            "weights": {"lighting": 0.25, "ridership": 0.25, "population_density": 0.5},
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["journeys"][0]
        self.assertEqual(result["values"], [None, 0.8])
        self.assertIsNone(result["score"])
        result = self.post({"journeys": [data]}).json()["journeys"][0]
        self.assertAlmostEqual(result["score"], 0.5)
        self.assertEqual(result["values"], [None, 0.8])
        self.service = IndicatorService((
            FixedProvider("lighting", 0.2),
            FailingProvider("population_density", 0.6, IndicatorDataError("Invalid density")),
        ), RidershipIndicatorProvider(self.path))
        self.assertEqual(self.post({"journeys": [data]}).status_code, 503)
        data["coordinates"] = [[-1, 48.9]]
        data["start_time"] = data["legs"][1]["start_time"]
        data["offsets_s"] = [0]
        data["legs"] = [{**data["legs"][1], "point_range": [0, 1]}]
        response = self.client.post("/journey-safety", json={"journeys": [data]})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["journeys"][0]
        self.assertEqual(result["values"], [0.8])
        self.assertAlmostEqual(result["score"], 0.8)
        self.assertEqual(result["indicators"], [{"indicator_id": "ridership", "value": 0.8}])

    def test_missing_expected_data_is_null_and_inapplicable_is_not_missing(self) -> None:
        data = journey()
        data["legs"][1]["gtfs_trip_id"] = "missing"
        result = self.post({"journeys": [data]}).json()["journeys"][0]
        self.assertEqual(result["values"], [0.2, None])
        self.assertIsNone(result["score"])
        result = self.post({
            "journeys": [data], "weights": {"lighting": 1, "ridership": 0},
        }).json()["journeys"][0]
        self.assertEqual(result["score"], 0.2)
        data["legs"][1]["mode"] = "walk_egress"
        result = self.post({"journeys": [data]}).json()["journeys"][0]
        self.assertAlmostEqual(result["score"], 0.2)

    def test_duration_weighting_and_missing_lighting(self) -> None:
        class LongitudeProvider(FixedProvider):
            async def evaluate(self, position: Position) -> float:
                if position.longitude < 0:
                    raise IndicatorUnavailableError("No lighting")
                return position.longitude / 10

        service = IndicatorService((LongitudeProvider("lighting", 0),))
        app.dependency_overrides[get_indicator_service] = lambda: service
        data = journey()
        data["legs"][1]["mode"] = "walk_egress"
        data["coordinates"] = [[2, 48], [8, 48]]
        data["legs"][0]["end_time"] = "2026-11-08T00:05:00+01:00"
        data["legs"][1]["start_time"] = data["legs"][0]["end_time"]
        data["offsets_s"] = [0, 300]
        result = self.post({"journeys": [data]}).json()["journeys"][0]
        self.assertAlmostEqual(result["score"], 0.65)
        data["coordinates"][1][0] = -1
        result = self.post({"journeys": [data]}).json()["journeys"][0]
        self.assertEqual(result["values"], [0.2, None])
        self.assertIsNone(result["score"])

    def test_linear_interpolation_and_zero_duration(self) -> None:
        class LongitudeProvider(FixedProvider):
            async def evaluate(self, position: Position) -> float:
                return position.longitude / 10

        service = IndicatorService((LongitudeProvider("lighting", 0),))
        app.dependency_overrides[get_indicator_service] = lambda: service
        data = journey()
        data["coordinates"] = [[2, 48], [8, 48]]
        data["offsets_s"] = [0, 300]
        data["legs"] = [{
            **data["legs"][0], "point_range": [0, 2], "end_time": data["end_time"],
        }]
        # 300 seconds interpolated at 0.5, then 900 seconds at the last value (0.8).
        result = self.post({"journeys": [data]}).json()["journeys"][0]
        self.assertAlmostEqual(result["score"], 0.725)
        data["end_time"] = data["start_time"]
        data["legs"][0]["end_time"] = data["start_time"]
        data["offsets_s"] = [0, 0]
        result = self.post({"journeys": [data]}).json()["journeys"][0]
        self.assertEqual(result["values"], [0.2, 0.8])
        self.assertIsNone(result["score"])

    def test_validation_limits_and_errors(self) -> None:
        self.assertEqual(self.post({}).status_code, 422)
        self.assertEqual(self.post({"journeys": []}).json()["journeys"], [])
        for weights in [
            {"lighting": 0.2, "ridership": 0.2}, {"lighting": 0, "ridership": 0},
            {"lighting": -1, "ridership": 2}, {"lighting": 1, "ridership": 0, "unknown": 1},
            {"lighting": 0.25, "ridership": 0.25, "population_density": 0.25},
            {"lighting": 0.5, "ridership": 1, "population_density": -0.5},
        ]:
            with self.subTest(weights=weights):
                self.assertEqual(self.post({"journeys": [journey()], "weights": weights}).status_code, 422)
        for value in (math.nan, math.inf):
            with self.assertRaises(ValidationError):
                SafetyWeights(lighting=value, ridership=0)
            with self.assertRaises(ValidationError):
                SafetyWeights(lighting=0, ridership=0, population_density=value)
        with self.assertRaises(ValidationError):
            JourneySafetyRequest.model_validate({"journeys": [journey(), journey()]})
        with self.assertRaises(ValidationError):
            JourneySafetyRequest.model_validate({"journeys": [journey()] * 101})
        data = journey()
        data["coordinates"] = [[2, 48]] * 5001
        data["offsets_s"] = [0] * 5001
        data["legs"] = [{**data["legs"][0], "point_range": [0, 5001], "end_time": data["end_time"]}]
        self.assertEqual(self.post({"journeys": [data]}).status_code, 422)
        self.path.unlink()
        self.assertEqual(self.post({"journeys": [journey()]}).status_code, 503)

    def test_favorable_boundary_survives_fractional_sampling_times(self) -> None:
        service = IndicatorService((FixedProvider("lighting", 1),))
        app.dependency_overrides[get_indicator_service] = lambda: service
        data = journey()
        data["offsets_s"] = [
            0, 14.923905, 149.134453, 386.311457, 417.022877, 427.336357,
            445.316502, 510.117768, 614.496197, 659.315457, 1712.705451, 1913.274923,
        ]
        data["coordinates"] = [[2, 48]] * len(data["offsets_s"])
        data["end_time"] = "2026-11-08T00:31:53.274923+01:00"
        data["legs"] = [{
            **data["legs"][0],
            "point_range": [0, len(data["offsets_s"])],
            "end_time": data["end_time"],
        }]
        response = self.post({"journeys": [data]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["journeys"][0]["score"], 1)
