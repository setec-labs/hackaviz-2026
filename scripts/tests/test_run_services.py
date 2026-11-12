import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_services  # noqa: E402


class BuildSpecsTest(unittest.TestCase):
    def test_builds_all_services_in_canonical_order(self) -> None:
        specs = run_services.build_specs(["frontend", "safety", "routing"], reload=False, uv="uv", npm="npm")

        self.assertEqual([spec.name for spec in specs], ["routing", "safety", "frontend"])
        self.assertEqual(
            specs[0].command,
            ["uv", "run", "--package", "routing", "uvicorn", "routing.main:app", "--port", "8001"],
        )
        self.assertEqual(
            specs[1].command,
            ["uv", "run", "--package", "safety", "uvicorn", "safety.main:app", "--port", "8002"],
        )
        self.assertEqual(specs[2].command, ["npm", "run", "dev", "--", "--port", "5173", "--strictPort"])
        self.assertEqual(specs[0].cwd, run_services.REPO_ROOT)
        self.assertEqual(specs[2].cwd, run_services.FRONTEND_DIR)

    def test_reload_only_applies_to_python_services(self) -> None:
        specs = run_services.build_specs(run_services.SERVICE_NAMES, reload=True, uv="uv", npm="npm")

        self.assertEqual(specs[0].command[-1], "--reload")
        self.assertEqual(specs[1].command[-1], "--reload")
        self.assertNotIn("--reload", specs[2].command)

    def test_uses_resolved_executables(self) -> None:
        specs = run_services.build_specs(["safety", "frontend"], reload=False, uv="/bin/uv", npm="C:/npm.cmd")

        self.assertEqual(specs[0].command[0], "/bin/uv")
        self.assertEqual(specs[1].command[0], "C:/npm.cmd")


class ParseArgsTest(unittest.TestCase):
    def test_defaults_to_all_services(self) -> None:
        args = run_services.parse_args([])

        self.assertEqual(args.only, list(run_services.SERVICE_NAMES))
        self.assertFalse(args.reload)

    def test_selects_services(self) -> None:
        args = run_services.parse_args(["--only", "safety", "frontend", "--reload"])

        self.assertEqual(args.only, ["safety", "frontend"])
        self.assertTrue(args.reload)

    def test_rejects_unknown_service(self) -> None:
        with self.assertRaises(SystemExit):
            run_services.parse_args(["--only", "unknown"])


class PrerequisitesTest(unittest.TestCase):
    def test_requires_frontend_dependencies(self) -> None:
        specs = run_services.build_specs(["frontend"], reload=False, uv="uv", npm="npm")
        with tempfile.TemporaryDirectory() as directory:
            frontend_dir = Path(directory)
            with self.assertRaisesRegex(run_services.LaunchError, "npm install"):
                run_services.check_prerequisites(specs, frontend_dir)

            (frontend_dir / "node_modules").mkdir()
            run_services.check_prerequisites(specs, frontend_dir)

    def test_python_services_do_not_need_node_modules(self) -> None:
        specs = run_services.build_specs(["safety"], reload=False, uv="uv", npm="npm")
        with tempfile.TemporaryDirectory() as directory:
            run_services.check_prerequisites(specs, Path(directory))

    def test_missing_executable_raises_launch_error(self) -> None:
        with self.assertRaises(run_services.LaunchError):
            run_services.find_executable("hackaviz-missing-tool")


if __name__ == "__main__":
    unittest.main()
