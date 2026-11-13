import math
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from hackaviz_2026.models import (
    EvaluateRequest,
    IndicatorResult,
    IndicatorWeight,
    MAX_SAFETY_INDEX_POINTS,
    Position,
    PositionSafetyIndex,
    SafetyIndexRequest,
    ScoreRequest,
    ScoreResponse,
)
from safety.main import app, get_indicator_service
from safety.providers import IndicatorDataError, IndicatorUnavailableError
from safety.service import IndicatorService


class FixedProvider:
    def __init__(self, indicator_id: str, value: float) -> None:
        self.id = indicator_id
        self.name = indicator_id.capitalize()
        self.description = "Test indicator"
        self.value = value

    async def evaluate(self, position: Position) -> float:
        return self.value


class FailingProvider(FixedProvider):
    """Raises `error` for positions west of longitude 0, returns `value` elsewhere."""

    def __init__(self, indicator_id: str, value: float, error: Exception) -> None:
        super().__init__(indicator_id, value)
        self.error = error

    async def evaluate(self, position: Position) -> float:
        if position.longitude < 0:
            raise self.error
        return self.value


class ModelTests(unittest.TestCase):
    def test_position_boundaries_and_invalid_values(self) -> None:
        for latitude, longitude in [(-90, -180), (90, 180), (0, 0)]:
            Position(latitude=latitude, longitude=longitude)
        for latitude, longitude in [(-90.1, 0), (90.1, 0), (0, -180.1), (0, 180.1), (math.nan, 0)]:
            with self.subTest(latitude=latitude, longitude=longitude), self.assertRaises(ValidationError):
                Position(latitude=latitude, longitude=longitude)
        with self.assertRaises(ValidationError):
            Position.model_validate({"latitude": 0})

    def test_normalized_values_and_weights(self) -> None:
        for value in (0.0, 1.0):
            IndicatorResult(indicator_id="test", value=value)
            ScoreResponse(position=Position(latitude=0, longitude=0), score=value, indicators=[])
        for value in (-0.01, 1.01, math.nan, math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    IndicatorResult(indicator_id="test", value=value)
                with self.assertRaises(ValidationError):
                    ScoreResponse(position=Position(latitude=0, longitude=0), score=value, indicators=[])
        for weight in (-1.0, math.nan, math.inf):
            with self.subTest(weight=weight), self.assertRaises(ValidationError):
                IndicatorWeight(indicator_id="test", weight=weight)
        IndicatorWeight(indicator_id="test", weight=0)

    def test_required_fields(self) -> None:
        for model in (
            EvaluateRequest, IndicatorResult, IndicatorWeight, ScoreRequest, ScoreResponse,
            SafetyIndexRequest, PositionSafetyIndex,
        ):
            with self.subTest(model=model), self.assertRaises(ValidationError):
                model.model_validate({})

    def test_safety_index_models(self) -> None:
        PositionSafetyIndex(latitude=0, longitude=0, value=None)
        PositionSafetyIndex(latitude=0, longitude=0, value=1.0)
        for value in (-0.1, 1.1, math.nan):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                PositionSafetyIndex(latitude=0, longitude=0, value=value)
        point = {"latitude": 0, "longitude": 0}
        SafetyIndexRequest.model_validate({"points": []})
        SafetyIndexRequest.model_validate({"points": [point] * MAX_SAFETY_INDEX_POINTS})
        with self.assertRaises(ValidationError):
            SafetyIndexRequest.model_validate({"points": [point] * (MAX_SAFETY_INDEX_POINTS + 1)})


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.position = {"latitude": 48.8566, "longitude": 2.3522}

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.client.close()

    def use_fixed_providers(self) -> None:
        service = IndicatorService((FixedProvider("a", 0.2), FixedProvider("b", 0.8)))
        app.dependency_overrides[get_indicator_service] = lambda: service

    def use_service(self, *providers: FixedProvider) -> None:
        service = IndicatorService(providers)
        app.dependency_overrides[get_indicator_service] = lambda: service

    def test_lighting_metadata(self) -> None:
        response = self.client.get("/indicators")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.json()],
            ["lighting", "population_density", "ridership"],
        )
        self.assertTrue(response.json()[0]["name"])
        self.assertTrue(response.json()[0]["description"])

    def test_unimplemented_indicator_never_returns_a_placeholder(self) -> None:
        self.use_service(FailingProvider("pending", 0.5, NotImplementedError()))
        west = {"latitude": 48.0, "longitude": -1.0}
        for path, body in [
            ("/evaluate", {"position": west}),
            ("/score", {"position": west, "weights": [{"indicator_id": "pending", "weight": 1}]}),
            ("/safety-index", {"points": [self.position, west]}),
        ]:
            with self.subTest(path=path):
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 501)
                self.assertIn("pending", response.json()["detail"])

    def test_unavailable_data_is_reported_not_invented(self) -> None:
        self.use_service(FixedProvider("a", 0.4), FailingProvider("b", 0.8, IndicatorUnavailableError("no data")))
        west = {"latitude": 48.0, "longitude": -1.0}
        for path, body in [
            ("/evaluate", {"position": west}),
            ("/score", {"position": west, "weights": [{"indicator_id": "b", "weight": 1}]}),
        ]:
            with self.subTest(path=path):
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["detail"], "no data")
        response = self.client.post("/safety-index", json={"points": [self.position, west]})
        self.assertEqual(response.status_code, 200)
        first, second = response.json()["indices"]
        self.assertEqual((first["latitude"], first["longitude"]), (self.position["latitude"], self.position["longitude"]))
        self.assertAlmostEqual(first["value"], 0.6)
        self.assertEqual(second, {**west, "value": None})

    def test_safety_index_keeps_request_order(self) -> None:
        self.use_fixed_providers()
        points = [{"latitude": 48.0 + i / 10, "longitude": 2.0 + i / 10} for i in range(4)]
        response = self.client.post("/safety-index", json={"points": points})
        self.assertEqual(response.status_code, 200)
        indices = response.json()["indices"]
        self.assertEqual([{"latitude": i["latitude"], "longitude": i["longitude"]} for i in indices], points)
        for item in indices:
            self.assertAlmostEqual(item["value"], 0.5)
        self.assertEqual(self.client.post("/safety-index", json={"points": []}).json(), {"indices": []})

    def test_source_data_errors_return_503(self) -> None:
        self.use_service(FailingProvider("broken", 0.5, IndicatorDataError("raster unreadable")))
        west = {"latitude": 48.0, "longitude": -1.0}
        for path, body in [
            ("/evaluate", {"position": west}),
            ("/safety-index", {"points": [west]}),
        ]:
            with self.subTest(path=path):
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["detail"], "raster unreadable")

    def test_empty_raster_setting_is_rejected(self) -> None:
        get_indicator_service.cache_clear()
        self.addCleanup(get_indicator_service.cache_clear)
        for setting in ("SAFETY_LIGHTING_RASTER", "SAFETY_POPULATION_DENSITY_RASTER"):
            with self.subTest(setting=setting):
                get_indicator_service.cache_clear()
                with patch.dict(os.environ, {setting: " "}):
                    response = self.client.get("/indicators")
                self.assertEqual(response.status_code, 503)

    def test_cors_allows_the_frontend_dev_server(self) -> None:
        response = self.client.options("/safety-index", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_evaluate_and_weighted_score(self) -> None:
        self.use_fixed_providers()
        response = self.client.post("/evaluate", json={"position": self.position})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "position": self.position,
            "indicators": [{"indicator_id": "a", "value": 0.2}, {"indicator_id": "b", "value": 0.8}],
        })
        response = self.client.post("/score", json={
            "position": self.position,
            "weights": [{"indicator_id": "b", "weight": 3}, {"indicator_id": "a", "weight": 1}],
        })
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.json()["score"], 0.65)
        self.assertEqual([item["indicator_id"] for item in response.json()["indicators"]], ["b", "a"])
        self.assertEqual(response.json()["position"], self.position)

    def test_extreme_and_zero_weights(self) -> None:
        self.use_fixed_providers()
        for weights, expected in [
            ([{"indicator_id": "a", "weight": 0}, {"indicator_id": "b", "weight": 2}], 0.8),
            ([{"indicator_id": "a", "weight": 1e308}, {"indicator_id": "b", "weight": 1e308}], 0.5),
        ]:
            with self.subTest(weights=weights):
                response = self.client.post("/score", json={"position": self.position, "weights": weights})
                self.assertEqual(response.status_code, 200)
                self.assertAlmostEqual(response.json()["score"], expected)

    def test_invalid_requests(self) -> None:
        self.use_fixed_providers()
        cases = [
            ("/evaluate", {}, 422),
            ("/evaluate", {"position": {"latitude": 91, "longitude": 0}}, 422),
            ("/evaluate", {"position": {"latitude": 0}}, 422),
            ("/score", {"position": self.position}, 422),
            ("/score", {"position": self.position, "weights": []}, 422),
            ("/score", {"position": self.position, "weights": [{"indicator_id": "a", "weight": 0}]}, 422),
            ("/score", {"position": self.position, "weights": [{"indicator_id": "a", "weight": -1}]}, 422),
            ("/score", {"position": self.position, "weights": [
                {"indicator_id": "a", "weight": 1}, {"indicator_id": "a", "weight": 2},
            ]}, 422),
            ("/score", {"position": self.position, "weights": [{"indicator_id": "unknown", "weight": 1}]}, 400),
            ("/safety-index", {}, 422),
            ("/safety-index", {"points": [{"latitude": 0, "longitude": 200}]}, 422),
            ("/safety-index", {"points": [self.position] * (MAX_SAFETY_INDEX_POINTS + 1)}, 422),
        ]
        for path, body, status in cases:
            with self.subTest(body=body):
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, status, response.text)

    def test_invalid_provider_score_is_not_exposed(self) -> None:
        service = IndicatorService((FixedProvider("bad", 1.01),))
        app.dependency_overrides[get_indicator_service] = lambda: service
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/evaluate", json={"position": self.position})
        self.assertEqual(response.status_code, 500)

    def test_non_finite_json_numbers_return_validation_errors(self) -> None:
        for path, body in [
            ("/evaluate", '{"position":{"latitude":1e999,"longitude":0}}'),
            ("/score", '{"position":{"latitude":0,"longitude":0},"weights":[{"indicator_id":"lighting","weight":1e999}]}'),
        ]:
            with self.subTest(path=path):
                response = self.client.post(path, content=body, headers={"Content-Type": "application/json"})
                self.assertEqual(response.status_code, 422)
                self.assertTrue(response.json()["detail"])

    def test_openapi_declares_models_and_bounds(self) -> None:
        schema = self.client.get("/openapi.json").json()
        schemas = schema["components"]["schemas"]
        self.assertEqual(schemas["Position"]["properties"]["latitude"]["minimum"], -90)
        self.assertEqual(schemas["IndicatorResult"]["properties"]["value"]["maximum"], 1)
        self.assertEqual(schemas["ScoreResponse"]["properties"]["score"]["minimum"], 0)
        self.assertIn("null", str(schemas["PositionSafetyIndex"]["properties"]["value"]))
        self.assertEqual(schemas["SafetyIndexRequest"]["properties"]["points"]["maxItems"], MAX_SAFETY_INDEX_POINTS)
        for path, method in [
            ("/indicators", "get"), ("/evaluate", "post"), ("/score", "post"), ("/safety-index", "post"),
        ]:
            self.assertIn("schema", schema["paths"][path][method]["responses"]["200"]["content"]["application/json"])


if __name__ == "__main__":
    unittest.main()
