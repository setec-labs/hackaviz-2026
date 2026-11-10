import logging
from pathlib import Path

from pydantic import ValidationError

from hackaviz_2026.routing import Scenario, ScenarioSummary


logger = logging.getLogger(__name__)


class ScenarioNotFoundError(LookupError):
    pass


class ScenarioDataError(RuntimeError):
    pass


class ScenarioRepository:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def _check_directory(self) -> None:
        if not self._directory.is_dir():
            logger.error("Scenario directory is unavailable: %s", self._directory)
            raise ScenarioDataError("Scenario data directory is unavailable")

    def _read(self, path: Path) -> Scenario:
        try:
            scenario = Scenario.model_validate_json(path.read_bytes())
        except FileNotFoundError as exc:
            raise ScenarioNotFoundError(f"Scenario '{path.stem}' was not found") from exc
        except (OSError, ValidationError) as exc:
            logger.error("Cannot read a valid scenario from %s", path)
            raise ScenarioDataError("Scenario data is unreadable or invalid") from exc
        if scenario.id != path.stem:
            logger.error("Scenario ID does not match its filename: %s", path)
            raise ScenarioDataError("Scenario ID must match its filename")
        return scenario

    def list_scenarios(self) -> list[ScenarioSummary]:
        self._check_directory()
        try:
            paths = sorted(path for path in self._directory.iterdir() if path.suffix == ".json")
        except OSError as exc:
            logger.error("Cannot list scenario directory: %s", self._directory)
            raise ScenarioDataError("Scenario data directory is unreadable") from exc
        summaries = []
        for path in paths:
            scenario = self._read(path)
            summaries.append(ScenarioSummary(
                id=scenario.id,
                name=scenario.name,
                description=scenario.description,
                type=scenario.type,
            ))
        return summaries

    def get_scenario(self, scenario_id: str) -> Scenario:
        self._check_directory()
        path = self._directory / f"{scenario_id}.json"
        return self._read(path)
