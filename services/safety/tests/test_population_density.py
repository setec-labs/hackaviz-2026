import asyncio
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
from pyproj import Transformer

from hackaviz_2026.models import Position
from safety.population_density import (
    DEFAULT_POPULATION_DENSITY_RASTER,
    PopulationDensityIndicatorProvider,
    normalize_population_density,
)
from safety.providers import IndicatorDataError, IndicatorUnavailableError
from test_lighting import NODATA, ORIGIN, pixel_center, write_raster


class PopulationDensityTests(unittest.TestCase):
    def test_inversion_and_invalid_values(self) -> None:
        for raw, expected in ((0, 1), (20, 0.8), (50, 0.5), (100, 0)):
            self.assertAlmostEqual(normalize_population_density(raw), expected)
        for raw in (-1, 101, math.nan, math.inf, -math.inf):
            with self.subTest(raw=raw), self.assertRaises(IndicatorDataError):
                normalize_population_density(raw)

    def test_reprojection_missing_pixels_invalid_values_and_cached_loading(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "density.tif"
            write_raster(path, np.array([[0, 50, 100], [NODATA, np.nan, 101]]))
            provider = PopulationDensityIndicatorProvider(path)
            for column, expected in enumerate((1, 0.5, 0)):
                self.assertEqual(asyncio.run(provider.evaluate(pixel_center(0, column))), expected)
            path.unlink()
            self.assertEqual(asyncio.run(provider.evaluate(pixel_center(0, 0))), 1)
            for position in (pixel_center(1, 0), pixel_center(1, 1), pixel_center(0, 3)):
                with self.subTest(position=position), self.assertRaises(IndicatorUnavailableError):
                    asyncio.run(provider.evaluate(position))
            with self.assertRaises(IndicatorDataError):
                asyncio.run(provider.evaluate(pixel_center(1, 2)))

    def test_missing_unreadable_or_unreferenced_source_fails_explicitly(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "density.tif"
            for state in ("missing", "unreadable", "without_crs"):
                if state == "unreadable":
                    path.write_text("invalid")
                elif state == "without_crs":
                    write_raster(path, np.array([[0]]), crs=None)
                with self.subTest(state=state), self.assertRaises(IndicatorDataError):
                    asyncio.run(PopulationDensityIndicatorProvider(path).evaluate(ORIGIN))

    def test_delivered_raster_range_and_actual_pixel_normalization(self) -> None:
        with rasterio.open(DEFAULT_POPULATION_DENSITY_RASTER) as dataset:
            values = dataset.read(1, masked=True)
            self.assertEqual(dataset.crs.to_epsg(), 2154)
            self.assertEqual(dataset.res, (100, 100))
            self.assertTrue(np.all(np.isfinite(values.compressed())))
            self.assertGreaterEqual(values.min(), 0)
            self.assertLessEqual(values.max(), 100)
            row, column = dataset.index(652000, 6861000)
            raw = float(values[row, column])
            longitude, latitude = Transformer.from_crs(
                dataset.crs, "EPSG:4326", always_xy=True,
            ).transform(*dataset.xy(row, column))
        provider = PopulationDensityIndicatorProvider()
        self.assertAlmostEqual(asyncio.run(provider.evaluate(
            Position(latitude=latitude, longitude=longitude),
        )), 1 - raw / 100)
        with self.assertRaises(IndicatorUnavailableError):
            asyncio.run(provider.evaluate(Position(latitude=45.76, longitude=4.83)))
