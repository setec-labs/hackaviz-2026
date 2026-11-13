from pathlib import Path
from typing import Any

from hackaviz_2026.routing import Scenario, ScenarioDocument


def make_journey(journey_id: str = "j-1", destination_name: str = "Hôpital de test") -> dict[str, Any]:
    return {
        "journey_id": journey_id,
        "destination": {"latitude": 48.86, "longitude": 2.36, "name": destination_name},
        "start_time": "2026-11-08T02:00:00+01:00",
        "end_time": "2026-11-08T02:01:00+01:00",
        "legs": [{
            "mode": "walk_direct",
            "start_time": "2026-11-08T02:00:00+01:00",
            "end_time": "2026-11-08T02:01:00+01:00",
            "from_stop": "ORIGIN",
            "to_stop": "DESTINATION",
            "gtfs_trip_id": None,
            "point_range": [0, 2],
        }],
        "coordinates": [[2.35, 48.85], [2.36, 48.86]],
        "offsets_s": [0, 60],
    }


def make_document_payload(with_metadata: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "origin": {"latitude": 48.85, "longitude": 2.35},
        "departure_time": "2026-11-08T02:00:00+01:00",
        "journeys": [make_journey("j-1", "Hôpital A"), make_journey("j-2", "Hôpital B")],
    }
    if with_metadata:
        payload = {"name": "Sortie de test", "description": "Scénario synthétique réservé aux tests.", **payload}
    return payload


def make_document(with_metadata: bool = True) -> ScenarioDocument:
    return ScenarioDocument.model_validate(make_document_payload(with_metadata))


def make_scenario(scenario_id: str = "Test-Scenario") -> Scenario:
    document = make_document()
    return Scenario(
        id=scenario_id,
        name=document.name or scenario_id,
        description=document.description or scenario_id,
        metadata_generated=False,
        origin=document.origin,
        departure_time=document.departure_time,
        journey_count=len(document.journeys),
        journeys=document.journeys,
    )


def write_document(directory: Path, scenario_id: str, content: str) -> Path:
    scenario_directory = directory / scenario_id
    scenario_directory.mkdir(parents=True, exist_ok=True)
    path = scenario_directory / "journeys.json"
    path.write_text(content, encoding="utf-8")
    return path
