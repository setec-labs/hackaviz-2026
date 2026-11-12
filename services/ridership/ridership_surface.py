"""Estimate surface-transit validations per scheduled service for scenario arcs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Iterator, TextIO

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GTFS_DIR = PROJECT_ROOT / "data" / "input" / "IDFM-gtfs-0511"
DEFAULT_VALIDATION_DIR = PROJECT_ROOT / "data" / "input" / "frequentation"
DEFAULT_SCENARIOS_DIR = PROJECT_ROOT / "data" / "output" / "scenarios"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "ridership"

JSON_CHUNK_SIZE = 64 * 1024
JOURNEYS_ARRAY_PATTERN = re.compile(r'(?:\{|,)\s*"journeys"\s*:\s*\[')
JSON_STRING_PROPERTY = re.compile(
    r'"(?P<key>name|departure_time)"\s*:\s*'
    r'(?P<value>"(?:\\.|[^"\\])*")'
)
PROFILE_CATEGORIES = {"DIJFP", "JOVS", "JOHV", "SAHV", "SAVS"}
SURFACE_ROUTE_TYPES = {0, 3}
RAIL_ROUTE_TYPES = {1, 2}

ARC_COLUMNS = (
    "service_date",
    "arc_occurrence_count",
    "gtfs_trip_id",
    "route_id",
    "route_short_name",
    "route_type",
    "network_class",
    "start_time",
    "end_time",
    "hour_bucket",
    "from_stop",
    "to_stop",
    "validation_method",
    "validation_baseline_method",
    "hourly_profile_method",
    "service_count_method",
    "validation_line_code",
    "validation_day_category",
    "validation_stop_count",
    "profile_categories_used",
    "average_daily_validations",
    "hourly_validation_share_pct",
    "estimated_validations_in_hour",
    "scheduled_services_in_hour",
    "estimated_validations_per_service",
    "vehicle_category",
    "vehicle_size_ratio",
    "estimated_validations_per_service_adjusted",
    "validation_status",
)


@dataclass(frozen=True)
class ScenarioMetadata:
    scenario_id: str
    service_date: date


@dataclass(frozen=True)
class Route:
    route_id: str
    short_name: str
    route_type: int


def vehicle_size_adjustment(route: Route) -> tuple[str, float]:
    short_name = route.short_name.strip().upper()
    if route.route_type == 3:
        return "bus", 1.0
    if route.route_type == 0:
        if short_name == "ORLYVAL":
            return "orlyval", 1 / 3
        return "tramway", 1 / 3
    if route.route_type == 1:
        return "metro", 1 / 4
    if route.route_type == 2:
        if short_name in {"A", "B", "C", "D", "E"}:
            return "rer", 1 / 8
        return "other_rail", 1 / 8
    if route.route_type == 6 and short_name == "C1":
        return "cable_car", 1.0
    raise ValueError(
        "Ratio de taille de véhicule non défini pour "
        f"route_type={route.route_type}, ligne={route.short_name!r}."
    )


def adjust_estimate_for_vehicle_size(estimate: float, ratio: float) -> float:
    adjusted = Decimal(str(estimate)) * Decimal(str(ratio))
    return float(adjusted.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))


def normalized_vehicle_adjusted_score(adjusted_estimate: float) -> float:
    bounded_estimate = min(
        max(Decimal(str(adjusted_estimate)), Decimal("0")),
        Decimal("50"),
    )
    score = Decimal("100") * (
        Decimal("1") - bounded_estimate / Decimal("50")
    )
    return float(score.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))


@dataclass(frozen=True)
class Trip:
    route_id: str
    service_id: str


RailStopIdentity = tuple[str, str, str, str]


@dataclass(frozen=True)
class RailValidationData:
    average_daily_validations: dict[tuple[RailStopIdentity, str], float]
    hourly_shares_pct: dict[tuple[RailStopIdentity, str, int], float]
    ambiguous_hourly_profiles: set[tuple[RailStopIdentity, str, int]]
    identities_by_station: dict[str, set[RailStopIdentity]]
    validation_day_counts: dict[str, int]
    validation_period: tuple[str, str]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate surface-transit validations per scheduled service for "
            "transit legs in previously calculated scenario JSON files."
        )
    )
    parser.add_argument("--gtfs-dir", type=Path, default=DEFAULT_GTFS_DIR)
    parser.add_argument(
        "--validation-dir", type=Path, default=DEFAULT_VALIDATION_DIR
    )
    parser.add_argument(
        "--scenarios-dir", type=Path, default=DEFAULT_SCENARIOS_DIR
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--day-category",
        choices=sorted(PROFILE_CATEGORIES),
        default=None,
        help=(
            "Override the profile category for all scenario arcs. Sundays and "
            "French public holidays are detected as DIJFP automatically; "
            "other days require an explicit category."
        ),
    )
    return parser.parse_args(argv)


def normalize_line_name(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized.isdigit():
        return normalized.lstrip("0") or "0"
    return normalized


def line_similarity_group(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    if compact.startswith("tad"):
        return "demand_responsive"
    if compact.startswith("n") and len(compact) > 1:
        return "night_bus"
    if compact.startswith("t") and len(compact) > 1:
        return "tram"
    if compact and compact[0].isalpha():
        return f"letter_{compact[0]}"
    if compact and compact[0].isdigit():
        return f"number_{compact[:2] if len(compact) > 2 else compact[0]}"
    return "unknown"


def hour_bucket(hour: int) -> str:
    if not 0 <= hour <= 23:
        raise ValueError(f"Heure invalide : {hour}")
    return f"{hour}H-{(hour + 1) % 24}H"


def parse_gtfs_time(value: str) -> int | None:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"Heure GTFS invalide : {value!r}")
    try:
        hours, minutes, seconds = map(int, parts)
    except ValueError as exc:
        raise ValueError(f"Heure GTFS invalide : {value!r}") from exc
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError(f"Heure GTFS invalide : {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def easter_sunday(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def french_public_holidays(year: int) -> set[date]:
    easter = easter_sunday(year)
    fixed = {
        date(year, 1, 1),
        date(year, 5, 1),
        date(year, 5, 8),
        date(year, 7, 14),
        date(year, 8, 15),
        date(year, 11, 1),
        date(year, 11, 11),
        date(year, 12, 25),
    }
    return fixed | {
        easter + timedelta(days=1),
        easter + timedelta(days=39),
        easter + timedelta(days=50),
    }


def inferred_day_category(service_date: date, override: str | None) -> str:
    if override is not None:
        return override
    if (
        service_date.weekday() == 6
        or service_date in french_public_holidays(service_date.year)
    ):
        return "DIJFP"
    raise ValueError(
        f"Impossible de choisir automatiquement un profil pour {service_date}. "
        "Utilisez --day-category JOVS, JOHV, SAHV ou SAVS selon le calendrier "
        "scolaire applicable."
    )


def _read_until_journeys(stream: TextIO, path: Path) -> tuple[str, str]:
    buffer = ""
    while True:
        match = JOURNEYS_ARRAY_PATTERN.search(buffer)
        if match:
            return buffer[: match.start()], buffer[match.end() :]
        chunk = stream.read(JSON_CHUNK_SIZE)
        if not chunk:
            raise ValueError(f"Tableau journeys introuvable dans {path}.")
        buffer += chunk


def read_scenario_metadata(path: Path) -> ScenarioMetadata:
    with path.open(encoding="utf-8") as stream:
        header, _ = _read_until_journeys(stream, path)
    properties = {
        match.group("key"): json.loads(match.group("value"))
        for match in JSON_STRING_PROPERTY.finditer(header)
    }
    if not isinstance(properties.get("name"), str):
        raise ValueError(f"Champ name manquant ou invalide dans {path}.")
    if not isinstance(properties.get("departure_time"), str):
        raise ValueError(f"Champ departure_time manquant ou invalide dans {path}.")
    try:
        service_date = datetime.fromisoformat(
            properties["departure_time"]
        ).date()
    except ValueError as exc:
        raise ValueError(
            f"departure_time invalide dans {path}: "
            f"{properties['departure_time']!r}"
        ) from exc
    return ScenarioMetadata(properties["name"], service_date)


def iter_scenario_journeys(path: Path) -> Iterator[dict[str, object]]:
    decoder = json.JSONDecoder()
    with path.open(encoding="utf-8") as stream:
        _, buffer = _read_until_journeys(stream, path)
        while True:
            buffer = buffer.lstrip()
            if not buffer:
                buffer = stream.read(JSON_CHUNK_SIZE)
                if not buffer:
                    raise ValueError(f"Tableau journeys incomplet dans {path}.")
                continue
            if buffer.startswith("]"):
                return
            if buffer.startswith(","):
                buffer = buffer[1:]
                continue
            try:
                journey, consumed = decoder.raw_decode(buffer)
            except json.JSONDecodeError as exc:
                chunk = stream.read(JSON_CHUNK_SIZE)
                if not chunk:
                    raise ValueError(
                        f"Trajet JSON invalide dans {path}: {exc}"
                    ) from exc
                buffer += chunk
                continue
            if not isinstance(journey, dict):
                raise ValueError(f"Un trajet dans {path} n'est pas un objet JSON.")
            yield journey
            buffer = buffer[consumed:]


def collect_transit_arcs(
    scenario_files: list[Path], day_category_override: str | None
) -> tuple[list[dict[str, object]], dict[str, ScenarioMetadata], int]:
    arcs_by_key: dict[tuple[object, ...], dict[str, object]] = {}
    scenarios: dict[str, ScenarioMetadata] = {}
    raw_arc_count = 0
    for path in scenario_files:
        metadata = read_scenario_metadata(path)
        if metadata.scenario_id in scenarios:
            raise ValueError(
                f"scenario_id dupliqué dans les sorties : {metadata.scenario_id}"
            )
        category = inferred_day_category(
            metadata.service_date, day_category_override
        )
        scenarios[metadata.scenario_id] = metadata
        for journey in iter_scenario_journeys(path):
            legs = journey.get("legs")
            if not isinstance(legs, list):
                raise ValueError(
                    f"Liste legs manquante ou invalide dans {path}."
                )
            for leg in legs:
                if not isinstance(leg, dict) or leg.get("mode") != "transit":
                    continue
                raw_arc_count += 1
                trip_id = leg.get("gtfs_trip_id")
                if not isinstance(trip_id, str) or not trip_id:
                    raise ValueError(
                        f"gtfs_trip_id manquant dans {path}."
                    )
                try:
                    start_time = datetime.fromisoformat(str(leg["start_time"]))
                    end_time = datetime.fromisoformat(str(leg["end_time"]))
                except (KeyError, ValueError) as exc:
                    raise ValueError(
                        f"Horaires invalides dans {path}."
                    ) from exc
                arc_key = (
                    metadata.service_date,
                    trip_id,
                    leg.get("from_stop"),
                    leg.get("to_stop"),
                    start_time.isoformat(),
                    end_time.isoformat(),
                )
                if arc_key in arcs_by_key:
                    arcs_by_key[arc_key]["arc_occurrence_count"] += 1
                    continue
                arcs_by_key[arc_key] = {
                    "service_date": metadata.service_date,
                    "arc_occurrence_count": 1,
                    "gtfs_trip_id": trip_id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "hour": start_time.hour,
                    "hour_bucket": hour_bucket(start_time.hour),
                    "from_stop": leg.get("from_stop"),
                    "to_stop": leg.get("to_stop"),
                    "day_category": category,
                    "validation_day_category": (
                        "WEEKEND"
                        if category in {"DIJFP", "SAHV", "SAVS"}
                        else category
                    ),
                }
    return list(arcs_by_key.values()), scenarios, raw_arc_count


def load_routes(gtfs_dir: Path) -> dict[str, Route]:
    routes_file = gtfs_dir / "routes.txt"
    routes: dict[str, Route] = {}
    with routes_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require_columns(
            reader,
            {"route_id", "route_short_name", "route_type"},
            routes_file,
        )
        for row in reader:
            try:
                route = Route(
                    route_id=row["route_id"],
                    short_name=row["route_short_name"],
                    route_type=int(row["route_type"]),
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"Ligne routes.txt invalide dans {routes_file}."
                ) from exc
            if route.route_id in routes:
                raise ValueError(
                    f"route_id dupliqué dans {routes_file}: {route.route_id}"
                )
            routes[route.route_id] = route
    return routes


def load_observed_trips(
    gtfs_dir: Path, observed_trip_ids: set[str]
) -> tuple[dict[str, Trip], set[str]]:
    trips_file = gtfs_dir / "trips.txt"
    observed: dict[str, Trip] = {}
    route_ids: set[str] = set()
    with trips_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require_columns(reader, {"route_id", "service_id", "trip_id"}, trips_file)
        for row in reader:
            if row["trip_id"] in observed_trip_ids:
                trip = Trip(row["route_id"], row["service_id"])
                observed[row["trip_id"]] = trip
                route_ids.add(trip.route_id)
    return observed, route_ids


def _require_columns(
    reader: csv.DictReader, required: set[str], path: Path
) -> None:
    columns = set(reader.fieldnames or [])
    missing = required - columns
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {path}: {', '.join(sorted(missing))}"
        )


def load_relevant_trips(gtfs_dir: Path, route_ids: set[str]) -> dict[str, Trip]:
    trips_file = gtfs_dir / "trips.txt"
    relevant: dict[str, Trip] = {}
    with trips_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require_columns(reader, {"route_id", "service_id", "trip_id"}, trips_file)
        for row in reader:
            if row["route_id"] in route_ids:
                relevant[row["trip_id"]] = Trip(row["route_id"], row["service_id"])
    return relevant


def active_services_by_date(
    gtfs_dir: Path, service_dates: set[date]
) -> dict[date, set[str]]:
    calendar_file = gtfs_dir / "calendar.txt"
    exceptions_file = gtfs_dir / "calendar_dates.txt"
    calendars: list[dict[str, str]] = []
    exceptions: dict[date, list[tuple[str, int]]] = defaultdict(list)

    with calendar_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "service_id",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "start_date",
            "end_date",
        }
        _require_columns(reader, required, calendar_file)
        calendars.extend(reader)

    with exceptions_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require_columns(
            reader,
            {"service_id", "date", "exception_type"},
            exceptions_file,
        )
        for row in reader:
            exception_date = datetime.strptime(row["date"], "%Y%m%d").date()
            exceptions[exception_date].append(
                (row["service_id"], int(row["exception_type"]))
            )

    result: dict[date, set[str]] = {}
    for service_date in service_dates:
        weekday = (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )[service_date.weekday()]
        active = {
            row["service_id"]
            for row in calendars
            if row[weekday] == "1"
            and datetime.strptime(row["start_date"], "%Y%m%d").date()
            <= service_date
            <= datetime.strptime(row["end_date"], "%Y%m%d").date()
        }
        for service_id, exception_type in exceptions.get(service_date, []):
            if exception_type == 1:
                active.add(service_id)
            elif exception_type == 2:
                active.discard(service_id)
            else:
                raise ValueError(
                    f"exception_type GTFS invalide : {exception_type}"
                )
        result[service_date] = active
    return result


def scheduled_services_by_hour(
    gtfs_dir: Path,
    trips: dict[str, Trip],
    active_services: dict[date, set[str]],
) -> dict[tuple[date, str, int], int]:
    active_service_ids = (
        set().union(*active_services.values()) if active_services else set()
    )
    relevant = {
        trip_id: trip
        for trip_id, trip in trips.items()
        if trip.service_id in active_service_ids
    }
    intervals: dict[str, list[int | None]] = {}
    stop_times_file = gtfs_dir / "stop_times.txt"
    with stop_times_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require_columns(
            reader,
            {"trip_id", "arrival_time", "departure_time"},
            stop_times_file,
        )
        for row in reader:
            trip_id = row["trip_id"]
            if trip_id not in relevant:
                continue
            departure = parse_gtfs_time(row["departure_time"])
            arrival = parse_gtfs_time(row["arrival_time"])
            interval = intervals.setdefault(trip_id, [None, None])
            if departure is not None:
                interval[0] = (
                    departure
                    if interval[0] is None
                    else min(interval[0], departure)
                )
            if arrival is not None:
                interval[1] = (
                    arrival
                    if interval[1] is None
                    else max(interval[1], arrival)
                )

    service_counts: Counter[tuple[date, str, int]] = Counter()
    for trip_id, interval in intervals.items():
        start, end = interval
        if start is None or end is None:
            continue
        if end < start:
            raise ValueError(f"Plage horaire GTFS incohérente pour {trip_id}.")
        trip = relevant[trip_id]
        first_hour = start // 3600
        last_hour = max(start, end - 1) // 3600
        for service_date, active_ids in active_services.items():
            if trip.service_id not in active_ids:
                continue
            for hour in range(first_hour, last_hour + 1):
                service_counts[(service_date, trip.route_id, hour % 24)] += 1
    return dict(service_counts)


def load_profile(
    profile_file: Path,
) -> tuple[
    dict[tuple[str, str, int], float],
    dict[str, set[str]],
    dict[str, str],
    set[tuple[str, str, int]],
]:
    percentages: dict[tuple[str, str, int], float] = {}
    ambiguous_profile_keys: set[tuple[str, str, int]] = set()
    codes_by_label: dict[str, set[str]] = defaultdict(set)
    original_codes: dict[str, str] = {}

    with profile_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        _require_columns(
            reader,
            {
                "code_stif_ligne",
                "libelle_ligne",
                "cat_jour",
                "trnc_horr_60",
                "pourcentage_validations",
            },
            profile_file,
        )
        for row in reader:
            code = normalize_line_name(row["code_stif_ligne"])
            label = row["libelle_ligne"].strip()
            original_codes.setdefault(code, row["code_stif_ligne"])
            codes_by_label[normalize_line_name(row["code_stif_ligne"])].add(code)
            codes_by_label[normalize_line_name(label)].add(code)
            label_prefix = re.split(r"\s+-\s*", label, maxsplit=1)[0].strip()
            if label_prefix:
                codes_by_label[normalize_line_name(label_prefix)].add(code)
            if row["cat_jour"] not in PROFILE_CATEGORIES:
                continue
            match = re.fullmatch(r"(\d{1,2})H-\d{1,2}H", row["trnc_horr_60"])
            if not match:
                if row["trnc_horr_60"].strip().upper() == "ND":
                    continue
                raise ValueError(
                    f"Tranche horaire invalide dans {profile_file}: "
                    f"{row['trnc_horr_60']!r}"
                )
            hour = int(match.group(1))
            if not 0 <= hour <= 23:
                raise ValueError(
                    f"Tranche horaire invalide dans {profile_file}: "
                    f"{row['trnc_horr_60']!r}"
                )
            key = (code, row["cat_jour"], hour)
            percentage = float(row["pourcentage_validations"])
            if key in percentages and percentages[key] != percentage:
                ambiguous_profile_keys.add(key)
            else:
                percentages[key] = percentage
    for key in ambiguous_profile_keys:
        percentages.pop(key, None)
    return percentages, codes_by_label, original_codes, ambiguous_profile_keys


def average_daily_validations(
    validation_file: Path,
    line_codes: set[str],
    categories: set[str],
) -> tuple[dict[tuple[str, str], float], dict[str, int], tuple[str, str]]:
    counts_by_line_date: Counter[tuple[str, date]] = Counter()
    validation_dates: set[date] = set()
    with validation_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        _require_columns(
            reader,
            {"jour", "code_stif_ligne", "nb_vald"},
            validation_file,
        )
        for row in reader:
            try:
                validation_date = date.fromisoformat(row["jour"])
                count = int(row["nb_vald"])
            except ValueError as exc:
                raise ValueError(
                    f"Date ou nombre de validations invalide dans {validation_file}."
                ) from exc
            validation_dates.add(validation_date)
            code = normalize_line_name(row["code_stif_ligne"])
            if code in line_codes:
                counts_by_line_date[(code, validation_date)] += count

    category_dates: dict[str, set[date]] = {
        category: {
            day
            for day in validation_dates
            if _validation_day_matches(day, category)
        }
        for category in categories
    }
    totals_by_line_category: dict[tuple[str, str], int] = Counter()
    for category, days in category_dates.items():
        if not days:
            continue
        for (code, validation_date), count in counts_by_line_date.items():
            if validation_date in days:
                totals_by_line_category[(code, category)] += count
    daily_averages = {
        key: total / len(category_dates[key[1]])
        for key, total in totals_by_line_category.items()
    }

    if validation_dates:
        period = (
            min(validation_dates).isoformat(),
            max(validation_dates).isoformat(),
        )
    else:
        period = ("", "")
    day_counts = {category: len(days) for category, days in category_dates.items()}
    return daily_averages, day_counts, period


def normalize_numeric_identifier(value: str) -> str | None:
    normalized = value.strip()
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    if not normalized.isdigit():
        return None
    return normalized.lstrip("0") or "0"


def load_rail_validation_data(
    validation_file: Path,
    profile_file: Path,
    categories: set[str],
) -> RailValidationData:
    counts_by_identity_date: Counter[tuple[RailStopIdentity, date]] = Counter()
    validation_dates: set[date] = set()

    with validation_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        _require_columns(
            reader,
            {
                "jour",
                "code_stif_trns",
                "code_stif_res",
                "code_stif_arret",
                "id_zdc",
                "nb_vald",
            },
            validation_file,
        )
        for row in reader:
            station_id = normalize_numeric_identifier(row["id_zdc"])
            if station_id is None:
                continue
            identity = (
                row["code_stif_trns"].strip(),
                row["code_stif_res"].strip(),
                row["code_stif_arret"].strip(),
                station_id,
            )
            try:
                validation_date = date.fromisoformat(row["jour"])
                count = int(row["nb_vald"])
            except ValueError as exc:
                raise ValueError(
                    f"Date ou nombre de validations invalide dans {validation_file}."
                ) from exc
            validation_dates.add(validation_date)
            counts_by_identity_date[(identity, validation_date)] += count

    dates_by_category = {
        category: {
            day
            for day in validation_dates
            if _validation_day_matches(day, category)
        }
        for category in categories
    }
    totals_by_identity_category: Counter[tuple[RailStopIdentity, str]] = Counter()
    for (identity, validation_date), count in counts_by_identity_date.items():
        for category, days in dates_by_category.items():
            if validation_date in days:
                totals_by_identity_category[(identity, category)] += count
    average_daily = {
        key: total / len(dates_by_category[key[1]])
        for key, total in totals_by_identity_category.items()
        if dates_by_category[key[1]]
    }
    identities_by_station: dict[str, set[RailStopIdentity]] = defaultdict(set)
    for identity, _ in counts_by_identity_date:
        identities_by_station[identity[3]].add(identity)

    hourly_shares: dict[tuple[RailStopIdentity, str, int], float] = {}
    ambiguous_profiles: set[tuple[RailStopIdentity, str, int]] = set()
    profile_categories = PROFILE_CATEGORIES
    with profile_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        _require_columns(
            reader,
            {
                "code_stif_trns",
                "code_stif_res",
                "code_stif_arret",
                "id_zdc",
                "cat_jour",
                "trnc_horr_60",
                "pourcentage_validations",
            },
            profile_file,
        )
        for row in reader:
            category = row["cat_jour"]
            if category not in profile_categories:
                continue
            station_id = normalize_numeric_identifier(row["id_zdc"])
            if station_id is None:
                continue
            identity = (
                row["code_stif_trns"].strip(),
                row["code_stif_res"].strip(),
                row["code_stif_arret"].strip(),
                station_id,
            )
            match = re.fullmatch(r"(\d{1,2})H-\d{1,2}H", row["trnc_horr_60"])
            if not match:
                if row["trnc_horr_60"].strip().upper() == "ND":
                    continue
                raise ValueError(
                    f"Tranche horaire invalide dans {profile_file}: "
                    f"{row['trnc_horr_60']!r}"
                )
            hour = int(match.group(1))
            if not 0 <= hour <= 23:
                raise ValueError(
                    f"Tranche horaire invalide dans {profile_file}: "
                    f"{row['trnc_horr_60']!r}"
                )
            key = (identity, category, hour)
            percentage = float(row["pourcentage_validations"])
            if key in hourly_shares and hourly_shares[key] != percentage:
                ambiguous_profiles.add(key)
            else:
                hourly_shares[key] = percentage
    for key in ambiguous_profiles:
        hourly_shares.pop(key, None)

    period = (
        (min(validation_dates).isoformat(), max(validation_dates).isoformat())
        if validation_dates
        else ("", "")
    )
    return RailValidationData(
        average_daily_validations=average_daily,
        hourly_shares_pct=hourly_shares,
        ambiguous_hourly_profiles=ambiguous_profiles,
        identities_by_station=dict(identities_by_station),
        validation_day_counts={
            category: len(days) for category, days in dates_by_category.items()
        },
        validation_period=period,
    )


def load_rail_route_stations(
    gtfs_dir: Path,
    rail_route_ids: set[str],
    validation_station_ids: set[str],
) -> tuple[dict[str, set[str]], set[str]]:
    stops_file = gtfs_dir / "stops.txt"
    stop_to_station: dict[str, str] = {}
    station_id_by_numeric_id: dict[str, str] = {}
    with stops_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require_columns(reader, {"stop_id", "parent_station"}, stops_file)
        for row in reader:
            stop_id = row["stop_id"].strip()
            station_id = row["parent_station"].strip() or stop_id
            stop_to_station[stop_id] = station_id
            numeric_id = normalize_numeric_identifier(
                station_id.rsplit(":", 1)[-1]
            )
            if numeric_id is not None:
                existing = station_id_by_numeric_id.setdefault(
                    numeric_id, station_id
                )
                if existing != station_id:
                    raise ValueError(
                        f"Identifiant numérique d'arrêt GTFS ambigu : {numeric_id}."
                    )

    station_ids_by_route: dict[str, set[str]] = defaultdict(set)
    trip_route: dict[str, str] = {}
    trips_file = gtfs_dir / "trips.txt"
    with trips_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require_columns(reader, {"trip_id", "route_id"}, trips_file)
        for row in reader:
            if row["route_id"] in rail_route_ids:
                trip_route[row["trip_id"]] = row["route_id"]

    stop_times_file = gtfs_dir / "stop_times.txt"
    with stop_times_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require_columns(reader, {"trip_id", "stop_id"}, stop_times_file)
        for row in reader:
            route_id = trip_route.get(row["trip_id"])
            if route_id is None:
                continue
            station_id = stop_to_station.get(row["stop_id"].strip())
            if station_id is None:
                continue
            numeric_id = normalize_numeric_identifier(
                station_id.rsplit(":", 1)[-1]
            )
            if numeric_id is not None:
                station_ids_by_route[route_id].add(numeric_id)

    mapped_ids = set(station_id_by_numeric_id) & validation_station_ids
    return dict(station_ids_by_route), mapped_ids


def _profile_categories_for_request(category: str) -> list[str]:
    if category == "WEEKEND":
        return ["DIJFP", "SAHV", "SAVS"]
    return [category]


def _mean_available_profile(
    percentages: dict[tuple[str, str, int], float],
    ambiguous_keys: set[tuple[str, str, int]],
    line_codes: set[str],
    categories: list[str],
    hour: int,
) -> tuple[float | None, list[str]]:
    values = [
        (code, profile_category, percentages[(code, profile_category, hour)])
        for code in sorted(line_codes)
        for profile_category in categories
        if (code, profile_category, hour) in percentages
        and (code, profile_category, hour) not in ambiguous_keys
    ]
    if not values:
        return None, []
    return (
        sum(value for _, _, value in values) / len(values),
        sorted({profile_category for _, profile_category, _ in values}),
    )


def resolve_surface_profile(
    percentages: dict[tuple[str, str, int], float],
    ambiguous_keys: set[tuple[str, str, int]],
    line_code: str | None,
    similar_line_codes: set[str],
    category: str,
    hour: int,
) -> tuple[float, list[str], str]:
    requested_categories = _profile_categories_for_request(category)
    all_codes = {
        code
        for code, _, _ in percentages
    }

    def line_values(
        codes: set[str], categories: list[str]
    ) -> tuple[float | None, list[str]]:
        return _mean_available_profile(
            percentages, ambiguous_keys, codes, categories, hour
        )

    if line_code is not None:
        value, used = line_values({line_code}, requested_categories)
        if value is not None:
            return value, used, "line_requested_day"
        other_categories = sorted(PROFILE_CATEGORIES - set(requested_categories))
        value, used = line_values({line_code}, other_categories)
        if value is not None:
            return value, used, "line_other_day"

    peers = similar_line_codes - ({line_code} if line_code else set())
    value, used = line_values(peers, requested_categories)
    if value is not None:
        return value, used, "similar_line_requested_day"
    other_categories = sorted(PROFILE_CATEGORIES - set(requested_categories))
    value, used = line_values(peers, other_categories)
    if value is not None:
        return value, used, "similar_line_other_day"
    value, used = line_values(all_codes, requested_categories)
    if value is not None:
        return value, used, "network_requested_day"
    value, used = line_values(
        all_codes,
        sorted(PROFILE_CATEGORIES - set(requested_categories)),
    )
    if value is not None:
        return value, used, "network_other_day"

    hourly_values = [
        (
            min(abs(profile_hour - hour), 24 - abs(profile_hour - hour)),
            profile_category,
            value,
        )
        for (code, profile_category, profile_hour), value in percentages.items()
        if code in all_codes
        and (code, profile_category, profile_hour) not in ambiguous_keys
    ]
    if not hourly_values:
        raise ValueError(
            f"Aucun profil horaire de surface disponible pour {hour}H."
        )
    nearest_distance = min(distance for distance, _, _ in hourly_values)
    nearest_values = [
        value
        for distance, _, value in hourly_values
        if distance == nearest_distance
    ]
    return (
        sum(nearest_values) / len(nearest_values),
        sorted(
            {
                category
                for distance, category, _ in hourly_values
                if distance == nearest_distance
            }
        ),
        "network_nearest_available_hour",
    )


def resolve_surface_daily_average(
    daily_averages: dict[tuple[str, str], float],
    line_code: str | None,
    similar_line_codes: set[str],
    category: str,
) -> tuple[float, str]:
    if line_code is not None and (line_code, category) in daily_averages:
        return daily_averages[(line_code, category)], "line_daily_validations"

    peer_codes = similar_line_codes - ({line_code} if line_code else set())
    peer_values = [
        daily_averages[(code, category)]
        for code in peer_codes
        if (code, category) in daily_averages
    ]
    if peer_values:
        return (
            sum(peer_values) / len(peer_values),
            "similar_line_daily_validations",
        )

    network_values = [
        value
        for (_, day_category), value in daily_averages.items()
        if day_category == category
    ]
    if not network_values:
        raise ValueError(
            f"Aucune validation quotidienne de surface disponible pour {category}."
        )
    return sum(network_values) / len(network_values), "network_daily_validations"


def estimate_rail_route_hour(
    route_station_ids: set[str],
    rail_data: RailValidationData,
    category: str,
    hour: int,
) -> tuple[float, float, int, list[str], list[str], list[str]]:
    matched_station_ids = route_station_ids & set(rail_data.identities_by_station)
    if route_station_ids:
        station_ids = route_station_ids
    else:
        station_ids = {"network_fallback"}
    route_identities = {
        identity
        for station_id in matched_station_ids
        for identity in rail_data.identities_by_station[station_id]
    }
    network_identities = {
        identity
        for identities in rail_data.identities_by_station.values()
        for identity in identities
    }
    requested_categories = _profile_categories_for_request(category)

    def daily_value(
        identity: RailStopIdentity | None,
    ) -> tuple[float, str]:
        if identity is not None:
            exact = rail_data.average_daily_validations.get((identity, category))
            if exact is not None:
                return exact, "station_daily_validations"

        excluded_station = identity[3] if identity is not None else None
        route_peer_stations = matched_station_ids - (
            {excluded_station} if excluded_station is not None else set()
        )
        peer_values = [
            sum(
                rail_data.average_daily_validations[(peer, category)]
                for peer in rail_data.identities_by_station[station_id]
                if (peer, category) in rail_data.average_daily_validations
            )
            for station_id in route_peer_stations
            if any(
                (peer, category) in rail_data.average_daily_validations
                for peer in rail_data.identities_by_station[station_id]
            )
        ]
        if peer_values:
            return (
                sum(peer_values) / len(peer_values),
                "route_peer_station_daily_validations",
            )

        network_values = [
            sum(
                rail_data.average_daily_validations[(peer, category)]
                for peer in identities
                if (peer, category) in rail_data.average_daily_validations
            )
            for identities in rail_data.identities_by_station.values()
            if any(
                (peer, category) in rail_data.average_daily_validations
                for peer in identities
            )
        ]
        if network_values:
            return (
                sum(network_values) / len(network_values),
                "network_daily_validations",
            )
        raise ValueError(
            f"Aucune validation quotidienne ferrée disponible pour {category}."
        )

    def profile_value(
        identity: RailStopIdentity | None,
    ) -> tuple[float, list[str], str]:
        def identity_values(
            identities: set[RailStopIdentity], categories: list[str]
        ) -> tuple[float | None, list[str]]:
            values = [
                (profile_category, value)
                for source_identity in identities
                for profile_category in categories
                if (
                    source_identity,
                    profile_category,
                    hour,
                ) in rail_data.hourly_shares_pct
                and (
                    source_identity,
                    profile_category,
                    hour,
                ) not in rail_data.ambiguous_hourly_profiles
                for value in [
                    rail_data.hourly_shares_pct[
                        (source_identity, profile_category, hour)
                    ]
                ]
            ]
            if not values:
                return None, []
            return (
                sum(value for _, value in values) / len(values),
                sorted({profile_category for profile_category, _ in values}),
            )

        if identity is not None:
            value, categories_used = identity_values(
                {identity}, requested_categories
            )
            if value is not None:
                return value, categories_used, "station_requested_day"

            other_categories = sorted(
                PROFILE_CATEGORIES - set(requested_categories)
            )
            value, categories_used = identity_values(
                {identity}, other_categories
            )
            if value is not None:
                return value, categories_used, "station_other_day"

        other_categories = sorted(PROFILE_CATEGORIES - set(requested_categories))
        if route_identities:
            route_peers = route_identities - ({identity} if identity else set())
            value, categories_used = identity_values(
                route_peers, requested_categories
            )
            if value is not None:
                return (
                    value,
                    categories_used,
                    "route_peer_station_requested_day",
                )
            value, categories_used = identity_values(
                route_peers, other_categories
            )
            if value is not None:
                return (
                    value,
                    categories_used,
                    "route_peer_station_other_day",
                )

        value, categories_used = identity_values(
            network_identities, requested_categories
        )
        if value is not None:
            return value, categories_used, "network_requested_day"
        value, categories_used = identity_values(
            network_identities, other_categories
        )
        if value is not None:
            return value, categories_used, "network_other_day"

        profile_values = [
            (
                min(abs(profile_hour - hour), 24 - abs(profile_hour - hour)),
                profile_category,
                value,
            )
            for (source_identity, profile_category, profile_hour), value
            in rail_data.hourly_shares_pct.items()
            if (source_identity, profile_category, profile_hour)
            not in rail_data.ambiguous_hourly_profiles
        ]
        if not profile_values:
            raise ValueError("Aucun profil horaire ferré disponible.")
        distance = min(item[0] for item in profile_values)
        return (
            sum(
                value
                for gap, _, value in profile_values
                if gap == distance
            )
            / sum(gap == distance for gap, _, _ in profile_values),
            sorted(
                {
                    profile_category
                    for gap, profile_category, _ in profile_values
                    if gap == distance
                }
            ),
            "network_nearest_available_hour",
        )

    daily_total = 0.0
    hourly_total = 0.0
    profile_categories_used: set[str] = set()
    baseline_methods: set[str] = set()
    profile_methods: set[str] = set()
    for station_id in sorted(station_ids):
        identities = sorted(
            rail_data.identities_by_station.get(station_id, set())
        )
        station_identities: list[RailStopIdentity | None] = (
            identities if identities else [None]
        )
        for identity in station_identities:
            daily, baseline_method = daily_value(identity)
            share, used_categories, profile_method = profile_value(identity)
            daily_total += daily
            hourly_total += daily * share / 100
            baseline_methods.add(baseline_method)
            profile_methods.add(profile_method)
            profile_categories_used.update(used_categories)

    overall_share = hourly_total / daily_total * 100 if daily_total else 0.0
    return (
        daily_total,
        overall_share,
        len(matched_station_ids),
        sorted(profile_categories_used),
        sorted(baseline_methods),
        sorted(profile_methods),
    )


def _validation_day_matches(day: date, category: str) -> bool:
    if category == "WEEKEND":
        return day.weekday() in {5, 6}
    if category == "DIJFP":
        return (
            day.weekday() == 6
            or day in french_public_holidays(day.year)
        )
    if category in {"SAHV", "SAVS"}:
        return day.weekday() == 5
    if category in {"JOVS", "JOHV"}:
        return day.weekday() < 5
    raise ValueError(f"Catégorie de jour inconnue : {category}")


def route_network_class(route_type: int | None) -> str:
    if route_type in SURFACE_ROUTE_TYPES:
        return "surface"
    if route_type in RAIL_ROUTE_TYPES:
        return "rail"
    if route_type is None:
        return "unknown"
    return "other"


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    scenario_files = sorted(args.scenarios_dir.glob("*/journeys.json"))
    if not scenario_files:
        raise FileNotFoundError(
            f"Aucun fichier journeys.json dans {args.scenarios_dir.resolve()}."
        )

    arcs, scenarios, source_arc_count = collect_transit_arcs(
        scenario_files, args.day_category
    )
    if not arcs:
        raise ValueError(
            "Aucun arc de transport collectif trouvé dans les scénarios."
        )

    routes = load_routes(args.gtfs_dir)
    observed_trip_ids = {str(arc["gtfs_trip_id"]) for arc in arcs}
    observed_trips, observed_route_ids = load_observed_trips(
        args.gtfs_dir, observed_trip_ids
    )
    relevant_route_ids = {
        route_id
        for route_id in observed_route_ids
        if route_id in routes
    }
    relevant_trips = load_relevant_trips(args.gtfs_dir, relevant_route_ids)
    service_dates = {metadata.service_date for metadata in scenarios.values()}
    active_services = active_services_by_date(args.gtfs_dir, service_dates)
    service_counts = scheduled_services_by_hour(
        args.gtfs_dir, relevant_trips, active_services
    )

    (
        surface_percentages,
        codes_by_label,
        original_line_codes,
        ambiguous_surface_profiles,
    ) = load_profile(
        args.validation_dir / "profilshoraires-surface-T4-2026.csv"
    )
    surface_codes_by_group: dict[str, set[str]] = defaultdict(set)
    for label, line_codes in codes_by_label.items():
        surface_codes_by_group[line_similarity_group(label)].update(line_codes)
    route_validation_codes: dict[str, str | None] = {}
    ambiguous_route_mapping: set[str] = set()
    rail_route_ids: set[str] = set()
    for route_id in relevant_route_ids:
        route = routes[route_id]
        if route_network_class(route.route_type) == "rail":
            rail_route_ids.add(route_id)
            continue
        if route_network_class(route.route_type) != "surface":
            continue
        route_name = route.short_name
        candidates = codes_by_label.get(normalize_line_name(route_name), set())
        if len(candidates) == 1:
            code = next(iter(candidates))
            route_validation_codes[route_id] = code
        elif len(candidates) > 1:
            route_validation_codes[route_id] = None
            ambiguous_route_mapping.add(route_id)
        else:
            route_validation_codes[route_id] = None

    validation_categories = {
        str(arc["validation_day_category"]) for arc in arcs
    }
    daily_averages, surface_day_counts, surface_validation_period = (
        average_daily_validations(
            args.validation_dir / "validations-surface-T4-2026.csv",
            set(original_line_codes),
            validation_categories,
        )
    )
    rail_data = load_rail_validation_data(
        args.validation_dir / "validations-fer-T4-2026.csv",
        args.validation_dir / "profilshoraires-fer-T4-2026.csv",
        validation_categories,
    )
    rail_route_stations, mapped_rail_station_ids = load_rail_route_stations(
        args.gtfs_dir,
        rail_route_ids,
        set(rail_data.identities_by_station),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    arcs_file = args.output_dir / "ridership_by_transit_arc.csv"
    summary_file = args.output_dir / "ridership_coverage_summary.json"
    unique_class_counts: Counter[str] = Counter()
    occurrence_class_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    occurrence_status_counts: Counter[str] = Counter()
    missing_estimate_counts: Counter[str] = Counter()
    missing_estimate_occurrence_counts: Counter[str] = Counter()
    baseline_method_counts: Counter[str] = Counter()
    profile_method_counts: Counter[str] = Counter()
    service_count_method_counts: Counter[str] = Counter()
    vehicle_category_counts: Counter[str] = Counter()
    vehicle_size_ratios: dict[str, float] = {}

    with arcs_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ARC_COLUMNS)
        writer.writeheader()
        for arc in arcs:
            trip_id = str(arc["gtfs_trip_id"])
            trip = observed_trips.get(trip_id)
            route = routes.get(trip.route_id) if trip else None
            route_type = route.route_type if route else None
            if route is None:
                raise ValueError(
                    "Impossible d'affecter un ratio de taille de véhicule : "
                    f"trajet GTFS {trip_id!r} ou sa ligne est introuvable."
                )
            vehicle_category, vehicle_size_ratio = vehicle_size_adjustment(route)
            vehicle_category_counts[vehicle_category] += 1
            vehicle_size_ratios[vehicle_category] = vehicle_size_ratio
            network_class = route_network_class(route_type)
            unique_class_counts[network_class] += 1
            occurrence_count = int(arc["arc_occurrence_count"])
            occurrence_class_counts[network_class] += occurrence_count
            route_id = route.route_id if route else None
            category = str(arc["validation_day_category"])
            hour = int(arc["hour"])
            average = None
            profile_pct = None
            estimated_hourly_validations = None
            scheduled_count = None
            per_service = None
            validation_method = ""
            baseline_method = ""
            profile_method = ""
            service_count_method = ""
            validation_line_code = ""
            validation_stop_count = None
            profile_categories_used: list[str] = []

            if network_class == "surface":
                line_code = (
                    route_validation_codes.get(route_id)
                    if route_id is not None
                    else None
                )
                route_name = route.short_name if route else ""
                similar_line_codes = surface_codes_by_group.get(
                    line_similarity_group(route_name),
                    set(original_line_codes),
                )
                validation_line_code = (
                    original_line_codes.get(line_code, "") if line_code else ""
                )
                average, baseline_method = resolve_surface_daily_average(
                    daily_averages,
                    line_code,
                    similar_line_codes,
                    category,
                )
                (
                    profile_pct,
                    profile_categories_used,
                    profile_method,
                ) = resolve_surface_profile(
                    surface_percentages,
                    ambiguous_surface_profiles,
                    line_code,
                    similar_line_codes,
                    category,
                    hour,
                )
                scheduled_count = (
                    service_counts.get((arc["service_date"], route_id, hour), 0)
                    if route_id is not None
                    else 0
                )
                if scheduled_count:
                    service_count_method = "gtfs_scheduled_services"
                else:
                    scheduled_count = 1
                    service_count_method = "observed_trip_minimum"
                validation_method = "surface_line_or_similarity_proxy"
                status = "estimated"
            elif network_class == "rail":
                validation_method = "station_validations_aggregated_to_route"
                validation_line_code = route.short_name
                route_stations = rail_route_stations.get(route_id, set())
                missing_station_ids = (
                    route_stations - set(rail_data.identities_by_station)
                )
                (
                    average,
                    profile_pct,
                    validation_stop_count,
                    profile_categories_used,
                    baseline_methods,
                    profile_methods,
                ) = estimate_rail_route_hour(
                    route_stations,
                    rail_data,
                    category,
                    hour,
                )
                scheduled_count = service_counts.get(
                    (arc["service_date"], route_id, hour), 0
                )
                baseline_method = ";".join(baseline_methods)
                profile_method = ";".join(profile_methods)
                if scheduled_count:
                    service_count_method = "gtfs_scheduled_services"
                else:
                    scheduled_count = 1
                    service_count_method = "observed_trip_minimum"
                status = (
                    "estimated_partial_rail_station_mapping"
                    if missing_station_ids
                    else "estimated"
                )
            else:
                similar_line_codes = set(original_line_codes)
                average, baseline_method = resolve_surface_daily_average(
                    daily_averages,
                    None,
                    similar_line_codes,
                    category,
                )
                (
                    profile_pct,
                    profile_categories_used,
                    profile_method,
                ) = resolve_surface_profile(
                    surface_percentages,
                    ambiguous_surface_profiles,
                    None,
                    similar_line_codes,
                    category,
                    hour,
                )
                scheduled_count = (
                    service_counts.get((arc["service_date"], route_id, hour), 0)
                    if route_id is not None
                    else 0
                )
                if scheduled_count:
                    service_count_method = "gtfs_scheduled_services"
                else:
                    scheduled_count = 1
                    service_count_method = "observed_trip_minimum"
                validation_method = "surface_network_proxy_for_unclassified_route"
                status = "estimated_with_network_fallback"

            if network_class == "surface":
                if (
                    baseline_method != "line_daily_validations"
                    or profile_method != "line_requested_day"
                    or service_count_method != "gtfs_scheduled_services"
                ):
                    status = "estimated_with_fallback"
            elif network_class == "rail":
                if (
                    status == "estimated"
                    and (
                        any(
                            method != "station_daily_validations"
                            for method in baseline_methods
                        )
                        or any(
                            method != "station_requested_day"
                            for method in profile_methods
                        )
                        or service_count_method != "gtfs_scheduled_services"
                    )
                ):
                    status = "estimated_with_fallback"
                elif status == "estimated_partial_rail_station_mapping" and (
                    any(
                        method != "station_daily_validations"
                        for method in baseline_methods
                    )
                    or any(
                        method != "station_requested_day"
                        for method in profile_methods
                    )
                    or service_count_method != "gtfs_scheduled_services"
                ):
                    status = "estimated_partial_rail_station_mapping_with_fallback"

            estimated_hourly_validations = average * profile_pct / 100
            per_service = estimated_hourly_validations / scheduled_count
            rounded_per_service = round(per_service, 6)
            adjusted_per_service = adjust_estimate_for_vehicle_size(
                rounded_per_service,
                vehicle_size_ratio,
            )
            normalized_score = normalized_vehicle_adjusted_score(
                adjusted_per_service
            )

            status_counts[status] += 1
            occurrence_status_counts[status] += occurrence_count
            baseline_method_counts.update(baseline_method.split(";"))
            profile_method_counts.update(profile_method.split(";"))
            service_count_method_counts.update(service_count_method.split(";"))
            if per_service is None:
                missing_estimate_counts[network_class] += 1
                missing_estimate_occurrence_counts[network_class] += occurrence_count
            writer.writerow(
                {
                    "service_date": arc["service_date"].isoformat(),
                    "arc_occurrence_count": occurrence_count,
                    "gtfs_trip_id": trip_id,
                    "route_id": route_id or "",
                    "route_short_name": route.short_name if route else "",
                    "route_type": route_type if route_type is not None else "",
                    "network_class": network_class,
                    "start_time": arc["start_time"],
                    "end_time": arc["end_time"],
                    "hour_bucket": arc["hour_bucket"],
                    "from_stop": arc["from_stop"] or "",
                    "to_stop": arc["to_stop"] or "",
                    "validation_method": validation_method,
                    "validation_baseline_method": baseline_method,
                    "hourly_profile_method": profile_method,
                    "service_count_method": service_count_method,
                    "validation_line_code": validation_line_code,
                    "validation_day_category": category,
                    "validation_stop_count": (
                        validation_stop_count
                        if validation_stop_count is not None
                        else ""
                    ),
                    "profile_categories_used": ";".join(profile_categories_used),
                    "average_daily_validations": (
                        round(average, 3) if average is not None else ""
                    ),
                    "hourly_validation_share_pct": (
                        profile_pct if profile_pct is not None else ""
                    ),
                    "estimated_validations_in_hour": (
                        round(estimated_hourly_validations, 3)
                        if estimated_hourly_validations is not None
                        else ""
                    ),
                    "scheduled_services_in_hour": (
                        scheduled_count if scheduled_count is not None else ""
                    ),
                    "estimated_validations_per_service": (
                        rounded_per_service
                    ),
                    "vehicle_category": vehicle_category,
                    "vehicle_size_ratio": vehicle_size_ratio,
                    "estimated_validations_per_service_adjusted": (
                        normalized_score
                    ),
                    "validation_status": status,
                }
            )

    classified_count = sum(
        unique_class_counts[network]
        for network in ("surface", "rail", "other")
    )
    rail_share = (
        unique_class_counts["rail"] / classified_count * 100
        if classified_count
        else None
    )
    summary = {
        "scenario_count": len(scenarios),
        "service_dates": sorted(day.isoformat() for day in service_dates),
        "source_transit_arc_occurrence_count": source_arc_count,
        "unique_transit_arc_count": len(arcs),
        "duplicate_arc_occurrences_removed": source_arc_count - len(arcs),
        "arc_occurrence_count_by_network_class": dict(
            sorted(occurrence_class_counts.items())
        ),
        "unique_arc_count_by_network_class": dict(
            sorted(unique_class_counts.items())
        ),
        "rail_arc_share_pct_of_classified_transit_arcs": (
            round(rail_share, 3) if rail_share is not None else None
        ),
        "unique_arc_count_by_validation_status": dict(
            sorted(status_counts.items())
        ),
        "baseline_method_counts": dict(sorted(baseline_method_counts.items())),
        "hourly_profile_method_counts": dict(
            sorted(profile_method_counts.items())
        ),
        "service_count_method_counts": dict(
            sorted(service_count_method_counts.items())
        ),
        "vehicle_size_adjustment": {
            "score_column": "estimated_validations_per_service_adjusted",
            "formula": (
                "100 × (1 - min(max(round(estimated_validations_per_service "
                "× vehicle_size_ratio, 6), 0), 50) / 50)"
            ),
            "score_range": [0, 100],
            "ratios_by_category": dict(sorted(vehicle_size_ratios.items())),
            "arc_counts_by_category": dict(
                sorted(vehicle_category_counts.items())
            ),
        },
        "arc_occurrence_count_by_validation_status": dict(
            sorted(occurrence_status_counts.items())
        ),
        "arcs_without_estimate_by_network_class": dict(
            sorted(missing_estimate_counts.items())
        ),
        "arc_occurrences_without_estimate_by_network_class": dict(
            sorted(missing_estimate_occurrence_counts.items())
        ),
        "surface_routes_without_validation_mapping": sum(
            1
            for route_id, code in route_validation_codes.items()
            if code is None
        ),
        "ambiguous_surface_route_mappings": len(ambiguous_route_mapping),
        "rail_route_count": len(rail_route_ids),
        "rail_routes_with_gtfs_stations": sum(
            bool(rail_route_stations.get(route_id))
            for route_id in rail_route_ids
        ),
        "rail_validation_station_mapping": {
            "validation_station_count": len(rail_data.identities_by_station),
            "gtfs_matched_validation_station_count": len(mapped_rail_station_ids),
            "gtfs_match_share_pct": (
                round(
                    len(mapped_rail_station_ids)
                    / len(rail_data.identities_by_station)
                    * 100,
                    3,
                )
                if rail_data.identities_by_station
                else None
            ),
        },
        "validation_source_periods": {
            "surface": {
                "start": surface_validation_period[0],
                "end": surface_validation_period[1],
            },
            "rail": {
                "start": rail_data.validation_period[0],
                "end": rail_data.validation_period[1],
            },
        },
        "validation_days_used_by_source_category": {
            "surface": surface_day_counts,
            "rail": rail_data.validation_day_counts,
        },
        "calculation_notes": [
            (
                "The value is an approximate count of validations per scheduled "
                "trip, not vehicle occupancy."
            ),
            (
                "Scenario dates that use the DIJFP category use daily validation "
                "totals averaged over Saturdays and Sundays. Their hourly "
                "profile share is the unweighted mean of available DIJFP, SAHV, "
                "and SAVS profiles."
            ),
            (
                "The daily validation files do not distinguish school periods; "
                "Saturday and Sunday validation totals are pooled for weekend "
                "scenarios."
            ),
            (
                "Rail validations are aggregated by station and assigned in "
                "full to every GTFS rail route serving that station; shared "
                "stations can therefore be counted on multiple routes."
            ),
            (
                "Missing validation baselines and hourly profiles are imputed "
                "from same-line other-day data, similar lines/stations, or "
                "network averages, with the method recorded per arc."
            ),
            (
                "A scheduled service is counted once per route and hour if its "
                "GTFS trip overlaps that hour."
            ),
            (
                "If the GTFS service count is zero for an observed transit arc, "
                "the estimate uses a minimum service count of one."
            ),
        ],
    }
    summary_file.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Arcs annotés : {arcs_file.resolve()}")
    print(f"Résumé de couverture : {summary_file.resolve()}")
    print(
        f"Arcs TC uniques : {len(arcs):,} "
        f"(occurrences initiales : {source_arc_count:,} ; "
        f"doublons retirés : {source_arc_count - len(arcs):,}) ; "
        f"ferré : {unique_class_counts['rail']:,} "
        f"({rail_share:.1f}% des arcs classés)"
        if rail_share is not None
        else "Aucun arc TC classé via le GTFS."
    )
    available_estimates = len(arcs) - sum(missing_estimate_counts.values())
    print(f"Estimations disponibles : {available_estimates:,}")
    print("Arcs uniques sans estimation par réseau :")
    any_missing_network = False
    for network_class, count in sorted(missing_estimate_counts.items()):
        any_missing_network = True
        print(f"  {network_class} : {count:,}")
    if not any_missing_network:
        print("  aucun")
    print("Arcs uniques sans estimation par statut :")
    any_missing_estimate = False
    for status, count in sorted(status_counts.items()):
        if not status.startswith("estimated"):
            any_missing_estimate = True
            print(f"  {status} : {count:,}")
    if not any_missing_estimate:
        print("  aucun")


if __name__ == "__main__":
    main()