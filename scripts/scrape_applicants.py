"""Scrape the Team Rynkeby intranet's applicant list for one season and merge
the result into a local, human-editable, git-backed data store.

See specs/001-scraper-persistence/ (spec.md, plan.md, research.md, data-model.md,
contracts/) for the full design. Configuration is env-var only (FR-002, FR-023):

    RKBY_INTRANET_USERNAME  intranet login username
    RKBY_INTRANET_PASSWORD  intranet login password
    RKBY_DATA_DIR           absolute path to the local, git-backed data repository
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import requests
import yaml
from bs4 import BeautifulSoup

SCHEMA_PATH = Path(__file__).parent / "schemas" / "applicant_record.schema.json"

BASE_URL = "https://intranet.team-rynkeby.com"
LOGIN_URL = f"{BASE_URL}/login"
APPLICANTS_URL = f"{BASE_URL}/team/applicants"
AJAX_URL = f"{BASE_URL}/Ajax/team_application_manager.php"

REQUIRED_ENV_VARS = (
    "RKBY_INTRANET_USERNAME",
    "RKBY_INTRANET_PASSWORD",
    "RKBY_DATA_DIR",
)


class ConfigError(Exception):
    """A required environment variable is missing or invalid."""


@dataclass(frozen=True)
class Config:
    username: str
    password: str
    data_dir: Path


def load_config() -> Config:
    """Validate all required env vars are present and usable before any
    network request or file write (FR-023)."""
    missing = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing:
        raise ConfigError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )

    username = os.environ["RKBY_INTRANET_USERNAME"]
    password = os.environ["RKBY_INTRANET_PASSWORD"]
    data_dir = Path(os.environ["RKBY_DATA_DIR"])

    if not data_dir.is_dir():
        raise ConfigError(
            f"RKBY_DATA_DIR does not exist or is not a directory: {data_dir}"
        )

    return Config(username=username, password=password, data_dir=data_dir)


# --- Season label handling (FR-022) -----------------------------------------

_SEASON_ARG_RE = re.compile(r"^(\d{4})[-/](\d{2})$")


def default_season_label(today: datetime.date) -> str:
    year = today.year
    if today.month <= 7:
        return f"{year - 1}-{year % 100:02d}"
    return f"{year}-{(year + 1) % 100:02d}"


def parse_season_arg(value: str) -> str:
    match = _SEASON_ARG_RE.match(value)
    if not match:
        raise ValueError(
            f"Invalid season format: {value!r}; expected YYYY-YY or YYYY/YY"
        )
    start_year, end_suffix = match.groups()
    return f"{start_year}-{end_suffix}"


# --- Name normalization / matching (FR-013) ----------------------------------

_WHITESPACE_OR_HYPHEN_RE = re.compile(r"[\s-]+")
_NON_ALNUM_HYPHEN_RE = re.compile(r"[^a-z0-9-]")


def normalize_name(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value.strip())
    ascii_only = stripped.encode("ascii", "ignore").decode("ascii").lower()
    hyphenated = _WHITESPACE_OR_HYPHEN_RE.sub("-", ascii_only)
    cleaned = _NON_ALNUM_HYPHEN_RE.sub("", hyphenated)
    return cleaned.strip("-")


def match_key(first_name: str, last_name: str) -> str:
    normalized_last = normalize_name(last_name)
    if not normalized_last:
        return normalize_name(first_name)
    return f"{normalize_name(first_name)}-{normalized_last}"


# --- Schema validation (FR-017) ----------------------------------------------


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def validate_record(record: dict) -> None:
    schema = load_schema()
    jsonschema.validate(instance=record, schema=schema)


# --- Season directory layout --------------------------------------------------


def season_dir(data_dir: Path, season_label: str) -> Path:
    return data_dir / "seasons" / season_label


def applicants_dir(data_dir: Path, season_label: str) -> Path:
    return season_dir(data_dir, season_label) / "applicants"


def photos_dir(data_dir: Path, season_label: str) -> Path:
    return season_dir(data_dir, season_label) / "photos"


def logs_dir(data_dir: Path, season_label: str) -> Path:
    return season_dir(data_dir, season_label) / "logs"


# --- Run logging (FR-016) -----------------------------------------------------


def _ensure_logs_gitignored(season_directory: Path) -> None:
    """Every run creates a fresh timestamped log file (FR-016), including
    no-op re-runs. Without this, such a run would always leave a new
    untracked file behind, so `git status` (and, if logs/ were ever staged,
    a commit) would never be truly empty -- breaking SC-002/quickstart
    Scenario 2. logs/ is scoped to this feature's own season folder, so
    ignoring it here isn't "provisioning" the data repo (out of scope per
    spec Assumptions), just this script managing output it alone owns."""
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


# --- Intranet client (US1: login, season resolution, page/photo fetch) -------


class AuthenticationError(Exception):
    """The intranet rejected the supplied credentials."""


class FetchError(Exception):
    """A page fetch failed or returned an unexpected shape."""


def _looks_like_login_page(html: str) -> bool:
    return 'id="loginusername"' in html


_TEAM_OPTION_RE = re.compile(
    r'id="team_group"[^>]*>.*?<option\s+value="(\d+)"', re.IGNORECASE | re.DOTALL
)
_SEASON_OPTION_RE = re.compile(
    r'get_season_data\((\d+)\);"\s*>\s*<input[^>]*?value="(\d+)"[^>]*>\s*<i></i>\s*([^<]*)',
    re.IGNORECASE,
)
_SEASON_LABEL_TEXT_RE = re.compile(r"Season\s+(\d{4})/(\d{2})")


def _parse_team_id(html: str) -> int:
    match = _TEAM_OPTION_RE.search(html)
    if not match:
        raise FetchError("Could not find the team selector on the applicants page")
    return int(match.group(1))


def _parse_season_map(html: str) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for _onclick_id, value_id, label_text in _SEASON_OPTION_RE.findall(html):
        label_match = _SEASON_LABEL_TEXT_RE.match(label_text.strip())
        if not label_match:
            continue
        start_year, end_suffix = label_match.groups()
        mapping[f"{start_year}-{end_suffix}"] = int(value_id)
    return mapping


class IntranetClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def login(self, username: str, password: str) -> None:
        response = self.session.post(
            LOGIN_URL,
            data={
                "loginusername": username,
                "loginpassword": password,
                "UseMd5": "UseMd5",
                "dologinnoredirect": "dologinnoredirect",
                "dologin": "Login",
            },
            timeout=30,
        )
        response.raise_for_status()
        if _looks_like_login_page(response.text):
            raise AuthenticationError(
                "Login failed: the intranet rejected the supplied credentials"
            )

    def resolve_season(self, season_label: str) -> tuple[int, int]:
        response = self.session.get(APPLICANTS_URL, timeout=30)
        response.raise_for_status()
        team_id = _parse_team_id(response.text)
        season_map = _parse_season_map(response.text)
        if season_label not in season_map:
            raise FetchError(
                f"Season {season_label!r} was not found on the season selector page"
            )
        return team_id, season_map[season_label]

    def fetch_applicants_page(self, team_id: int, season_id: int, page: int) -> str:
        response = self.session.get(
            AJAX_URL,
            params={
                "tableSettings": "true",
                "teamid": team_id,
                "season": season_id,
                "filter_status": "",
                "page": page,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.text

    def fetch_photo_bytes(self, thumbnail_url: str) -> bytes:
        full_url = full_resolution_photo_url(thumbnail_url)
        response = self.session.get(BASE_URL + full_url, timeout=30)
        response.raise_for_status()
        return response.content


# --- Applicant row parsing (FR-001, FR-004, FR-005) ---------------------------

_BACKGROUND_URL_RE = re.compile(r"url\('([^']+)'\)")


def _split_name(name_text: str) -> tuple[str, str]:
    """Split one intranet Name cell into (first_name, last_name). Usually
    "First Last" -- split on the first space (research.md §15's documented
    limitation for multi-word first names still applies). Two shapes seen in
    practice break that: "Last,First" (comma, no space -- entered
    last-name-first) and a bare single name with no separator at all (no
    last name on file for that person)."""
    if "," in name_text:
        last_name, _, first_name = name_text.partition(",")
        return first_name.strip(), last_name.strip()
    first_name, _, last_name = name_text.partition(" ")
    return first_name, last_name


def _parse_status(status_cell) -> str:
    active_label = status_cell.find("label", class_="active")
    raw = (
        active_label.get_text(strip=True)
        if active_label
        else status_cell.get_text(strip=True)
    )
    lowered = raw.strip().lower()
    if lowered == "yes" or "approved" in lowered:
        return "yes"
    if lowered == "no" or "declined" in lowered:
        return "no"
    if lowered == "undecided":
        return "undecided"
    return lowered


def _parse_photo_thumbnail_url(image_cell) -> str | None:
    div = image_cell.find("div", class_="profile-image-list")
    if div is None:
        return None
    match = _BACKGROUND_URL_RE.search(div.get("style") or "")
    return match.group(1) if match else None


def full_resolution_photo_url(thumbnail_url: str | None) -> str | None:
    if thumbnail_url is None:
        return None
    return thumbnail_url.split("?", 1)[0]


def parse_applicant_rows(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="applicants") or soup.find("table")
    if table is None:
        return []
    thead = table.find("thead")
    headers = [th.get_text(strip=True) for th in thead.find_all("th")]
    tbody = table.find("tbody") or table

    rows: list[dict] = []
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) != len(headers):
            continue
        cell = dict(zip(headers, tds))

        name_text = cell["Name"].get_text(strip=True)
        first_name, last_name = _split_name(name_text)

        address_line = cell["Address"].get_text(strip=True)
        zip_code = cell["Zip"].get_text(strip=True)
        city = cell["City"].get_text(strip=True)
        country = cell["Country"].get_text(strip=True)
        zip_city = " ".join(part for part in (zip_code, city) if part)
        address = (
            ", ".join(part for part in (address_line, zip_city, country) if part)
            or None
        )

        rows.append(
            {
                "first_name": first_name,
                "last_name": last_name,
                "phone": cell["Phone"].get_text(strip=True) or None,
                "address": address,
                "birthday": None,  # not available on this view (research.md §15)
                "status": _parse_status(cell["Accept on teams"]),
                "photo_thumbnail_url": _parse_photo_thumbnail_url(cell["Image"]),
            }
        )
    return rows


def fetch_all_pages(client: IntranetClient, team_id: int, season_id: int) -> list[dict]:
    """Fetch + parse every page for a season. Network + parse only, no disk
    writes (research.md §10) -- any failure here propagates uncaught so the
    caller writes nothing (FR-018 all-or-nothing)."""
    all_rows: list[dict] = []
    seen_keys: set[str] = set()
    page = 0
    max_pages = 1000  # safety cap against a runaway loop, not a real limit
    while page < max_pages:
        html = client.fetch_applicants_page(team_id, season_id, page)
        page_rows = parse_applicant_rows(html)
        new_rows = [
            row
            for row in page_rows
            if match_key(row["first_name"], row["last_name"]) not in seen_keys
        ]
        if not new_rows:
            break
        for row in new_rows:
            seen_keys.add(match_key(row["first_name"], row["last_name"]))
            all_rows.append(row)
        page += 1
    return all_rows


_CONFLICT_FIELDS = ("address", "phone", "birthday")


def _conflicting_fields(a: dict, b: dict) -> list[str]:
    """Fields that are non-empty on both sides and disagree (research.md §9)."""
    return [
        field
        for field in _CONFLICT_FIELDS
        if a.get(field) and b.get(field) and a[field] != b[field]
    ]


def _merge_two_scraped_rows(a: dict, b: dict) -> dict:
    merged = dict(a)
    for field in (*_CONFLICT_FIELDS, "photo_thumbnail_url"):
        if not merged.get(field) and b.get(field):
            merged[field] = b[field]
    return merged


def deduplicate_scraped_rows(rows: list[dict], logger: logging.Logger) -> list[dict]:
    """Collapse same-person duplicates within one scrape (Story 5, FR-013).
    Consistent duplicates (no disagreement on a field both sides set) merge
    into one candidate; a meaningful conflict logs a warning and drops all
    of that person's rows from this run rather than guessing."""
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for row in rows:
        key = match_key(row["first_name"], row["last_name"])
        if key not in grouped:
            order.append(key)
        grouped.setdefault(key, []).append(row)

    result: list[dict] = []
    for key in order:
        candidates = grouped[key]
        if len(candidates) == 1:
            result.append(candidates[0])
            continue

        merged = candidates[0]
        conflict = False
        for other in candidates[1:]:
            if _conflicting_fields(merged, other):
                conflict = True
                break
            merged = _merge_two_scraped_rows(merged, other)

        if conflict:
            logger.warning(
                "Duplicate applicants for %s within this scrape have conflicting "
                "details; none persisted this run: %s",
                key,
                candidates,
            )
            continue
        result.append(merged)
    return result


