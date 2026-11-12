import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from hackaviz_2026.routing import Scenario, ScenarioDocument, ScenarioId, ScenarioSummary


logger = logging.getLogger(__name__)

JOURNEYS_FILENAME = "journeys.json"
_scenario_id_adapter: TypeAdapter[str] = TypeAdapter(ScenarioId)


class ScenarioNotFoundError(LookupError):
    pass


class ScenarioDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class _CachedScenario:
    signature: tuple[int, int]
    scenario: Scenario


def describe_scenario(scenario_id: str, document: ScenarioDocument) -> tuple[str, str]:
    """Fallback metadata derived only from the data, used until the pipeline exports name and description."""
    name = document.name or scenario_id.replace("-", " ").replace("_", " ")
    if document.description is not None:
        return name, document.description
    departure = document.departure_time
    destinations = len({journey.destination.name for journey in document.journeys})
    description = (
        f"Départ le {departure:%d/%m/%Y} à {departure:%H:%M} : "
        f"{len(document.journeys)} trajets vers {destinations} destinations."
    )
    return name, description


class ScenarioRepository:
    """Reads scenarios stored as `<directory>/<scenario_id>/journeys.json`."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._cache: dict[str, _CachedScenario] = {}

    def _check_directory(self) -> None:
        if not self._directory.is_dir():
            logger.error("Scenario directory is unavailable: %s", self._directory)
            raise ScenarioDataError("Scenario data directory is unavailable")

    def _read(self, scenario_id: str) -> Scenario:
        path = self._directory / scenario_id / JOURNEYS_FILENAME
        try:
            stat = path.stat()
        except FileNotFoundError as exc:
            raise ScenarioNotFoundError(f"Scenario '{scenario_id}' was not found") from exc
        except OSError as exc:
            logger.error("Cannot access scenario file %s", path)
            raise ScenarioDataError("Scenario data is unreadable") from exc
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = self._cache.get(scenario_id)
        if cached is not None and cached.signature == signature:
            return cached.scenario
        try:
            document = ScenarioDocument.model_validate_json(path.read_bytes())
        except (OSError, ValidationError) as exc:
            logger.error("Cannot read a valid scenario from %s", path)
            raise ScenarioDataError("Scenario data is unreadable or invalid") from exc
        name, description = describe_scenario(scenario_id, document)
        metadata_generated = document.name is None or document.description is None
        if metadata_generated:
            logger.warning("Scenario '%s' has no name or description: using generated metadata", scenario_id)
        scenario = Scenario(
            id=scenario_id,
            name=name,
            description=description,
            metadata_generated=metadata_generated,
            origin=document.origin,
            departure_time=document.departure_time,
            journey_count=len(document.journeys),
            journeys=document.journeys,
        )
        self._cache[scenario_id] = _CachedScenario(signature, scenario)
        return scenario

    def _scenario_ids(self) -> list[str]:
        self._check_directory()
        try:
            entries = sorted(self._directory.iterdir())
        except OSError as exc:
            logger.error("Cannot list scenario directory: %s", self._directory)
            raise ScenarioDataError("Scenario data directory is unreadable") from exc
        scenario_ids = []
        for entry in entries:
            if not (entry / JOURNEYS_FILENAME).is_file():
                continue
            try:
                scenario_ids.append(_scenario_id_adapter.validate_python(entry.name))
            except ValidationError as exc:
                logger.error("Scenario folder name is not a valid scenario ID: %s", entry)
                raise ScenarioDataError("Scenario folder names must be valid scenario IDs") from exc
        return scenario_ids

    def list_scenarios(self) -> list[ScenarioSummary]:
        return [
            ScenarioSummary.model_validate(self._read(scenario_id).model_dump(exclude={"journeys"}))
            for scenario_id in self._scenario_ids()
        ]

    def get_scenario(self, scenario_id: str) -> Scenario:
        self._check_directory()
        return self._read(scenario_id)
