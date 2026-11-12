import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from hackaviz_2026.routing import ScenarioDocument
from routing.optimize import (
    OPTIMIZED_FILENAME,
    OptimizationError,
    main,
    optimize_directory,
    optimize_document,
    simplify_trajectory,
)
from routing.repository import ScenarioRepository
from scenario_fixture import make_document_payload, write_document


def straight_walk_journey() -> dict[str, object]:
    """Walk of 10 aligned points at constant speed, a 2-point wait, then a 3-point transit leg."""
    coordinates = [[2.35 + 0.0001 * index, 48.85] for index in range(10)]
    coordinates += [[2.3509, 48.85], [2.3509, 48.85], [2.36, 48.86], [2.37, 48.86], [2.38, 48.87]]
    offsets = [10.0 * index for index in range(10)] + [100.0, 200.0, 260.0, 270.0, 300.0]
    return {
        "journey_id": "j-1",
        "destination": {"latitude": 48.87, "longitude": 2.38, "name": "Gare", "population": 1200},
        "start_time": "2026-11-08T02:00:00+01:00",
        "end_time": "2026-11-08T02:05:00+01:00",
        "legs": [
            _leg("walk_access", "02:00:00", "02:01:30", [0, 10]),
            _leg("wait", "02:01:30", "02:03:20", [10, 12]),
            _leg("transit", "02:03:20", "02:05:00", [12, 15]),
        ],
        "coordinates": coordinates,
        "offsets_s": offsets,
    }


def _leg(mode: str, start: str, end: str, point_range: list[int]) -> dict[str, object]:
    return {
        "mode": mode,
        "start_time": f"2026-11-08T{start}+01:00",
        "end_time": f"2026-11-08T{end}+01:00",
        "from_stop": "A",
        "to_stop": "B",
        "gtfs_trip_id": None,
        "point_range": point_range,
    }


class SimplifyTrajectoryTest(unittest.TestCase):
    def test_drops_aligned_points_at_constant_speed(self) -> None:
        xy = np.column_stack((np.arange(10.0) * 10, np.zeros(10)))
        keep = simplify_trajectory(xy, np.arange(10.0), tolerance_m=1.0)
        self.assertEqual(np.flatnonzero(keep).tolist(), [0, 9])

    def test_keeps_a_stop_on_a_straight_line(self) -> None:
        # Same straight path, but the walker stands still for 60 s at x = 50 m.
        xy = np.array([[0.0, 0.0], [50.0, 0.0], [50.0, 0.0], [100.0, 0.0]])
        keep = simplify_trajectory(xy, np.array([0.0, 50.0, 110.0, 160.0]), tolerance_m=5.0)
        self.assertTrue(keep[1] and keep[2])

    def test_keeps_a_corner_beyond_the_tolerance(self) -> None:
        xy = np.array([[0.0, 0.0], [50.0, 30.0], [100.0, 0.0]])
        offsets = np.array([0.0, 1.0, 2.0])
        self.assertTrue(simplify_trajectory(xy, offsets, tolerance_m=10.0)[1])
        self.assertFalse(simplify_trajectory(xy, offsets, tolerance_m=40.0)[1])

    def test_handles_tiny_inputs(self) -> None:
        self.assertEqual(simplify_trajectory(np.zeros((0, 2)), np.zeros(0), 1.0).tolist(), [])
        self.assertEqual(simplify_trajectory(np.zeros((1, 2)), np.zeros(1), 1.0).tolist(), [True])


class OptimizeDocumentTest(unittest.TestCase):
    def test_simplifies_each_leg_and_remaps_point_ranges(self) -> None:
        payload = {**make_document_payload(), "journeys": [straight_walk_journey()]}
        document = ScenarioDocument.model_validate(payload)
        journey = optimize_document(document, tolerance_m=2.0).journeys[0]
        self.assertEqual([leg.point_range for leg in journey.legs], [(0, 2), (2, 4), (4, 7)])
        self.assertEqual(journey.coordinates[:2], [(2.35, 48.85), (2.3509, 48.85)])
        self.assertEqual(journey.offsets_s, [0.0, 90.0, 100.0, 200.0, 260.0, 270.0, 300.0])
        self.assertEqual(journey.destination.population, 1200)
        self.assertEqual(journey.end_time, document.journeys[0].end_time)

    def test_zero_tolerance_keeps_every_distinct_point(self) -> None:
        document = ScenarioDocument.model_validate(make_document_payload())
        self.assertEqual(optimize_document(document, tolerance_m=0.0), document)

    def test_rejects_invalid_tolerances(self) -> None:
        document = ScenarioDocument.model_validate(make_document_payload())
        for tolerance in (-1.0, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                optimize_document(document, tolerance)


class OptimizeDirectoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        payload = {**make_document_payload(), "journeys": [straight_walk_journey()]}
        self.source = write_document(self.directory, "Test-Scenario", json.dumps(payload))
        self.target = self.source.with_name(OPTIMIZED_FILENAME)

    def test_writes_a_valid_lighter_file_then_skips_it_while_up_to_date(self) -> None:
        [result] = optimize_directory(self.directory, tolerance_m=2.0)
        self.assertEqual((result.status, result.points_before, result.points_after), ("optimized", 15, 7))
        optimized = ScenarioDocument.model_validate_json(self.target.read_bytes())
        self.assertEqual(len(optimized.journeys[0].coordinates), 7)
        self.assertEqual(optimize_directory(self.directory)[0].status, "up to date")
        self.assertEqual(optimize_directory(self.directory, force=True)[0].status, "optimized")

    def test_regenerates_when_the_pipeline_file_is_newer(self) -> None:
        optimize_directory(self.directory)
        newer = self.target.stat().st_mtime_ns + 1_000_000_000
        os.utime(self.source, ns=(newer, newer))
        self.assertEqual(optimize_directory(self.directory)[0].status, "optimized")

    def test_invalid_source_and_missing_directory_are_reported(self) -> None:
        with self.assertRaises(OptimizationError):
            optimize_directory(self.directory / "missing")
        self.source.write_text("{}", encoding="utf-8")
        with self.assertRaises(OptimizationError):
            optimize_directory(self.directory)
        self.assertFalse(self.target.exists())

    def test_command_line_reports_failures_with_an_exit_code(self) -> None:
        self.assertEqual(main(["--directory", str(self.directory)]), 0)
        self.assertEqual(main(["--directory", str(self.directory / "missing")]), 1)
        self.assertEqual(main(["--directory", str(self.directory), "--tolerance-m", "-1"]), 1)

    def test_repository_prefers_the_up_to_date_optimized_file(self) -> None:
        optimize_directory(self.directory, tolerance_m=2.0)
        scenario = ScenarioRepository(self.directory).get_scenario("Test-Scenario")
        self.assertEqual(len(scenario.journeys[0].coordinates), 7)

        newer = self.target.stat().st_mtime_ns + 1_000_000_000
        os.utime(self.source, ns=(newer, newer))
        with self.assertLogs("routing.repository", level="WARNING"):
            scenario = ScenarioRepository(self.directory).get_scenario("Test-Scenario")
        self.assertEqual(len(scenario.journeys[0].coordinates), 15)

    def test_repository_serves_an_optimized_file_without_its_source(self) -> None:
        optimize_directory(self.directory, tolerance_m=2.0)
        self.source.unlink()
        repository = ScenarioRepository(self.directory)
        self.assertEqual([summary.id for summary in repository.list_scenarios()], ["Test-Scenario"])
        self.assertEqual(repository.list_scenarios()[0].journey_count, 1)


if __name__ == "__main__":
    unittest.main()
