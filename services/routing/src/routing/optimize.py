"""Derive lighter `journeys.min.json` files from the pipeline's `journeys.json` outputs.

The pipeline keeps every street-network vertex (~2 million points per scenario, one every ~5 m),
far more than the map can show. Each leg is simplified with a time-aware Douglas-Peucker: a vertex
is dropped only if the position interpolated at its own timestamp stays within the tolerance, so
stops and speed changes survive. The output follows the same `ScenarioDocument` contract and is
validated before being written; the pipeline files are never modified.

Usage, from the repository root (re-run whenever the pipeline regenerates scenarios):

    uv run --package routing optimize-scenarios
    uv run --package routing optimize-scenarios --tolerance-m 5 --force
"""

import argparse
import logging
import math
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from hackaviz_2026.routing import Journey, JourneyLeg, ScenarioDocument

logger = logging.getLogger(__name__)

SOURCE_FILENAME = "journeys.json"
OPTIMIZED_FILENAME = "journeys.min.json"
DEFAULT_TOLERANCE_M = 10.0
DEFAULT_SCENARIOS_DIR = Path("data") / "output" / "scenarios"
_METRES_PER_DEGREE_LAT = 110_540.0
_METRES_PER_DEGREE_LON_AT_EQUATOR = 111_320.0


class OptimizationError(RuntimeError):
    """A scenario could not be read or the scenario directory is unavailable."""


@dataclass(frozen=True)
class OptimizationResult:
    """Status and point counts for one scenario optimization."""

    scenario_id: str
    status: str
    points_before: int = 0
    points_after: int = 0


def is_up_to_date(source: Path, optimized: Path) -> bool:
    """Return whether both files exist and the optimized file is not older."""
    try:
        return optimized.stat().st_mtime_ns >= source.stat().st_mtime_ns
    except FileNotFoundError:
        return False


