import time
import unittest
from pathlib import Path

from routing.repository import JOURNEYS_FILENAME, ScenarioRepository


PIPELINE_SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "data" / "output" / "scenarios"
LFS_POINTER_PREFIX = b"version https://git-lfs"


def pipeline_outputs_available() -> bool:
    """False when the directory is missing or holds Git LFS pointers (e.g. CI without `git lfs pull`)."""
    files = list(PIPELINE_SCENARIOS_DIR.glob(f"*/{JOURNEYS_FILENAME}"))
    if not files:
        return False
    for path in files:
        with path.open("rb") as handle:
            if handle.read(len(LFS_POINTER_PREFIX)) == LFS_POINTER_PREFIX:
                return False
    return True


@unittest.skipUnless(pipeline_outputs_available(), "Pipeline scenario outputs are not available (run git lfs pull)")
class PipelineScenarioDataTests(unittest.TestCase):
    """Validate the pipeline outputs so invalid files are caught before serving them."""

    def test_every_pipeline_scenario_is_valid(self) -> None:
        repository = ScenarioRepository(PIPELINE_SCENARIOS_DIR)
        started = time.perf_counter()
        summaries = repository.list_scenarios()
        elapsed = time.perf_counter() - started
        self.assertEqual(
            [summary.id for summary in summaries],
            sorted(path.parent.name for path in PIPELINE_SCENARIOS_DIR.glob(f"*/{JOURNEYS_FILENAME}")),
        )
        self.assertLess(elapsed, 10.0)
        for summary in summaries:
            with self.subTest(scenario=summary.id):
                scenario = repository.get_scenario(summary.id)
                self.assertEqual(scenario.journey_count, len(scenario.journeys))


if __name__ == "__main__":
    unittest.main()