def fetch_photo(
    client: IntranetClient,
    thumbnail_url: str | None,
    logger: logging.Logger,
    match_key_value: str,
) -> bytes | None:
    """Fetch one applicant's full-resolution photo. Never raises -- a failure
    is logged as a warning and retried on a later run (FR-005)."""
    if thumbnail_url is None:
        return None
    try:
        return client.fetch_photo_bytes(thumbnail_url)
    except Exception as exc:  # noqa: BLE001 - intentionally broad, see FR-005
        logger.warning("Photo fetch failed for %s: %s", match_key_value, exc)
        return None


# --- Persistence (US1 create + US2 merge/overwrite-protection, FR-009) --------


class InvalidExistingRecordError(Exception):
    """An existing persisted record failed schema validation (FR-017)."""


def _log_invalid_scraped_record(
    logger: logging.Logger,
    key: str,
    record: dict,
    exc: jsonschema.exceptions.ValidationError,
) -> None:
    """A freshly-scraped record failing schema validation means the scraper
    produced something the schema doesn't allow (e.g. an unusual name shape),
    not a hand-edit problem. Log the full offending record at ERROR (so it
    lands in the WARNING+ run-log file, not just the console) so the failure
    is diagnosable without having to reproduce it."""
    logger.error(
        "Applicant %s: scraped record failed schema validation at %s: %s; "
        "not persisted this run. Offending record: %s",
        key,
        list(exc.path),
        exc.message,
        record,
    )


