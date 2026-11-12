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

DEFAULT_LIGHTING_RASTER = Path(__file__).with_name("luminosite_log.tif")

# luminosite_log.tif is already on a logarithmic scale (delivered by the victoria branch),
# with values spanning exactly [0, 100]: do not apply another logarithm.
LIGHTING_RAW_MAX = 100.0
LIGHTING_RAW_THRESHOLD = 50.0


def normalize_lighting(raw_value: float) -> float:
    """Normalize an already log-scaled raster value without applying another log.

    Args:
        raw_value: Finite raster value in [0, 100].

    Returns:
        Zero below 50, otherwise the raw value divided by 100.

    Raises:
        IndicatorDataError: The raw value is nonfinite or outside [0, 100].
    """
    if not math.isfinite(raw_value) or not 0.0 <= raw_value <= LIGHTING_RAW_MAX:
        raise IndicatorDataError(
            f"Lighting raw value {raw_value} is outside the expected range [0, {LIGHTING_RAW_MAX:g}]"
        )
    if raw_value < LIGHTING_RAW_THRESHOLD:
        return 0.0
    return raw_value / LIGHTING_RAW_MAX


@dataclass(frozen=True)
class LightingRaster:
    """An in-memory raster and the transform from WGS84 to its CRS."""

    values: np.ma.MaskedArray
    transform: Affine
    to_raster_crs: Transformer

    @classmethod
    def open(cls, path: Path) -> "LightingRaster":
        """Load the first raster band and prepare a WGS84 coordinate transform.

        Args:
            path: Path to the lighting raster.

        Returns:
            The raster data, affine transform and coordinate transformer.

        Raises:
            IndicatorDataError: The raster cannot be loaded or has no CRS.
        """
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
        """Read the pixel containing a WGS84 position.

        Args:
            position: Position to project into the raster CRS.

        Returns:
            The unnormalized raster value at the containing pixel.

        Raises:
            IndicatorUnavailableError: The position cannot be projected, is
                outside the raster, or falls on a pixel without valid data.
        """
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
    """Evaluate lighting from a lazily loaded, already log-scaled raster."""

    id = "lighting"
    name = "Lighting"
    description = (
        "Night-time lighting indicator: 0 below 50% of the log-scaled raster range, "
        "otherwise the raster value divided by 100 (1 is the brightest). "
        "This is not an objective measure of safety."
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
        """Return the normalized lighting score at the given WGS84 position."""
        return normalize_lighting(self._get_raster().raw_value(position))
