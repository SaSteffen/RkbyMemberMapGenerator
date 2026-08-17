"""Generate the one combined, self-contained interactive photo map spanning
every season already scraped into a local, human-editable, git-backed data
store (see specs/003-interactive-photo-map/ for the full design).
Configuration is env-var only:

    RKBY_DATA_DIR  absolute path to the local, git-backed data repository

Also requires Node.js + pnpm on PATH -- this script builds
frontend/interactive-map/ itself, every run (contracts/cli-and-env.md).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.rkby_interactive_map.bundle import (
    assemble_map_data,
    copy_assets,
    generate_basemap,
)
from scripts.rkby_interactive_map.frontend_build import (
    FrontendBuildError,
    build_frontend,
)
from scripts.rkby_interactive_map.merge import merge_seasons
from scripts.rkby_records import auto_commit, discover_seasons, setup_run_logger

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "interactive-map"

_GITIGNORE_ENTRIES = ("interactive_map/",)


class ConfigError(Exception):
    """A required environment variable is missing or invalid."""


@dataclass(frozen=True)
class Config:
    data_dir: Path


def load_config() -> Config:
    """Validate all required env vars are present and usable before any
    network request or file write (mirrors generate_member_maps.load_config)."""
    raw_data_dir = os.environ.get("RKBY_DATA_DIR")
    if not raw_data_dir:
        raise ConfigError("Missing required environment variable: RKBY_DATA_DIR")

    data_dir = Path(raw_data_dir)
    if not data_dir.is_dir():
        raise ConfigError(
            f"RKBY_DATA_DIR does not exist or is not a directory: {data_dir}"
        )

    return Config(data_dir=data_dir)


# --- CLI arg parsing (contracts/cli-and-env.md, FR-002) -------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    """No flags at all (FR-002) -- unlike generate_member_maps.py's two
    tuning flags, this script has exactly one artifact and one behavior:
    every season under RKBY_DATA_DIR is bundled into it, every run."""
    return argparse.ArgumentParser(
        description=(
            "Generate the one combined interactive photo map spanning every "
            "season in RKBY_DATA_DIR."
        )
    )


# --- Output-folder bootstrapping (data-model.md § Idempotency) ------------------


def _ensure_interactive_map_dir(data_dir: Path) -> Path:
    """Delete everything under `<data_dir>/interactive_map/` except `tiles/`
    if present, recreate the dir, and add an `interactive_map/` entry to
    `<data_dir>/.gitignore` if not already there. Called only after
    `build_frontend()` succeeds (contracts/cli-and-env.md: pnpm failures are
    checked before any RKBY_DATA_DIR write).

    `tiles/` (the stitched basemap chunk grid) is exempt from this wipe --
    it must never be deleted, and `generate_basemap` skips re-stitching any
    chunk file already on disk, so previously baked tiles survive every
    later run (data-model.md § Idempotency exception, tiles/)."""
    interactive_map_dir = data_dir / "interactive_map"
    if interactive_map_dir.exists():
        for entry in interactive_map_dir.iterdir():
            if entry.name == "tiles":
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    interactive_map_dir.mkdir(parents=True, exist_ok=True)

    gitignore_path = data_dir / ".gitignore"
    existing_lines = (
        gitignore_path.read_text().splitlines() if gitignore_path.exists() else []
    )
    missing_entries = [
        entry for entry in _GITIGNORE_ENTRIES if entry not in existing_lines
    ]
    if missing_entries:
        updated_lines = [*existing_lines, *missing_entries]
        gitignore_path.write_text("\n".join(updated_lines) + "\n")

    return interactive_map_dir


# --- CLI entrypoint --------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    build_arg_parser().parse_args(argv)  # FR-002: no flags accepted

    try:
        build_frontend(FRONTEND_DIR)
    except FrontendBuildError as exc:
        print(f"Frontend build failed: {exc}", file=sys.stderr)
        return 1

    interactive_map_dir = _ensure_interactive_map_dir(config.data_dir)

    seasons = discover_seasons(config.data_dir)
    loggers = {
        season_label: setup_run_logger(
            config.data_dir / "seasons" / season_label / "logs",
            logger_name=f"generate_interactive_map.{season_label}",
        )[0]
        for season_label in seasons
    }

    merged_members = merge_seasons(config.data_dir, seasons, loggers)

    assemble_map_data(config.data_dir, interactive_map_dir, seasons, merged_members)
    generate_basemap(
        interactive_map_dir, merged_members, config.data_dir / ".tile_cache"
    )
    copy_assets(
        config.data_dir,
        interactive_map_dir,
        merged_members,
        FRONTEND_DIR / "dist" / "index.html",
    )

    # Auto-commit (contracts/cli-and-env.md § Auto-commit behavior): newly-
    # cached lat/lon per season, plus the top-level .gitignore.
    # interactive_map/ itself is never staged (already gitignored).
    commit_logger = (
        next(iter(loggers.values()), None)
        or setup_run_logger(
            config.data_dir / "seasons" / ".generate_interactive_map_logs",
            logger_name="generate_interactive_map.commit",
        )[0]
    )
    commit_paths = [f"seasons/{label}/applicants" for label in seasons] + [".gitignore"]
    auto_commit(
        config.data_dir,
        commit_paths,
        "interactive map: cache newly-resolved coordinates",
        commit_logger,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
