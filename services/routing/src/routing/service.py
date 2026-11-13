from hackaviz_2026.routing import ReportResponse, Scenario, ScenarioSummary

from routing.providers import ReportProvider
from routing.repository import ScenarioRepository


class ReportNotImplementedError(RuntimeError):
    """A scenario report was requested before report calculation is available."""


class RoutingService:
    """Coordinate scenario reads and report generation."""

    def __init__(self, repository: ScenarioRepository, report_provider: ReportProvider) -> None:
        self._repository = repository
        self._report_provider = report_provider

    def list_scenarios(self) -> list[ScenarioSummary]:
        """List scenario summaries in repository order."""
        return self._repository.list_scenarios()

    def get_scenario(self, scenario_id: str) -> Scenario:
        """Load a scenario by its validated folder identifier."""
        return self._repository.get_scenario(scenario_id)

    async def report(self, scenario_id: str) -> ReportResponse:
        """Load a scenario and ask the provider to produce its report.

        Args:
            scenario_id: Identifier of the scenario to report.

        Returns:
            A report supplied by the configured provider.

        Raises:
            ReportNotImplementedError: The provider cannot yet calculate reports.
        """
        scenario = self._repository.get_scenario(scenario_id)
        try:
            return await self._report_provider.report(scenario)
        except NotImplementedError as exc:
            raise ReportNotImplementedError(
                "Scenario reports are not implemented: person counts and anxiety scores are unavailable"
            ) from exc
