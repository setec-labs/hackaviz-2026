import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from pyproj.exceptions import ProjError
from rasterio.errors import RasterioError
from rasterio.transform import Affine

from hackaviz_2026.models import Position
from safety.providers import IndicatorDataError, IndicatorUnavailableError


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IndicatorRaster:
    """An in-memory raster and the transform from WGS84 to its CRS."""

    values: np.ma.MaskedArray
    transform: Affine
    to_raster_crs: Transformer
    name: str = "Lighting"

    @classmethod
    def open(cls, path: Path, *, name: str = "Lighting") -> "IndicatorRaster":
        """Load the first band and prepare its WGS84 coordinate transform."""
        try:
            with rasterio.open(path) as dataset:
                if dataset.crs is None:
                    raise IndicatorDataError(f"{name} raster has no coordinate reference system")
                values = dataset.read(1, masked=True)
                transform = dataset.transform
                crs_wkt = dataset.crs.to_wkt()
            to_raster_crs = Transformer.from_crs("EPSG:4326", crs_wkt, always_xy=True)
        except (RasterioError, ProjError) as exc:
            logger.error("Cannot load %s raster from %s: %s", name, path, exc)
            raise IndicatorDataError(f"{name} raster is unavailable or unreadable") from exc
        return cls(values=values, transform=transform, to_raster_crs=to_raster_crs, name=name)

    def raw_value(self, position: Position) -> float:
        """Read a WGS84 pixel, or report a position outside coverage or without data."""
        x, y = self.to_raster_crs.transform(position.longitude, position.latitude)
        if not (math.isfinite(x) and math.isfinite(y)):
            raise IndicatorUnavailableError(f"Position cannot be projected to the {self.name} raster")
        column, row = ~self.transform @ (x, y)
        row_index, column_index = math.floor(row), math.floor(column)
        height, width = self.values.shape
        if not (0 <= row_index < height and 0 <= column_index < width):
            raise IndicatorUnavailableError(f"Position is outside the {self.name} raster")
        value = self.values[row_index, column_index]
        if value is np.ma.masked or not math.isfinite(float(value)):
            raise IndicatorUnavailableError(f"{self.name} raster has no data at this position")
        return float(value)
