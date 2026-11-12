from hackaviz_2026.routing import ReportResponse, Scenario, ScenarioSummary

from routing.providers import ReportProvider
from routing.repository import ScenarioRepository


class ReportNotImplementedError(RuntimeError):
    pass


class RoutingService:
    def __init__(self, repository: ScenarioRepository, report_provider: ReportProvider) -> None:
        self._repository = repository
        self._report_provider = report_provider

    def list_scenarios(self) -> list[ScenarioSummary]:
        return self._repository.list_scenarios()

    def get_scenario(self, scenario_id: str) -> Scenario:
        return self._repository.get_scenario(scenario_id)

    async def report(self, scenario_id: str) -> ReportResponse:
        scenario = self._repository.get_scenario(scenario_id)
        try:
            return await self._report_provider.report(scenario)
        except NotImplementedError as exc:
            raise ReportNotImplementedError(
                "Scenario reports are not implemented: person counts and anxiety scores are unavailable"
            ) from exc
