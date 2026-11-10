import unittest
from pathlib import Path

from routing.repository import ScenarioRepository


LOCAL_SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "data" / "routing" / "scenarios"


@unittest.skipUnless(LOCAL_SCENARIOS_DIR.is_dir(), "Local scenario data is not available")
class LocalScenarioDataTests(unittest.TestCase):
    """Validate the git-ignored local catalog so invalid files are caught before serving them."""

    def test_every_local_scenario_is_valid(self) -> None:
        repository = ScenarioRepository(LOCAL_SCENARIOS_DIR)
        summaries = repository.list_scenarios()
        self.assertEqual(
            [summary.id for summary in summaries],
            sorted(path.stem for path in LOCAL_SCENARIOS_DIR.glob("*.json")),
        )
        for summary in summaries:
            with self.subTest(scenario=summary.id):
                scenario = repository.get_scenario(summary.id)
                self.assertEqual(scenario.id, summary.id)


if __name__ == "__main__":
    unittest.main()
