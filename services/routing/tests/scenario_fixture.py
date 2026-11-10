from hackaviz_2026.routing import Scenario


def make_scenario(scenario_id: str = "test-hospital") -> Scenario:
    return Scenario.model_validate({
        "id": scenario_id,
        "name": "Trajet vers un hôpital de test",
        "description": "Scénario synthétique réservé aux tests.",
        "type": "hospital",
        "origin": {"latitude": 48.85, "longitude": 2.35},
        "departure_time": "2026-11-08T02:00:00+01:00",
        "journey": {
            "journey_id": "test-journey",
            "destination": {"latitude": 48.86, "longitude": 2.36, "name": "Hôpital de test"},
            "start_time": "2026-11-08T02:00:00+01:00",
            "end_time": "2026-11-08T02:01:00+01:00",
            "legs": [{
                "mode": "walk_access",
                "start_time": "2026-11-08T02:00:00+01:00",
                "end_time": "2026-11-08T02:01:00+01:00",
                "from_stop": "ORIGIN",
                "to_stop": "DESTINATION",
                "gtfs_trip_id": None,
                "point_range": [0, 2],
            }],
            "coordinates": [[2.35, 48.85], [2.36, 48.86]],
            "offsets_s": [0, 60],
        },
    })
