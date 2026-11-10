from typing import Protocol

from hackaviz_2026.models import Position


class IndicatorProvider(Protocol):
    id: str
    name: str
    description: str

    async def evaluate(self, position: Position) -> float:
        """Return the final normalized score between 0.0 and 1.0."""
        ...


class LightingIndicatorProvider:
    id = "lighting"
    name = "Lighting"
    description = "Lighting conditions in the nighttime environment."

    async def evaluate(self, position: Position) -> float:
        """Future implementation: transform WGS84 to the raster CRS, read and normalize."""
        raise NotImplementedError("The lighting indicator is not implemented yet")
