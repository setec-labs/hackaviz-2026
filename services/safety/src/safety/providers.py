from typing import Protocol

from hackaviz_2026.models import Position


class IndicatorUnavailableError(LookupError):
    """No source data covers the position (outside the dataset extent or nodata)."""


class IndicatorDataError(RuntimeError):
    """The indicator source data is missing, unreadable or inconsistent."""


class IndicatorProvider(Protocol):
    id: str
    name: str
    description: str

    async def evaluate(self, position: Position) -> float:
        """Return the final normalized score between 0.0 and 1.0.

        Raise IndicatorUnavailableError when no data covers the position,
        IndicatorDataError when the source data cannot be used and
        NotImplementedError while the indicator is not implemented.
        """
        ...
