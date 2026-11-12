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

DEFAULT_LIGHTING_RASTER = Path(__file__).with_name("luminosite.tif")

# luminosite.tif values span exactly [0, 100]; the source does not document their unit.
LIGHTING_RAW_MAX = 100.0


def normalize_lighting(raw_value: float) -> float:
    """Logarithmic normalization log(1 + v) / log(1 + max): 0 = darkest, 1 = brightest.

    Raw values are heavily skewed towards 0 (95 % of pixels below 2.7), so a linear scale
    would compress almost every place near 0; the log scale spreads the low values.
    """
    if not math.isfinite(raw_value) or not 0.0 <= raw_value <= LIGHTING_RAW_MAX:
        raise IndicatorDataError(
            f"Lighting raw value {raw_value} is outside the expected range [0, {LIGHTING_RAW_MAX:g}]"
        )
    return math.log1p(raw_value) / math.log1p(LIGHTING_RAW_MAX)


@dataclass(frozen=True)
class LightingRaster:
    values: np.ma.MaskedArray
    transform: Affine
    to_raster_crs: Transformer

    @classmethod
    def open(cls, path: Path) -> "LightingRaster":
        try:
            with rasterio.open(path) as dataset:
                if dataset.crs is None:
                    raise IndicatorDataError("Lighting raster has no coordinate reference system")
                values = dataset.read(1, masked=True)
                transform = dataset.transform
                crs_wkt = dataset.crs.to_wkt()
            to_raster_crs = Transformer.from_crs("EPSG:4326", crs_wkt, always_xy=True)
        except (RasterioError, ProjError) as exc:
            logger.error("Cannot load lighting raster from %s: %s", path, exc)
            raise IndicatorDataError("Lighting raster is unavailable or unreadable") from exc
        return cls(values=values, transform=transform, to_raster_crs=to_raster_crs)

    def raw_value(self, position: Position) -> float:
        x, y = self.to_raster_crs.transform(position.longitude, position.latitude)
        if not (math.isfinite(x) and math.isfinite(y)):
            raise IndicatorUnavailableError("Position cannot be projected to the lighting raster")
        column, row = ~self.transform @ (x, y)
        row_index, column_index = math.floor(row), math.floor(column)
        height, width = self.values.shape
        if not (0 <= row_index < height and 0 <= column_index < width):
            raise IndicatorUnavailableError("Position is outside the lighting raster")
        value = self.values[row_index, column_index]
        if value is np.ma.masked or not math.isfinite(float(value)):
            raise IndicatorUnavailableError("Lighting raster has no data at this position")
        return float(value)


class LightingIndicatorProvider:
    id = "lighting"
    name = "Lighting"
    description = (
        "Night-time lighting level read from a raster and linearly normalized: "
        "0 is the darkest, 1 the brightest."
    )

    def __init__(self, raster_path: Path = DEFAULT_LIGHTING_RASTER) -> None:
        self._raster_path = raster_path
        self._raster: LightingRaster | None = None

    def _get_raster(self) -> LightingRaster:
        # Loaded on first use and kept in memory (about 5 MB) for all later requests.
        if self._raster is None:
            self._raster = LightingRaster.open(self._raster_path)
        return self._raster

    async def evaluate(self, position: Position) -> float:
        return normalize_lighting(self._get_raster().raw_value(position))
