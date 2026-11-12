import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
from pydantic_core import from_json

from routing.optimize import OPTIMIZED_FILENAME, is_up_to_date
from hackaviz_2026.routing import (
    Scenario,
    ScenarioDocument,
    ScenarioDocumentHeader,
    ScenarioId,
    ScenarioSummary,
)


logger = logging.getLogger(__name__)

JOURNEYS_FILENAME = "journeys.json"
_scenario_id_adapter: TypeAdapter[str] = TypeAdapter(ScenarioId)
# Pipeline files weigh ~150 MB: the listing only parses the root fields written before `journeys`.
_HEADER_PREFIX_BYTES = 64 * 1024
_JOURNEY_ID_KEY = b'"journey_id"'
# Each validated scenario holds millions of points in memory: keep only the most recent ones.
_SCENARIO_CACHE_SIZE = 2


class ScenarioNotFoundError(LookupError):
    """The requested scenario file does not exist."""


class ScenarioDataError(RuntimeError):
    """The scenario directory or its contents cannot be used."""


@dataclass(frozen=True)
class _CachedScenario:
    signature: tuple[int, int]
    scenario: Scenario


@dataclass(frozen=True)
class _CachedSummary:
    signature: tuple[int, int]
    summary: ScenarioSummary


def describe_scenario(scenario_id: str, document: ScenarioDocument) -> tuple[str, str]:
    """Fill missing scenario metadata using only the document's known data.

    Args:
        scenario_id: Folder identifier used when the name is absent.
        document: Validated scenario document.

    Returns:
        The supplied or generated name and description.
    """
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
    """Read scenario files and cache summaries and recently loaded journeys.

    Prefer ``journeys.min.json`` when it is not older than the pipeline file.
    Cached entries are invalidated when the selected file's size or mtime changes.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._cache: OrderedDict[str, _CachedScenario] = OrderedDict()
        self._summaries: dict[str, _CachedSummary] = {}

    def _check_directory(self) -> None:
        if not self._directory.is_dir():
            logger.error("Scenario directory is unavailable: %s", self._directory)
            raise ScenarioDataError("Scenario data directory is unavailable")

    def _locate(self, scenario_id: str) -> tuple[Path, tuple[int, int]]:
        path = _scenario_file(self._directory / scenario_id)
        try:
            stat = path.stat()
        except FileNotFoundError as exc:
            raise ScenarioNotFoundError(f"Scenario '{scenario_id}' was not found") from exc
        except OSError as exc:
            logger.error("Cannot access scenario file %s", path)
            raise ScenarioDataError("Scenario data is unreadable") from exc
        return path, (stat.st_mtime_ns, stat.st_size)

    def _read(self, scenario_id: str) -> Scenario:
        path, signature = self._locate(scenario_id)
        cached = self._cache.get(scenario_id)
        if cached is not None and cached.signature == signature:
            self._cache.move_to_end(scenario_id)
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
        while len(self._cache) > _SCENARIO_CACHE_SIZE:
            self._cache.popitem(last=False)
        self._summaries[scenario_id] = _CachedSummary(signature, _summarize(scenario))
        return scenario

    def _read_summary(self, scenario_id: str) -> ScenarioSummary:
        """Summary from the file header; falls back to a full read when metadata must be generated."""
        path, signature = self._locate(scenario_id)
        cached = self._summaries.get(scenario_id)
        if cached is not None and cached.signature == signature:
            return cached.summary
        try:
            data = path.read_bytes()
        except OSError as exc:
            logger.error("Cannot read scenario file %s", path)
            raise ScenarioDataError("Scenario data is unreadable") from exc
        summary = _summary_from_header(scenario_id, data)
        if summary is None:
            return _summarize(self._read(scenario_id))
        self._summaries[scenario_id] = _CachedSummary(signature, summary)
        return summary

    def _scenario_ids(self) -> list[str]:
        self._check_directory()
        try:
            entries = sorted(self._directory.iterdir())
        except OSError as exc:
            logger.error("Cannot list scenario directory: %s", self._directory)
            raise ScenarioDataError("Scenario data directory is unreadable") from exc
        scenario_ids = []
        for entry in entries:
            if not ((entry / JOURNEYS_FILENAME).is_file() or (entry / OPTIMIZED_FILENAME).is_file()):
                continue
            try:
                scenario_ids.append(_scenario_id_adapter.validate_python(entry.name))
            except ValidationError as exc:
                logger.error("Scenario folder name is not a valid scenario ID: %s", entry)
                raise ScenarioDataError("Scenario folder names must be valid scenario IDs") from exc
        return scenario_ids

    def list_scenarios(self) -> list[ScenarioSummary]:
        """List summaries sorted by scenario folder ID.

        Raises:
            ScenarioDataError: The directory, folder IDs or scenario data are invalid.
        """
        return [self._read_summary(scenario_id) for scenario_id in self._scenario_ids()]

    def get_scenario(self, scenario_id: str) -> Scenario:
        """Load and validate one scenario, reusing a matching cached entry.

        Args:
            scenario_id: Scenario folder identifier.

        Returns:
            The scenario with all journeys.

        Raises:
            ScenarioNotFoundError: The scenario file is absent.
            ScenarioDataError: The directory or scenario data cannot be read.
        """
        self._check_directory()
        return self._read(scenario_id)


def _scenario_file(folder: Path) -> Path:
    source = folder / JOURNEYS_FILENAME
    optimized = folder / OPTIMIZED_FILENAME
    if not source.exists() and optimized.is_file():
        return optimized
    if optimized.is_file():
        if is_up_to_date(source, optimized):
            return optimized
        logger.warning("%s is older than %s: run optimize-scenarios", optimized, source)
    return source


def _summarize(scenario: Scenario) -> ScenarioSummary:
    return ScenarioSummary.model_validate(scenario.model_dump(exclude={"journeys"}))


def _summary_from_header(scenario_id: str, data: bytes) -> ScenarioSummary | None:
    """Build a summary from root fields and the number of journey IDs.

    Return ``None`` when the partial header cannot provide the required
    metadata. Full journey validation happens when the scenario is requested.
    """
    try:
        root = from_json(data[:_HEADER_PREFIX_BYTES], allow_partial=True)
    except ValueError:
        return None
    if not isinstance(root, dict):
        return None
    root.pop("journeys", None)
    try:
        header = ScenarioDocumentHeader.model_validate(root)
    except ValidationError:
        return None
    journey_count = data.count(_JOURNEY_ID_KEY)
    if header.name is None or header.description is None or journey_count == 0:
        return None
    return ScenarioSummary(
        id=scenario_id,
        name=header.name,
        description=header.description,
        metadata_generated=False,
        origin=header.origin,
        departure_time=header.departure_time,
        journey_count=journey_count,
    )
