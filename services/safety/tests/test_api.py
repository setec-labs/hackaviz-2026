import asyncio
import math
import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from hackaviz_2026.models import (
    EvaluateRequest,
    IndicatorResult,
    IndicatorWeight,
    Position,
    ScoreRequest,
    ScoreResponse,
)
from safety.main import app, get_indicator_service
from safety.providers import LightingIndicatorProvider
from safety.service import IndicatorService


class FixedProvider:
    def __init__(self, indicator_id: str, value: float) -> None:
        self.id = indicator_id
        self.name = indicator_id.capitalize()
        self.description = "Test indicator"
        self.value = value

    async def evaluate(self, position: Position) -> float:
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
        for model in (EvaluateRequest, IndicatorResult, IndicatorWeight, ScoreRequest, ScoreResponse):
            with self.subTest(model=model), self.assertRaises(ValidationError):
                model.model_validate({})

    def test_lighting_does_not_return_a_placeholder(self) -> None:
        with self.assertRaises(NotImplementedError):
            asyncio.run(LightingIndicatorProvider().evaluate(Position(latitude=0, longitude=0)))


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

    def test_lighting_metadata_and_unimplemented_responses(self) -> None:
        response = self.client.get("/indicators")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], "lighting")
        self.assertTrue(response.json()[0]["name"])
        self.assertTrue(response.json()[0]["description"])
        for path, body in [
            ("/evaluate", {"position": self.position}),
            ("/score", {"position": self.position, "weights": [{"indicator_id": "lighting", "weight": 1}]}),
        ]:
            with self.subTest(path=path):
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 501)
                self.assertIn("lighting", response.json()["detail"])

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
        for path, method in [("/indicators", "get"), ("/evaluate", "post"), ("/score", "post")]:
            self.assertIn("schema", schema["paths"][path][method]["responses"]["200"]["content"]["application/json"])


if __name__ == "__main__":
    unittest.main()