_RECORD_FIELD_ORDER = (
    "match_key",
    "first_name",
    "last_name",
    "address",
    "phone",
    "birthday",
    "status",
    "excluded",
    "excluded_observed_at",
    "ignore",
    "photo",
)


def _guess_photo_extension(thumbnail_url: str | None) -> str:
    if not thumbnail_url:
        return ".jpg"
    suffix = Path(thumbnail_url.split("?", 1)[0]).suffix
    return suffix if suffix else ".jpg"


def _dump_record_yaml(record: dict) -> str:
    ordered = {key: record[key] for key in _RECORD_FIELD_ORDER}
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


def merge_record(existing: dict, scraped: dict) -> dict:
    """Fill-empty-only merge (FR-009): a field already holding a value is
    never overwritten by a new scrape; `status` is frozen at creation and
    never touched here. Returns a new dict; does not mutate `existing`."""
    merged = dict(existing)
    for field in ("address", "phone", "birthday"):
        if not merged.get(field) and scraped.get(field):
            merged[field] = scraped[field]
    return merged


def _photo_file_exists(photos_dir_path: Path, key: str) -> bool:
    return any(photos_dir_path.glob(f"{key}.*"))


def _fetch_photo_if_needed(
    record: dict,
    row: dict,
    client: IntranetClient,
    p_dir: Path,
    logger: logging.Logger,
    key: str,
) -> bool:
    """Fetch + write a photo into `record` (mutated in place) unless one is
    already recorded/on disk. Returns whether a new photo was fetched."""
    if record.get("photo") or _photo_file_exists(p_dir, key):
        return False
    photo_bytes = fetch_photo(client, row.get("photo_thumbnail_url"), logger, key)
    if photo_bytes is None:
        return False
    extension = _guess_photo_extension(row.get("photo_thumbnail_url"))
    (p_dir / f"{key}{extension}").write_bytes(photo_bytes)
    record["photo"] = f"photos/{key}{extension}"
    return True


