"""Shared season/record I/O, extracted out of `scrape_applicants.py` (research.md
§10): both it and `generate_member_maps.py` need the exact same season-folder
layout, YAML load/validate, and record-write logic. Constitution Principle II
allows this once duplication is real, not anticipated -- see plan.md's Structure
Decision for why this lives here instead of being re-implemented per script."""

from __future__ import annotations

import datetime
import json
import logging
import re
import subprocess
import unicodedata
from pathlib import Path

import jsonschema
import yaml

SCHEMA_PATH = Path(__file__).parent / "schemas" / "applicant_record.schema.json"


# --- Season directory layout --------------------------------------------------


def season_dir(data_dir: Path, season_label: str) -> Path:
    return data_dir / "seasons" / season_label


def applicants_dir(data_dir: Path, season_label: str) -> Path:
    return season_dir(data_dir, season_label) / "applicants"


def photos_dir(data_dir: Path, season_label: str) -> Path:
    return season_dir(data_dir, season_label) / "photos"


def logs_dir(data_dir: Path, season_label: str) -> Path:
    return season_dir(data_dir, season_label) / "logs"


def discover_seasons(data_dir: Path) -> list[str]:
    """List every season under `<data_dir>/seasons/` that has an `applicants/`
    subfolder, sorted for determinism (needed only by the map generator, which
    processes every season in one run instead of taking a `--season` switch)."""
    seasons_root = data_dir / "seasons"
    if not seasons_root.is_dir():
        return []
    return sorted(
        entry.name
        for entry in seasons_root.iterdir()
        if entry.is_dir() and (entry / "applicants").is_dir()
    )


# --- Name normalization (FR-013) ----------------------------------------------

_WHITESPACE_OR_HYPHEN_RE = re.compile(r"[\s-]+")
_NON_ALNUM_HYPHEN_RE = re.compile(r"[^a-z0-9-]")


def normalize_name(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value.strip())
    ascii_only = stripped.encode("ascii", "ignore").decode("ascii").lower()
    hyphenated = _WHITESPACE_OR_HYPHEN_RE.sub("-", ascii_only)
    cleaned = _NON_ALNUM_HYPHEN_RE.sub("", hyphenated)
    return cleaned.strip("-")


# --- Schema validation (FR-017) ----------------------------------------------


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def validate_record(record: dict) -> None:
    schema = load_schema()
    jsonschema.validate(instance=record, schema=schema)


# --- Record read/write ---------------------------------------------------------


class InvalidExistingRecordError(Exception):
    """An existing persisted record failed schema validation (FR-017)."""


_RECORD_FIELD_ORDER = (
    "match_key",
    "first_name",
    "last_name",
    "address",
    "phone",
    "role",
    "birthday",
    "sex",
    "num_previous_seasons",
    "status",
    "excluded",
    "excluded_observed_at",
    "ignore",
    "photo",
    "latitude",
    "longitude",
)


def _dump_record_yaml(record: dict) -> str:
    # .get() rather than direct indexing: an existing record persisted before
    # an optional field (e.g. "role", "latitude") existed won't have that key
    # yet, and must still be re-dumpable without a separate migration step.
    ordered = {key: record.get(key) for key in _RECORD_FIELD_ORDER}
    header = (
        "# Validate against scripts/schemas/applicant_record.schema.json "
        "in the RkbyMemberMapGenerator repo.\n"
    )
    return header + yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True)


def load_existing_records(data_dir: Path, season_label: str) -> dict[str, dict]:
    """Load + schema-validate every persisted record for a season. Raises
    before any write happens if any existing file is invalid (FR-017) --
    callers must call this before touching any other file."""
    a_dir = applicants_dir(data_dir, season_label)
    if not a_dir.exists():
        return {}
    records: dict[str, dict] = {}
    for path in sorted(a_dir.glob("*.yaml")):
        record = yaml.safe_load(path.read_text())
        try:
            validate_record(record)
        except jsonschema.exceptions.ValidationError as exc:
            raise InvalidExistingRecordError(
                f"Existing record {path.name} failed schema validation: {exc.message}"
            ) from exc
        records[record["match_key"]] = record
    return records


# --- Run logging (FR-016) -----------------------------------------------------


def _ensure_logs_gitignored(season_directory: Path) -> None:
    """Every run creates a fresh timestamped log file (FR-016), including
    no-op re-runs. Without this, such a run would always leave a new
    untracked file behind, so `git status` (and, if logs/ were ever staged,
    a commit) would never be truly empty. logs/ is scoped to this feature's
    own season folder, so ignoring it here isn't "provisioning" the data
    repo, just this script managing output it alone owns."""
    gitignore_path = season_directory / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text("logs/\n")


def setup_run_logger(
    run_logs_dir: Path, logger_name: str = "scrape_applicants"
) -> tuple[logging.Logger, Path]:
    """Configure a per-run logger: WARNING+ to a timestamped file under
    run_logs_dir, INFO+ to the console."""
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    _ensure_logs_gitignored(run_logs_dir.parent)
    timestamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H%M%S")
    log_file = run_logs_dir / f"{timestamp}.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger, log_file


# --- Auto-commit local data-repo changes (research.md §12) --------------------


def _run_git(data_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(data_dir), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _is_git_work_tree(data_dir: Path) -> bool:
    result = _run_git(data_dir, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def auto_commit(
    data_dir: Path, paths: list[str], message: str, logger: logging.Logger
) -> None:
    """If `RKBY_DATA_DIR` is a git work tree, stage + commit the given paths
    (relative to data_dir, only those that currently exist). No-op if not a
    git repo, none of the paths exist, or nothing actually changed; a commit
    failure is logged as a warning and never raised -- the already-written
    data is valid regardless of whether the commit succeeds."""
    if not _is_git_work_tree(data_dir):
        return

    existing_paths = [path for path in paths if (data_dir / path).exists()]
    if not existing_paths:
        return

    add_result = _run_git(data_dir, "add", *existing_paths)
    if add_result.returncode != 0:
        logger.warning(
            "git add failed for %s: %s", existing_paths, add_result.stderr.strip()
        )
        return

    status_result = _run_git(data_dir, "status", "--porcelain", "--", *existing_paths)
    if not status_result.stdout.strip():
        return  # nothing staged -> no empty commit

    commit_result = _run_git(data_dir, "commit", "-m", message)
    if commit_result.returncode != 0:
        logger.warning("git commit failed: %s", commit_result.stderr.strip())