def simplify_trajectory(xy: np.ndarray, offsets: np.ndarray, tolerance_m: float) -> np.ndarray:
    """Select vertices using time-aware Douglas-Peucker simplification.

    A vertex's error is its distance from the position interpolated at its
    timestamp between retained neighbors.

    Args:
        xy: Vertex coordinates in metres.
        offsets: Vertex timestamps in seconds.
        tolerance_m: Maximum interpolation error in metres.

    Returns:
        Boolean mask of retained vertices, including the first and last when
        the input is nonempty.
    """
    count = len(xy)
    keep = np.zeros(count, dtype=bool)
    if count == 0:
        return keep
    keep[0] = keep[-1] = True
    stack = [(0, count - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        duration = offsets[last] - offsets[first]
        inner = slice(first + 1, last)
        if duration > 0:
            fraction = (offsets[inner] - offsets[first]) / duration
        else:
            fraction = np.zeros(last - first - 1)
        expected = xy[first] + np.outer(fraction, xy[last] - xy[first])
        errors = np.hypot(*(xy[inner] - expected).T)
        worst = int(np.argmax(errors))
        if errors[worst] > tolerance_m:
            middle = first + 1 + worst
            keep[middle] = True
            stack.append((first, middle))
            stack.append((middle, last))
    return keep


def simplify_journey(journey: Journey, tolerance_m: float) -> Journey:
    """Simplify each leg separately, preserving leg boundaries and point ranges.

    Args:
        journey: Validated journey to simplify.
        tolerance_m: Maximum temporal interpolation error in metres.

    Returns:
        A validated journey with remapped point ranges and retained offsets.
    """
    coordinates = np.asarray(journey.coordinates, dtype=float)
    offsets = np.asarray(journey.offsets_s, dtype=float)
    lon_scale = _METRES_PER_DEGREE_LON_AT_EQUATOR * math.cos(math.radians(float(coordinates[0, 1])))
    xy = np.column_stack((coordinates[:, 0] * lon_scale, coordinates[:, 1] * _METRES_PER_DEGREE_LAT))
    keep = np.zeros(len(coordinates), dtype=bool)
    for leg in journey.legs:
        start, end = leg.point_range
        keep[start:end] = simplify_trajectory(xy[start:end], offsets[start:end], tolerance_m)
    new_index = np.concatenate(([0], np.cumsum(keep)))
    legs = [
        JourneyLeg.model_validate(
            {**leg.model_dump(), "point_range": (int(new_index[leg.point_range[0]]), int(new_index[leg.point_range[1]]))}
        )
        for leg in journey.legs
    ]
    kept = np.flatnonzero(keep)
    return Journey.model_validate(
        {
            **journey.model_dump(exclude={"legs", "coordinates", "offsets_s"}),
            "legs": legs,
            "coordinates": [journey.coordinates[index] for index in kept],
            "offsets_s": [journey.offsets_s[index] for index in kept],
        }
    )


def _check_tolerance(tolerance_m: float) -> None:
    if not math.isfinite(tolerance_m) or tolerance_m < 0:
        raise ValueError("tolerance_m must be a finite, non-negative distance")


def optimize_document(document: ScenarioDocument, tolerance_m: float = DEFAULT_TOLERANCE_M) -> ScenarioDocument:
    """Simplify all journeys and validate the resulting scenario document.

    Raises:
        ValueError: The tolerance is negative or nonfinite.
    """
    _check_tolerance(tolerance_m)
    journeys = [simplify_journey(journey, tolerance_m) for journey in document.journeys]
    return ScenarioDocument.model_validate({**document.model_dump(exclude={"journeys"}), "journeys": journeys})


def optimize_file(source: Path, target: Path, tolerance_m: float = DEFAULT_TOLERANCE_M) -> tuple[int, int]:
    """Validate, simplify and atomically write a scenario to the target.

    Args:
        source: Original scenario JSON file.
        target: Destination for the optimized JSON file.
        tolerance_m: Maximum temporal interpolation error in metres.

    Returns:
        The total point counts before and after simplification.

    Raises:
        OptimizationError: The source cannot be read or validated.
        ValueError: The tolerance is negative or nonfinite.
    """
    try:
        document = ScenarioDocument.model_validate_json(source.read_bytes())
    except (OSError, ValidationError) as exc:
        raise OptimizationError(f"Cannot read a valid scenario from {source}") from exc
    optimized = optimize_document(document, tolerance_m)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(optimized.model_dump_json(), encoding="utf-8")
    os.replace(temporary, target)
    points = sum(len(journey.coordinates) for journey in document.journeys)
    return points, sum(len(journey.coordinates) for journey in optimized.journeys)


def optimize_directory(
    directory: Path, tolerance_m: float = DEFAULT_TOLERANCE_M, force: bool = False
) -> list[OptimizationResult]:
    """Optimize scenario files in subdirectories, skipping current outputs by default.

    Args:
        directory: Root containing scenario directories.
        tolerance_m: Maximum temporal interpolation error in metres.
        force: Rebuild outputs even when they are up to date.

    Returns:
        Results in scenario folder order.

    Raises:
        OptimizationError: The directory or a scenario cannot be read.
        ValueError: The tolerance is negative or nonfinite.
    """
    if not directory.is_dir():
        raise OptimizationError(f"Scenario directory is unavailable: {directory}")
    _check_tolerance(tolerance_m)
    results = []
    for folder in sorted(entry for entry in directory.iterdir() if entry.is_dir()):
        source = folder / SOURCE_FILENAME
        target = folder / OPTIMIZED_FILENAME
        if not source.is_file():
            continue
        if not force and is_up_to_date(source, target):
            results.append(OptimizationResult(folder.name, "up to date"))
            continue
        before, after = optimize_file(source, target, tolerance_m)
        results.append(OptimizationResult(folder.name, "optimized", before, after))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    """Run the optimization CLI and return a process exit status."""
    parser = argparse.ArgumentParser(description="Write simplified journeys.min.json next to each journeys.json.")
    parser.add_argument("--directory", type=Path, default=DEFAULT_SCENARIOS_DIR)
    parser.add_argument("--tolerance-m", type=float, default=DEFAULT_TOLERANCE_M)
    parser.add_argument("--force", action="store_true", help="Rebuild even when the optimized file is up to date.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()
    try:
        results = optimize_directory(args.directory, args.tolerance_m, args.force)
    except (OptimizationError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    for result in results:
        if result.status == "optimized":
            ratio = result.points_after / result.points_before if result.points_before else 0.0
            logger.info(
                "%s: %d -> %d points (%.0f %%)", result.scenario_id, result.points_before, result.points_after, 100 * ratio
            )
        else:
            logger.info("%s: %s", result.scenario_id, result.status)
    logger.info("%d scenario(s) checked in %.1f s", len(results), time.perf_counter() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