def _now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat()


def persist_records(
    data_dir: Path,
    season_label: str,
    rows: list[dict],
    client: IntranetClient,
    logger: logging.Logger,
) -> dict:
    """Load existing records (US2), merge scraped rows into them
    (fill-empty-only, FR-009) or create genuinely new ones (US1), mark a
    status flip to "no" as excluded rather than deleting (FR-015), and write
    only what actually changed (SC-002 idempotency). A freshly-built record
    that fails schema validation (a scraper bug, not a hand-edit -- existing
    records are already validated by load_existing_records above) is logged
    with its full contents and skipped; it does not abort the rest of the
    run."""
    existing_records = load_existing_records(data_dir, season_label)

    a_dir = applicants_dir(data_dir, season_label)
    p_dir = photos_dir(data_dir, season_label)
    a_dir.mkdir(parents=True, exist_ok=True)
    p_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    updated = 0
    photos_fetched = 0
    excluded = 0
    validation_errors = 0

    for row in rows:
        key = match_key(row["first_name"], row["last_name"])
        existing = existing_records.get(key)

        if existing is not None and existing.get("ignore"):
            # FR-010/FR-011: a human-set ignore flag freezes the record
            # entirely -- no field writes, no photo fetch, no recreation.
            continue

        if existing is None:
            if row["status"] == "no":
                continue  # FR-003: never persist a never-before-seen "no"
            record = {
                "match_key": key,
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "address": row.get("address"),
                "phone": row.get("phone"),
                "birthday": row.get("birthday"),
                "status": row["status"],
                "excluded": False,
                "excluded_observed_at": None,
                "ignore": False,
                "photo": None,
            }
            try:
                validate_record(record)
            except jsonschema.exceptions.ValidationError as exc:
                _log_invalid_scraped_record(logger, key, record, exc)
                validation_errors += 1
                continue
            if _fetch_photo_if_needed(record, row, client, p_dir, logger, key):
                photos_fetched += 1
            (a_dir / f"{key}.yaml").write_text(_dump_record_yaml(record))
            created += 1
            continue

        if row["status"] == "no" and not existing.get("excluded"):
            # FR-015: mark excluded, leave every other field untouched --
            # no merge, no photo fetch, this run only records the flip.
            record = dict(existing)
            record["excluded"] = True
            record["excluded_observed_at"] = _now_iso()
            excluded += 1
            logger.warning(
                "Applicant %s now excluded: a later scrape observed status 'no'", key
            )
        else:
            conflicts = _conflicting_fields(existing, row)
            if conflicts:
                # FR-014: flag for human review; existing value(s) still win
                # via merge_record's fill-empty-only rule below.
                logger.warning(
                    "Applicant %s: scraped data conflicts with the existing "
                    "record on %s; existing value(s) kept, new snapshot: %s",
                    key,
                    conflicts,
                    row,
                )
            record = merge_record(existing, row)
            if _fetch_photo_if_needed(record, row, client, p_dir, logger, key):
                photos_fetched += 1

        if record != existing:
            try:
                validate_record(record)
            except jsonschema.exceptions.ValidationError as exc:
                _log_invalid_scraped_record(logger, key, record, exc)
                validation_errors += 1
                continue
            (a_dir / f"{key}.yaml").write_text(_dump_record_yaml(record))
            updated += 1
        # else: nothing changed for this record -> no write (SC-002)

    return {
        "created": created,
        "updated": updated,
        "photos_fetched": photos_fetched,
        "excluded": excluded,
        "validation_errors": validation_errors,
    }


