import asyncio
import math
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import rasterio
from fastapi.testclient import TestClient
from pyproj import Transformer
from rasterio.transform import from_origin

from hackaviz_2026.models import Position
from safety.lighting import (
    DEFAULT_LIGHTING_RASTER,
    LightingIndicatorProvider,
    normalize_lighting,
)
from safety.main import app, get_indicator_service
from safety.providers import IndicatorDataError, IndicatorUnavailableError


NODATA = -9999.0
PIXEL_SIZE = 100.0
# Châtelet, used as the top-left corner of the synthetic rasters.
ORIGIN = Position(latitude=48.8590, longitude=2.3470)
TO_LAMBERT93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
TO_WGS84 = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)


def write_raster(path: Path, values: np.ndarray, crs: str | None = "EPSG:2154") -> None:
    x, y = TO_LAMBERT93.transform(ORIGIN.longitude, ORIGIN.latitude)
    with rasterio.open(
        path, "w", driver="GTiff", height=values.shape[0], width=values.shape[1], count=1,
        dtype="float32", crs=crs, transform=from_origin(x, y, PIXEL_SIZE, PIXEL_SIZE), nodata=NODATA,
    ) as dataset:
        dataset.write(values.astype("float32"), 1)


def pixel_center(row: int, column: int) -> Position:
    x, y = TO_LAMBERT93.transform(ORIGIN.longitude, ORIGIN.latitude)
    longitude, latitude = TO_WGS84.transform(
        x + (column + 0.5) * PIXEL_SIZE, y - (row + 0.5) * PIXEL_SIZE
    )
    return Position(latitude=latitude, longitude=longitude)


def evaluate(provider: LightingIndicatorProvider, position: Position) -> float:
    return asyncio.run(provider.evaluate(position))


class NormalizationTests(unittest.TestCase):
    def test_linear_normalization_of_log_scaled_values(self) -> None:
        for raw, expected in [(0.0, 0.0), (9.0, 0.09), (100.0, 1.0)]:
            with self.subTest(raw=raw):
                self.assertAlmostEqual(normalize_lighting(raw), expected)

    def test_normalization_is_increasing(self) -> None:
        scores = [normalize_lighting(raw) for raw in (0.0, 0.5, 2.7, 20.0, 50.0, 100.0)]
        self.assertEqual(scores, sorted(scores))

    def test_unexpected_raw_values_are_rejected(self) -> None:
        for raw in (-0.1, 100.1, math.nan, math.inf):
            with self.subTest(raw=raw), self.assertRaises(IndicatorDataError):
                normalize_lighting(raw)


class LightingProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.raster = self.directory / "lighting.tif"
        write_raster(self.raster, np.array([
            [0.0, 25.0, 100.0],
            [NODATA, 150.0, np.nan],
        ]))
        self.provider = LightingIndicatorProvider(self.raster)

    def test_reads_the_pixel_after_reprojection(self) -> None:
        for (row, column), expected in [((0, 0), 0.0), ((0, 1), 0.25), ((0, 2), 1.0)]:
            with self.subTest(row=row, column=column):
                self.assertAlmostEqual(evaluate(self.provider, pixel_center(row, column)), expected)

    def test_missing_data_is_unavailable(self) -> None:
        outside = [pixel_center(-1, 0), pixel_center(0, 3), pixel_center(2, 0), Position(latitude=0, longitude=0)]
        for position in [pixel_center(1, 0), pixel_center(1, 2), *outside]:
            with self.subTest(position=position), self.assertRaises(IndicatorUnavailableError):
                evaluate(self.provider, position)

    def test_out_of_range_raw_value_is_a_data_error(self) -> None:
        with self.assertRaises(IndicatorDataError):
            evaluate(self.provider, pixel_center(1, 1))

    def test_unreadable_rasters_are_data_errors(self) -> None:
        invalid = self.directory / "invalid.tif"
        invalid.write_text("not a raster", encoding="utf-8")
        without_crs = self.directory / "without_crs.tif"
        write_raster(without_crs, np.zeros((1, 1)), crs=None)
        for path in (self.directory / "missing.tif", invalid, without_crs):
            with self.subTest(path=path.name), self.assertRaises(IndicatorDataError):
                evaluate(LightingIndicatorProvider(path), ORIGIN)

    def test_api_uses_the_configured_raster(self) -> None:
        get_indicator_service.cache_clear()
        self.addCleanup(get_indicator_service.cache_clear)
        points = [pixel_center(0, 1), pixel_center(1, 0), Position(latitude=0, longitude=0)]
        with patch.dict(os.environ, {"SAFETY_LIGHTING_RASTER": str(self.raster)}), TestClient(app) as client:
            response = client.post("/safety-index", json={"points": [p.model_dump() for p in points]})
            evaluate_response = client.post("/evaluate", json={"position": points[2].model_dump()})
        self.assertEqual(response.status_code, 200)
        values = [item["value"] for item in response.json()["indices"]]
        self.assertAlmostEqual(values[0], 0.25)
        self.assertEqual(values[1:], [None, None])
        self.assertEqual(evaluate_response.status_code, 404)


@unittest.skipUnless(DEFAULT_LIGHTING_RASTER.is_file(), "Delivered lighting raster is not available")
class DeliveredRasterTests(unittest.TestCase):
    def test_known_places(self) -> None:
        provider = LightingIndicatorProvider()
        chatelet = evaluate(provider, Position(latitude=48.8590, longitude=2.3470))
        vincennes_wood = evaluate(provider, Position(latitude=48.8330, longitude=2.4370))
        self.assertAlmostEqual(chatelet, 0.7974, places=3)
        self.assertLess(vincennes_wood, chatelet)
        with self.assertRaises(IndicatorUnavailableError):
            evaluate(provider, Position(latitude=45.76, longitude=4.83))


if __name__ == "__main__":
    unittest.main()
