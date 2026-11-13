import math
from pathlib import Path

from hackaviz_2026.models import Position
from safety.providers import IndicatorDataError
from safety.raster import IndicatorRaster


DEFAULT_POPULATION_DENSITY_RASTER = Path(__file__).with_name("PresenceHum_IDF_OK.tif")


def normalize_population_density(raw_value: float) -> float:
    """Invert the prepared 0-100 index; raw 0 is favorable and raw 100 unfavorable."""
    if not math.isfinite(raw_value) or not 0 <= raw_value <= 100:
        raise IndicatorDataError("Population density raw value must be finite and in [0, 100]")
    return 1 - raw_value / 100


class PopulationDensityIndicatorProvider:
    """Evaluate the prepared population-density context, not observed human presence."""

    id = "population_density"
    name = "Population density"
    description = (
        "Population-density context from PresenceHum_IDF_OK.tif: 1 - raw value / 100. "
        "Raw 0 is favorable and raw 100 unfavorable according to the source's convention. "
        "Not observed occupancy or an objective measure of safety."
    )

    def __init__(self, raster_path: Path = DEFAULT_POPULATION_DENSITY_RASTER) -> None:
        self._raster_path = raster_path
        self._raster: IndicatorRaster | None = None

    async def evaluate(self, position: Position) -> float:
        """Return the normalized score, loading the raster once on first use."""
        if self._raster is None:
            self._raster = IndicatorRaster.open(self._raster_path, name="Population density")
        return normalize_population_density(self._raster.raw_value(position))