# --- Auto-commit local data-repo changes (research.md §14) --------------------


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


def auto_commit_season(
    data_dir: Path, season_label: str, summary: dict, logger: logging.Logger
) -> None:
    """If `RKBY_DATA_DIR` is a git work tree, stage + commit the applicant
    data this run changed. No-op if not a git repo or nothing changed; a
    commit failure is logged as a warning and never raised -- the already
    -written season data is valid regardless of whether the commit succeeds.

    Deliberately scoped to applicants/ + photos/ (+ the season's own
    logs-ignoring .gitignore, committed once when first created), not
    logs/ itself: every run writes a fresh timestamped log file (FR-016)
    even when no applicant data changes, so including logs/ in the
    "anything staged?" check would make a true no-op re-run always produce
    a commit, breaking SC-002/quickstart Scenario 2's "identical HEAD, empty
    git status" guarantee. Log files are still written to disk every run;
    they're just not git-tracked by this step."""
    if not _is_git_work_tree(data_dir):
        return

    data_paths = [
        relative
        for relative in (
            f"seasons/{season_label}/applicants",
            f"seasons/{season_label}/photos",
            f"seasons/{season_label}/.gitignore",
        )
        if (data_dir / relative).exists()
    ]
    if not data_paths:
        return

    add_result = _run_git(data_dir, "add", *data_paths)
    if add_result.returncode != 0:
        logger.warning(
            "git add failed for %s: %s", data_paths, add_result.stderr.strip()
        )
        return

    status_result = _run_git(data_dir, "status", "--porcelain", "--", *data_paths)
    if not status_result.stdout.strip():
        return  # nothing staged -> no empty commit

    message = (
        f"scrape({season_label}): {summary['created']} new, "
        f"{summary['excluded']} excluded, {summary['photos_fetched']} photos fetched "
        f"— {_now_iso()}"
    )
    commit_result = _run_git(data_dir, "commit", "-m", message)
    if commit_result.returncode != 0:
        logger.warning("git commit failed: %s", commit_result.stderr.strip())


