import math
from pathlib import Path

from hackaviz_2026.models import Position
from safety.providers import IndicatorDataError
from safety.raster import IndicatorRaster as LightingRaster


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
