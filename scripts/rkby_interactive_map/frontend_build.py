"""Builds `frontend/interactive-map/` via pnpm, every run, before any
`RKBY_DATA_DIR` write (research.md §1, contracts/cli-and-env.md) -- so the
shipped bundle can never silently drift from `frontend/interactive-map/src/`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FrontendBuildError(Exception):
    """`pnpm` isn't on `PATH`, or `pnpm install`/`pnpm run build` failed."""


def build_frontend(frontend_dir: Path) -> None:
    if shutil.which("pnpm") is None:
        raise FrontendBuildError(
            "pnpm not found on PATH -- Node.js and pnpm are required to run "
            "this script (contracts/cli-and-env.md)"
        )

    install_result = subprocess.run(
        ["pnpm", "install", "--frozen-lockfile"],
        cwd=frontend_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if install_result.returncode != 0:
        raise FrontendBuildError(f"pnpm install failed:\n{install_result.stderr}")

    build_result = subprocess.run(
        ["pnpm", "run", "build"],
        cwd=frontend_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if build_result.returncode != 0:
        raise FrontendBuildError(f"pnpm run build failed:\n{build_result.stderr}")