# --- CLI entrypoint ------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape the Team Rynkeby intranet's applicant list for one season."
    )
    parser.add_argument(
        "--season",
        help="Season to scrape, e.g. 2025-26 or 2025/26. Defaults based on today's date.",
    )
    return parser


def main(argv: list[str] | None = None, today: datetime.date | None = None) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    args = build_arg_parser().parse_args(argv)
    season_label = (
        parse_season_arg(args.season)
        if args.season
        else default_season_label(today or datetime.datetime.now().astimezone().date())
    )

    logger, _log_file = setup_run_logger(logs_dir(config.data_dir, season_label))

    client = IntranetClient()
    try:
        client.login(config.username, config.password)
        team_id, season_id = client.resolve_season(season_label)
        rows = fetch_all_pages(client, team_id, season_id)
    except (AuthenticationError, FetchError, requests.RequestException) as exc:
        logger.error("Run aborted before any data was written: %s", exc)
        return 1

    rows = deduplicate_scraped_rows(rows, logger)

    # "no"-status rows are not pre-filtered here: persist_records() itself
    # decides per-row (FR-003: never create from a "no"; FR-015: mark an
    # existing record excluded rather than dropping it).
    try:
        summary = persist_records(config.data_dir, season_label, rows, client, logger)
    except InvalidExistingRecordError as exc:
        logger.error("Run aborted, existing data left untouched: %s", exc)
        return 1

    logger.info(
        "Run complete for season %s: %d created, %d updated, %d excluded, "
        "%d photos fetched, %d validation errors",
        season_label,
        summary["created"],
        summary["updated"],
        summary["excluded"],
        summary["photos_fetched"],
        summary["validation_errors"],
    )

    auto_commit_season(config.data_dir, season_label, summary, logger)

    # Non-zero exit even though we didn't abort: some applicants were
    # silently skipped this run (already logged above with full details)
    # and need a human to look at the log, not just a clean-looking exit.
    return 1 if summary["validation_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
