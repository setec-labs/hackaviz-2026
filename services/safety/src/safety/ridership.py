import csv
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

from hackaviz_2026.routing import JourneyLeg
from safety.providers import IndicatorDataError, IndicatorUnavailableError


logger = logging.getLogger(__name__)
DEFAULT_RIDERSHIP_CSV = (
    Path(__file__).resolve().parents[4] / "data/output/ridership/ridership_by_transit_arc.csv"
)

type ArcKey = tuple[str, str, str, datetime, datetime]


def normalize_ridership(value: float) -> float:
    """Invert the CSV's isolation score: greater estimated ridership is favorable."""
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise IndicatorDataError("Adjusted ridership score must be finite and in [0, 100]")
    return 1 - value / 100


def _arc_key(leg: JourneyLeg) -> ArcKey:
    return (
        leg.gtfs_trip_id or "",
        leg.from_stop,
        leg.to_stop,
        leg.start_time.astimezone(timezone.utc),
        leg.end_time.astimezone(timezone.utc),
    )


class RidershipIndicatorProvider:
    """Load contextual transit-arc estimates once; never infer a value from a position."""

    id = "ridership"
    name = "Ridership"
    description = (
        "Estimated validations per service, not observed occupancy. "
        "Score = 1 - estimated_validations_per_service_adjusted / 100. "
        "Requires a transit arc through /journey-safety; not an objective safety measure."
    )

    def __init__(self, path: Path = DEFAULT_RIDERSHIP_CSV) -> None:
        self._path = path
        self._scores: dict[ArcKey, float] | None = None

    def _load(self) -> dict[ArcKey, float]:
        scores: dict[ArcKey, float] = {}
        required = {
            "gtfs_trip_id", "from_stop", "to_stop", "start_time", "end_time",
            "estimated_validations_per_service_adjusted",
        }
        try:
            with self._path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not required.issubset(reader.fieldnames or []):
                    raise IndicatorDataError("Ridership CSV is missing required columns")
                for number, row in enumerate(reader, 2):
                    try:
                        leg = JourneyLeg.model_validate({
                            **{key: row[key] for key in required if key != "estimated_validations_per_service_adjusted"},
                            "mode": "transit",
                            "point_range": [0, 1],
                        })
                        if not leg.gtfs_trip_id:
                            raise ValueError("Missing GTFS trip ID")
                        value = normalize_ridership(float(row["estimated_validations_per_service_adjusted"]))
                    except (ValueError, TypeError) as exc:
                        raise IndicatorDataError(f"Invalid ridership CSV row {number}: {exc}") from exc
                    key = _arc_key(leg)
                    if key in scores and scores[key] != value:
                        raise IndicatorDataError(f"Conflicting ridership estimates at row {number}")
                    scores[key] = value
        except (OSError, UnicodeError, csv.Error) as exc:
            logger.error("Cannot load ridership CSV from %s: %s", self._path, exc)
            raise IndicatorDataError("Ridership CSV is unavailable or unreadable") from exc
        if not scores:
            raise IndicatorDataError("Ridership CSV contains no arcs")
        return scores

    async def evaluate_arc(self, leg: JourneyLeg) -> float:
        """Return the exact trip/stop/time match, or explicitly report missing data."""
        if self._scores is None:
            self._scores = self._load()
        try:
            return self._scores[_arc_key(leg)]
        except KeyError as exc:
            raise IndicatorUnavailableError("No ridership estimate matches this transit arc") from exc
