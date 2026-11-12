from typing import Protocol

from hackaviz_2026.routing import ReportResponse, Scenario


class ReportProvider(Protocol):
    """Contract for producing a report from a validated scenario."""

    async def report(self, scenario: Scenario) -> ReportResponse:
        """Report the person count and favorability at each journey's final point.

        Args:
            scenario: Scenario whose journeys are to be reported.

        Returns:
            One result per journey, including its normalized favorability score.

        Raises:
            NotImplementedError: Report calculation is not available.
        """
        ...


class UnimplementedReportProvider:
    """Placeholder that explicitly rejects reports until a provider is ready."""

    async def report(self, scenario: Scenario) -> ReportResponse:
        """Raise ``NotImplementedError`` instead of returning invented data."""
        raise NotImplementedError("Person counts and anxiety scores are not implemented yet")
