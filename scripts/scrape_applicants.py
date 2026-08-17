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
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import requests
from bs4 import BeautifulSoup

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Several of these are only used elsewhere in this module (applicants_dir,
# etc.) -- others (load_schema, validate_record, load_existing_records,
# setup_run_logger, InvalidExistingRecordError) are re-exported here purely
# so this module's existing test suite keeps importing them from
# scripts.scrape_applicants unmodified.
from scripts.rkby_records import (  # noqa: F401
    InvalidExistingRecordError,
    _dump_record_yaml,
    applicants_dir,
    auto_commit,
    discover_seasons,
    load_existing_records,
    load_schema,
    logs_dir,
    normalize_name,
    photos_dir,
    setup_run_logger,
    validate_record,
)

BASE_URL = "https://intranet.team-rynkeby.com"
LOGIN_URL = f"{BASE_URL}/login"
APPLICANTS_URL = f"{BASE_URL}/team/applicants"
AJAX_URL = f"{BASE_URL}/Ajax/team_application_manager.php"
PARTICIPANT_URL = f"{BASE_URL}/Ajax/showparticipant.php"

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


# --- Name matching (FR-013) ---------------------------------------------------


def match_key(first_name: str, last_name: str) -> str:
    normalized_last = normalize_name(last_name)
    if not normalized_last:
        return normalize_name(first_name)
    return f"{normalize_name(first_name)}-{normalized_last}"


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

    def fetch_participant_detail(self, season_id: int, applicant_id: int) -> str:
        response = self.session.get(
            PARTICIPANT_URL,
            params={
                "season": season_id,
                "mplc": "/team/applicants",
                "userid": applicant_id,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.text


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


def _parse_applicant_id(status_cell) -> int | None:
    """The "Accept on teams" cell carries `<span class="iddata"
    data-id="...">` regardless of which status rendering it uses (research.md
    §15 revision) -- this is the `userid` the detail popup is fetched by."""
    span = status_cell.find("span", class_="iddata")
    if span is None:
        return None
    raw = span.get("data-id")
    return int(raw) if raw and raw.isdigit() else None


_BIRTHDAY_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")


def _parse_birthday(html: str) -> str | None:
    """Parse the `dd-mm-yyyy` birthday out of an applicant detail popup
    (`/Ajax/showparticipant.php`) into ISO 8601 (YYYY-MM-DD). Birthday is not
    present in the applicant list view itself, only here (research.md §15
    revision)."""
    soup = BeautifulSoup(html, "html.parser")
    el = soup.find("p", class_="profile_birthday")
    if el is None:
        return None
    match = _BIRTHDAY_RE.search(el.get_text())
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month}-{day}"


_SEX_RE = re.compile(r"Sex:\s*(\S+)")


def _parse_sex(html: str) -> str | None:
    """Parse the raw Sex text out of an applicant detail popup's Profile tab
    (`<p class="profile_sex">`), next to birthday. Not present in the
    applicant list view itself, only here."""
    soup = BeautifulSoup(html, "html.parser")
    el = soup.find("p", class_="profile_sex")
    if el is None:
        return None
    match = _SEX_RE.search(el.get_text())
    return match.group(1) if match else None


_PARTICIPATED_RE = re.compile(r"Participated:\s*(\d+)")


def _parse_num_previous_seasons(html: str) -> int | None:
    """Parse the "Participated: N times" count out of an applicant detail
    popup's "Team application" tab (`tabs-applications`). That tab reuses one
    `<p class="application-role">` class for several unrelated lines (Role,
    Participated, motivation text), so every such paragraph must be checked
    for the one carrying "Participated:" rather than selecting by class
    alone."""
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all("p", class_="application-role"):
        match = _PARTICIPATED_RE.search(el.get_text())
        if match:
            return int(match.group(1))
    return None


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
                "role": cell["Role"].get_text(strip=True) or None,
                "birthday": None,  # fetched later from the detail popup if needed
                "sex": None,  # ditto
                "num_previous_seasons": None,  # ditto
                "status": _parse_status(cell["Accept on teams"]),
                "photo_thumbnail_url": _parse_photo_thumbnail_url(cell["Image"]),
                "applicant_id": _parse_applicant_id(cell["Accept on teams"]),
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


_CONFLICT_FIELDS = ("address", "phone", "birthday", "role")


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


def fetch_participant_details(
    client: IntranetClient,
    season_id: int,
    applicant_id: int | None,
    logger: logging.Logger,
    match_key_value: str,
) -> dict | None:
    """Fetch one applicant's detail popup once and parse out every field it
    carries (birthday, sex, num_previous_seasons) instead of re-fetching the
    same popup once per field. Never raises -- a failure is logged as a
    warning and retried on a later run (mirrors fetch_photo's FR-005
    handling)."""
    if applicant_id is None:
        return None
    try:
        html = client.fetch_participant_detail(season_id, applicant_id)
    except Exception as exc:  # noqa: BLE001 - intentionally broad, see FR-005
        logger.warning("Detail fetch failed for %s: %s", match_key_value, exc)
        return None
    return {
        "birthday": _parse_birthday(html),
        "sex": _parse_sex(html),
        "num_previous_seasons": _parse_num_previous_seasons(html),
    }


# --- Persistence (US1 create + US2 merge/overwrite-protection, FR-009) --------


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


def _guess_photo_extension(thumbnail_url: str | None) -> str:
    if not thumbnail_url:
        return ".jpg"
    suffix = Path(thumbnail_url.split("?", 1)[0]).suffix
    return suffix if suffix else ".jpg"


def merge_record(existing: dict, scraped: dict) -> dict:
    """Fill-empty-only merge (FR-009): a field already holding a value is
    never overwritten by a new scrape; `status` is frozen at creation and
    never touched here. Returns a new dict; does not mutate `existing`."""
    merged = dict(existing)
    for field in ("address", "phone", "birthday", "role"):
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


def _fetch_participant_details_if_needed(
    record: dict,
    row: dict,
    client: IntranetClient,
    season_id: int,
    logger: logging.Logger,
    key: str,
) -> bool:
    """Fetch + fill birthday, sex, and num_previous_seasons into `record`
    (mutated in place) from a single detail-popup fetch, unless every one of
    them is already recorded. Each field is filled independently
    (fill-empty-only) so a popup missing one field doesn't block the others.
    num_previous_seasons is checked with `is None`, not truthiness -- 0 (a
    first-time applicant) is a real, meaningful observed value. Returns
    whether the popup was fetched."""
    needs_birthday = not record.get("birthday")
    needs_sex = not record.get("sex")
    needs_num_previous_seasons = record.get("num_previous_seasons") is None
    if not (needs_birthday or needs_sex or needs_num_previous_seasons):
        return False

    details = fetch_participant_details(
        client, season_id, row.get("applicant_id"), logger, key
    )
    if details is None:
        return False

    if needs_birthday and details["birthday"] is not None:
        record["birthday"] = details["birthday"]
    if needs_sex and details["sex"] is not None:
        record["sex"] = details["sex"]
    if needs_num_previous_seasons and details["num_previous_seasons"] is not None:
        record["num_previous_seasons"] = details["num_previous_seasons"]
    return True


def _now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat()


def persist_records(
    data_dir: Path,
    season_label: str,
    season_id: int,
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
    details_fetched = 0
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
                "role": row.get("role"),
                "birthday": row.get("birthday"),
                "sex": row.get("sex"),
                "num_previous_seasons": row.get("num_previous_seasons"),
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
            if _fetch_participant_details_if_needed(
                record, row, client, season_id, logger, key
            ):
                details_fetched += 1
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
                logger.debug(
                    "Applicant %s: scraped data conflicts with the existing "
                    "record on %s; existing value(s) kept, new snapshot: %s",
                    key,
                    conflicts,
                    row,
                )
            record = merge_record(existing, row)
            if _fetch_photo_if_needed(record, row, client, p_dir, logger, key):
                photos_fetched += 1
            if _fetch_participant_details_if_needed(
                record, row, client, season_id, logger, key
            ):
                details_fetched += 1

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
        "details_fetched": details_fetched,
        "excluded": excluded,
        "validation_errors": validation_errors,
    }


# --- Auto-commit local data-repo changes (research.md §12) --------------------


def auto_commit_season(
    data_dir: Path, season_label: str, summary: dict, logger: logging.Logger
) -> None:
    """Stage + commit the applicant data this run changed, via the shared
    `rkby_records.auto_commit` helper (research.md §10, §12).

    Deliberately scoped to applicants/ + photos/ (+ the season's own
    logs-ignoring .gitignore, committed once when first created), not
    logs/ itself: every run writes a fresh timestamped log file (FR-016)
    even when no applicant data changes, so including logs/ in the
    "anything staged?" check would make a true no-op re-run always produce
    a commit, breaking SC-002/quickstart Scenario 2's "identical HEAD, empty
    git status" guarantee. Log files are still written to disk every run;
    they're just not git-tracked by this step."""
    data_paths = [
        f"seasons/{season_label}/applicants",
        f"seasons/{season_label}/photos",
        f"seasons/{season_label}/.gitignore",
    ]
    message = (
        f"scrape({season_label}): {summary['created']} new, "
        f"{summary['excluded']} excluded, {summary['photos_fetched']} photos fetched "
        f"— {_now_iso()}"
    )
    auto_commit(data_dir, data_paths, message, logger)


# --- CLI entrypoint ------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape the Team Rynkeby intranet's applicant list for one season."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--season",
        help="Season to scrape, e.g. 2025-26 or 2025/26. Defaults based on today's date.",
    )
    group.add_argument(
        "--update-data",
        action="store_true",
        help=(
            "Re-scrape every season that already has data under RKBY_DATA_DIR, "
            "instead of a single --season. Shortcut for running this script once "
            "per existing season."
        ),
    )
    return parser


def _run_one_season(client: IntranetClient, data_dir: Path, season_label: str) -> int:
    """Scrape + persist one already-logged-in season, mirroring what a
    single-season `main()` run does from season resolution onward. Never
    raises -- a fetch/persist failure here is logged and turned into exit
    code 1 so a multi-season --update-data run keeps going onto the next
    season instead of aborting the whole batch."""
    logger, _log_file = setup_run_logger(logs_dir(data_dir, season_label))

    try:
        team_id, season_id = client.resolve_season(season_label)
        rows = fetch_all_pages(client, team_id, season_id)
    except (FetchError, requests.RequestException) as exc:
        logger.error("Run aborted before any data was written: %s", exc)
        return 1

    rows = deduplicate_scraped_rows(rows, logger)

    # "no"-status rows are not pre-filtered here: persist_records() itself
    # decides per-row (FR-003: never create from a "no"; FR-015: mark an
    # existing record excluded rather than dropping it).
    try:
        summary = persist_records(
            data_dir, season_label, season_id, rows, client, logger
        )
    except InvalidExistingRecordError as exc:
        logger.error("Run aborted, existing data left untouched: %s", exc)
        return 1

    logger.info(
        "Run complete for season %s: %d created, %d updated, %d excluded, "
        "%d photos fetched, %d applicant details fetched, %d validation errors",
        season_label,
        summary["created"],
        summary["updated"],
        summary["excluded"],
        summary["photos_fetched"],
        summary["details_fetched"],
        summary["validation_errors"],
    )

    auto_commit_season(data_dir, season_label, summary, logger)

    # Non-zero exit even though we didn't abort: some applicants were
    # silently skipped this run (already logged above with full details)
    # and need a human to look at the log, not just a clean-looking exit.
    return 1 if summary["validation_errors"] else 0


def main(argv: list[str] | None = None, today: datetime.date | None = None) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    args = build_arg_parser().parse_args(argv)

    if args.update_data:
        season_labels = discover_seasons(config.data_dir)
        if not season_labels:
            print(
                "No previously-scraped seasons found under RKBY_DATA_DIR; "
                "--update-data has nothing to do.",
                file=sys.stderr,
            )
            return 0
    else:
        season_labels = [
            parse_season_arg(args.season)
            if args.season
            else default_season_label(
                today or datetime.datetime.now().astimezone().date()
            )
        ]

    client = IntranetClient()
    try:
        client.login(config.username, config.password)
    except (AuthenticationError, requests.RequestException) as exc:
        # Login is shared across every season in this run -- if it fails,
        # every requested season's run would have failed the same way, so
        # log the abort to each season's own log (FR-016) rather than
        # picking one arbitrarily.
        for season_label in season_labels:
            logger, _log_file = setup_run_logger(
                logs_dir(config.data_dir, season_label)
            )
            logger.error("Run aborted before any data was written: %s", exc)
        return 1

    exit_code = 0
    for season_label in season_labels:
        exit_code = max(
            exit_code, _run_one_season(client, config.data_dir, season_label)
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
