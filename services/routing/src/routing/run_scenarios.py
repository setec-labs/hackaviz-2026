"""Run the transit accessibility calculation for a list of scenarios."""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "input"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "scenarios"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "output" / "transit_accessibility_cache"
TRANSIT_SCRIPT = Path(__file__).with_name("transit_accessibility.py")
SCENARIO_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run transit accessibility for scenarios listed in a JSON file."
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        required=True,
        help=(
            "JSON file containing scenario_id, description, origin_lat, "
            "origin_lon and departure_time."
        ),
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Shared graph/cache folder reused by every scenario.",
    )
    parser.add_argument(
        "--service-date",
        default="2026-11-08",
        help="GTFS service date for all scenarios (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--all-communes",
        action="store_true",
        help="Use every commune town hall as a destination for each scenario.",
    )
    parser.add_argument("--max-destinations", type=int, default=None)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip scenarios whose output already contains a valid journeys.json.",
    )
    return parser.parse_args(argv)


def load_scenarios(path: Path) -> list[dict[str, str | float]]:
    try:
        scenarios = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Impossible de lire le fichier des scénarios {path}: {exc}") from exc

    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Le JSON des scénarios doit être une liste non vide.")

    validated = []
    seen_ids = set()
    required_fields = {
        "scenario_id",
        "description",
        "origin_lat",
        "origin_lon",
        "departure_time",
    }
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise ValueError(f"Le scénario à l'index {index} doit être un objet JSON.")
        missing_fields = required_fields - scenario.keys()
        if missing_fields:
            raise ValueError(
                f"Champs manquants dans le scénario à l'index {index}: "
                f"{', '.join(sorted(missing_fields))}"
            )

        scenario_id = scenario["scenario_id"]
        if not isinstance(scenario_id, str) or not SCENARIO_ID_PATTERN.fullmatch(scenario_id):
            raise ValueError(
                f"scenario_id invalide à l'index {index}: utilisez 1 à 64 caractères "
                "alphanumériques, '.', '_' ou '-', en commençant par un caractère alphanumérique."
            )
        if scenario_id in seen_ids:
            raise ValueError(f"scenario_id dupliqué: {scenario_id}")
        seen_ids.add(scenario_id)

        description = scenario["description"]
        if not isinstance(description, str):
            raise ValueError(f"description doit être une chaîne de caractères ({scenario_id}).")

        try:
            latitude = float(scenario["origin_lat"])
            longitude = float(scenario["origin_lon"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Coordonnées invalides pour le scénario {scenario_id}.") from exc
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError(f"Coordonnées hors limites pour le scénario {scenario_id}.")

        departure_time = scenario["departure_time"]
        if not isinstance(departure_time, str):
            raise ValueError(f"departure_time doit être une chaîne HH:MM:SS ({scenario_id}).")
        try:
            hours, minutes, seconds = map(int, departure_time.split(":"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"departure_time invalide pour {scenario_id}: utilisez HH:MM:SS."
            ) from exc
        if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
            raise ValueError(
                f"departure_time invalide pour {scenario_id}: utilisez HH:MM:SS."
            )

        validated.append(
            {
                "scenario_id": scenario_id,
                "description": description,
                "origin_lat": latitude,
                "origin_lon": longitude,
                "departure_time": departure_time,
            }
        )
    return validated


def has_valid_journeys(path: Path, scenario: dict[str, str | float]) -> bool:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(document, dict)
        and document.get("name") == scenario["scenario_id"]
        and document.get("description") == scenario["description"]
        and isinstance(document.get("journeys"), list)
        and bool(document["journeys"])
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    service_date = date.fromisoformat(args.service_date)
    if args.max_destinations is not None and args.max_destinations < 1:
        raise ValueError("--max-destinations doit être supérieur ou égal à 1.")

    scenarios = load_scenarios(args.scenarios)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"{len(scenarios)} scénario(s), exécution séquentielle. "
        f"Le graphe piéton sera partagé via {args.cache_dir.resolve()}.",
        flush=True,
    )
    started_at = time.perf_counter()
    completed = 0
    skipped = 0

    for index, scenario in enumerate(scenarios, start=1):
        scenario_id = scenario["scenario_id"]
        scenario_output_dir = args.output_dir / scenario_id
        journey_file = scenario_output_dir / "journeys.json"
        if args.resume and has_valid_journeys(journey_file, scenario):
            skipped += 1
            print(
                f"[{index}/{len(scenarios)}] {scenario_id}: résultat déjà présent, ignoré.",
                flush=True,
            )
            continue

        command = [
            sys.executable,
            str(TRANSIT_SCRIPT),
            "--data-dir",
            str(args.data_dir.resolve()),
            "--output-dir",
            str(scenario_output_dir.resolve()),
            "--cache-dir",
            str(args.cache_dir.resolve()),
            "--service-date",
            service_date.isoformat(),
            "--departure-time",
            scenario["departure_time"],
            "--scenario-name",
            scenario["scenario_id"],
            "--scenario-description",
            scenario["description"],
            "--origin-lat",
            str(scenario["origin_lat"]),
            "--origin-lon",
            str(scenario["origin_lon"]),
        ]
        if args.all_communes:
            command.append("--all-communes")
        if args.max_destinations is not None:
            command.extend(("--max-destinations", str(args.max_destinations)))

        print(
            f"[{index}/{len(scenarios)}] {scenario_id}: "
            f"départ {scenario['departure_time']} depuis "
            f"({scenario['origin_lat']}, {scenario['origin_lon']})",
            flush=True,
        )
        scenario_started_at = time.perf_counter()
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
        completed += 1
        duration_minutes = (time.perf_counter() - scenario_started_at) / 60
        print(
            f"[{index}/{len(scenarios)}] {scenario_id}: terminé en "
            f"{duration_minutes:.1f} min; sortie: {journey_file.resolve()}",
            flush=True,
        )

    total_minutes = (time.perf_counter() - started_at) / 60
    print(
        f"Terminé : {completed} calcul(s), {skipped} scénario(s) repris, "
        f"{total_minutes:.1f} min au total."
    )


if __name__ == "__main__":
    main()
