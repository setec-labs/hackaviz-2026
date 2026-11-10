from typing import Protocol

from hackaviz_2026.routing import ReportResponse, Scenario


class ReportProvider(Protocol):
    async def report(self, scenario: Scenario) -> ReportResponse:
        """Report person count and a normalized favorability score at the final point."""
        ...


class UnimplementedReportProvider:
    async def report(self, scenario: Scenario) -> ReportResponse:
        raise NotImplementedError("Person counts and anxiety scores are not implemented yet")
