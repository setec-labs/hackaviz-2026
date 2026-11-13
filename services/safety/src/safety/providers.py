from typing import Protocol

from hackaviz_2026.models import Position


class IndicatorUnavailableError(LookupError):
    """No source data covers the position (outside the dataset extent or nodata)."""


class IndicatorDataError(RuntimeError):
    """The indicator source data is missing, unreadable or inconsistent."""


class IndicatorProvider(Protocol):
    """Contract for an indicator that returns a normalized favorability score."""

    id: str
    name: str
    description: str

    async def evaluate(self, position: Position) -> float:
        """Evaluate the indicator at a WGS84 position.

        Args:
            position: WGS84 latitude and longitude to evaluate.

        Returns:
            A normalized score in [0, 1], where 1 is the most favorable.

        Raises:
            IndicatorUnavailableError: No source data covers the position.
            IndicatorDataError: The source data cannot be used.
            NotImplementedError: The indicator has not been implemented.
        """
        ...
