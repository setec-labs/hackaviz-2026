"""Launch the project services locally (routing, safety and the frontend dev server).

Usage, from the repository root:

    uv run python scripts/run_services.py
    uv run python scripts/run_services.py --only safety frontend --reload

Before starting routing, the scenario files are optimized (`optimize-scenarios`, a no-op when
they are up to date); use --skip-optimize to bypass it. Every service output is prefixed with its name. Ctrl+C stops all services; if one
service exits, the others are stopped too.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
SERVICE_NAMES = ("routing", "safety", "frontend")
PYTHON_SERVICES = {"routing": 8001, "safety": 8002}
FRONTEND_PORT = 5173
STOP_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class ServiceSpec:
    """Command, working directory and URL for a local service."""

    name: str
    command: list[str]
    cwd: Path
    url: str


class LaunchError(RuntimeError):
    """Raised when a service cannot be launched (missing tool or dependencies)."""


def build_specs(names: Sequence[str], reload: bool, uv: str, npm: str) -> list[ServiceSpec]:
    """Build service commands in the canonical launch order.

    Args:
        names: Selected service names.
        reload: Whether Python services should reload on code changes.
        uv: Path or command name for uv.
        npm: Path or command name for npm.

    Returns:
        A specification for each selected, recognized service.
    """
    specs: list[ServiceSpec] = []
    for name in SERVICE_NAMES:
        if name not in names:
            continue
        if name in PYTHON_SERVICES:
            port = PYTHON_SERVICES[name]
            command = [uv, "run", "--package", name, "uvicorn", f"{name}.main:app", "--port", str(port)]
            if reload:
                command.append("--reload")
            specs.append(ServiceSpec(name, command, REPO_ROOT, f"http://localhost:{port}/docs"))
        else:
            command = [npm, "run", "dev", "--", "--port", str(FRONTEND_PORT), "--strictPort"]
            specs.append(ServiceSpec(name, command, FRONTEND_DIR, f"http://localhost:{FRONTEND_PORT}"))
    return specs


def build_prepare_command(names: Sequence[str], uv: str) -> list[str] | None:
    """Return the scenario optimization command when routing is selected."""
    if "routing" not in names:
        return None
    return [uv, "run", "--package", "routing", "optimize-scenarios"]


def find_executable(name: str) -> str:
    """Find an executable on PATH.

    Raises:
        LaunchError: The executable cannot be found.
    """
    path = shutil.which(name)
    if path is None:
        raise LaunchError(f"'{name}' was not found in PATH.")
    return path


def check_prerequisites(specs: Sequence[ServiceSpec], frontend_dir: Path = FRONTEND_DIR) -> None:
    """Check that frontend dependencies exist when the frontend is selected.

    Raises:
        LaunchError: The frontend's ``node_modules`` directory is missing.
    """
    if any(spec.name == "frontend" for spec in specs) and not (frontend_dir / "node_modules").is_dir():
        raise LaunchError("Frontend dependencies are missing: run 'npm install' in the frontend folder.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the service launcher options."""
    parser = argparse.ArgumentParser(description="Launch the Noctambulle services locally.")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=SERVICE_NAMES,
        default=list(SERVICE_NAMES),
        metavar="SERVICE",
        help=f"services to launch among {', '.join(SERVICE_NAMES)} (default: all)",
    )
    parser.add_argument("--reload", action="store_true", help="restart the Python services on code changes")
    parser.add_argument(
        "--skip-optimize", action="store_true", help="do not refresh the optimized scenario files before routing"
    )
    return parser.parse_args(argv)


class ServiceRunner:
    """Start selected services, forward output and stop their process trees."""

    def __init__(self, specs: Sequence[ServiceSpec]) -> None:
        self._specs = list(specs)
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._threads: list[threading.Thread] = []
        self._print_lock = threading.Lock()
        self._label_width = max(len(spec.name) for spec in self._specs)

    def log(self, name: str, message: str) -> None:
        """Print a service-prefixed message without interleaving output."""
        with self._print_lock:
            print(f"[{name.ljust(self._label_width)}] {message}", flush=True)

    def start(self) -> None:
        """Start all service processes and forward their combined output."""
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        for spec in self._specs:
            self.log(spec.name, f"starting on {spec.url}")
            process = subprocess.Popen(
                spec.command,
                cwd=spec.cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                # A separate process group lets us stop the whole tree (uv -> uvicorn, npm -> vite).
                start_new_session=os.name != "nt",
            )
            self._processes[spec.name] = process
            thread = threading.Thread(target=self._forward_output, args=(spec.name, process), daemon=True)
            thread.start()
            self._threads.append(thread)

    def _forward_output(self, name: str, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.log(name, line.rstrip())

    def wait_for_first_exit(self) -> tuple[str, int]:
        """Wait for a service to exit and return its name and exit code."""
        while True:
            for name, process in self._processes.items():
                code = process.poll()
                if code is not None:
                    return name, code
            time.sleep(0.5)

    def stop(self) -> None:
        """Stop all running service trees, escalating after the timeout."""
        for name, process in self._processes.items():
            if process.poll() is None:
                self.log(name, "stopping")
                _terminate_tree(process)
        deadline = time.monotonic() + STOP_TIMEOUT_SECONDS
        for process in self._processes.values():
            try:
                process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                _kill_tree(process)
                process.wait()
        for thread in self._threads:
            thread.join(timeout=1.0)


def _terminate_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        _kill_tree(process)
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def _kill_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare scenarios, run the selected services and return an exit status."""
    # Child output may contain characters the console encoding cannot represent (e.g. cp1252).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = parse_args(argv)
    try:
        uv = find_executable("uv") if set(args.only) & PYTHON_SERVICES.keys() else "uv"
        npm = find_executable("npm") if "frontend" in args.only else "npm"
        specs = build_specs(args.only, args.reload, uv, npm)
        check_prerequisites(specs)
    except LaunchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    prepare = None if args.skip_optimize else build_prepare_command(args.only, uv)
    if prepare is not None:
        print("[prepare] optimizing routing scenarios (no-op when up to date)", flush=True)
        if subprocess.run(prepare, cwd=REPO_ROOT, check=False).returncode != 0:
            # The routing API falls back to the raw pipeline files, only slower.
            print("[prepare] scenario optimization failed: routing will read the raw files", file=sys.stderr)

    runner = ServiceRunner(specs)
    exit_code = 0
    try:
        runner.start()
        name, code = runner.wait_for_first_exit()
        runner.log(name, f"exited with code {code}, stopping the other services")
        exit_code = code or 1
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
