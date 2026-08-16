<!--
Sync Impact Report
- Version change: 1.1.0 → 2.0.0
- Rationale for MAJOR: redefines the scope of Principle I (Member Data Privacy First,
  NON-NEGOTIABLE). The principle previously read as an unqualified "MUST NOT be
  uploaded to third-party cloud services"; this amendment adds a narrow, conditional
  exception for address-text geocoding. That flips the compliance verdict for a
  concrete, already-planned behavior (specs/002-map-generator's Nominatim call) from
  "in tension with a NON-NEGOTIABLE principle" (see plan.md's Complexity Tracking,
  CONDITIONAL PASS) to compliant — a backward-incompatible redefinition of what the
  principle permits, not a mere clarification or additive expansion.
- Principles added: none
- Principles modified:
  - I. Member Data Privacy First (NON-NEGOTIABLE) — added an explicit, narrowly-scoped
    exception permitting address-text-only geocoding lookups, under stated conditions.
- Sections added: none
- Sections removed: none
- Section content changes: none outside Principle I
- Templates checked for alignment:
  - .specify/templates/* — not modified by this command (out of scope per scope guard).
  - specs/002-map-generator/plan.md's Complexity Tracking table explicitly recommended
    this amendment before/alongside implementation; this ratifies that recommendation.
    No further template changes needed — the exception is scoped to match what that
    plan already documents (research.md §3, §11).
- Deferred TODOs: none — all placeholders resolved from user input.
-->

# Team Rynkeby Hamburg Team Map Tool Constitution

## Core Principles

### I. Member Data Privacy First (NON-NEGOTIABLE)

Team member data (name, address, phone number, photo, birthday) is real personal data
about real people, scraped from a members-only intranet, and MUST be treated as
sensitive at every stage of handling.

- Data MUST be stored locally only. It MUST NOT be uploaded to third-party cloud
  services, analytics platforms, or public repositories, and MUST NOT be committed to
  version control.
- Any artifact intended for sharing beyond the immediate team (interactive maps,
  shared calendars, printed graphics) MUST expose only the minimum data necessary for
  its stated purpose, and MUST support excluding a member who opts out.
- Credentials or session tokens used to scrape the Team Rynkeby Intranet MUST be kept
  out of source control (environment variables or a gitignored config file only).
- Exception — address-only geocoding lookups: a member's `address` field text MAY be
  sent to a third-party geocoding lookup (e.g. OpenStreetMap's Nominatim) solely to
  resolve it to map coordinates, and only when all of the following hold:
  - No other member field (name, photo, phone, birthday) accompanies the request —
    the request payload is address text and nothing else.
  - Each distinct address is geocoded at most once, ever; the resolved coordinates
    are cached locally and reused on every subsequent run, never re-requested.
  - The lookup is the minimum necessary to produce the artifact's location data; no
    other third-party service is covered by this exception.
  This exception exists because plotting members on a map is impossible without
  converting an address into coordinates; it MUST NOT be read as license to send any
  other field, or to send address data for any purpose beyond geocoding.

Rationale: The entire input to this tool is personal data. A privacy lapse — an
accidental commit, an over-shared map, a leaked credential — directly harms team
members' trust and safety, and is the single largest risk this project carries.
Address-text geocoding is the one deliberate exception to the "no third-party upload"
rule; the conditions above (address-only, once-ever, cached, single-purpose) exist
specifically to keep that exception narrow rather than letting it become a general
license to share member data.

### II. One Script, One Artifact

Each target artifact (member map, rider pairing suggestions, birthday calendar) is
produced by its own independent, focused Python script rather than a single
multi-purpose application or shared framework.

- A new use case gets a new script, not a new mode or flag bolted onto an existing
  one.
- Shared logic (e.g. loading the local member dataset) MAY be factored into a small
  shared module once duplication is real and causing bugs — not in anticipation of it.

Rationale: The project's scope is intentionally small — a handful of related use
cases, not a platform. Independent scripts stay easy for a single maintainer to
understand, run, and debug, and avoid infrastructure the project doesn't need.

### III. Local Data Is the Editable Source of Truth

Data scraped from the Team Rynkeby Intranet is a starting point, not an authority: it
MUST be persisted to a local, human-readable store (e.g. CSV/JSON) that manual
corrections are applied to.

- Re-running the scraper MUST NOT silently overwrite manually corrected fields;
  merging scraped updates into the local store MUST preserve existing manual edits by
  default.
- The local store's format MUST stay easy to inspect and hand-edit without special
  tooling.

Rationale: Intranet data is known to be incorrect or spotty, and is expected to be
manually improved (fixed birthdays, added addresses, replaced photos) after scraping.
Every downstream script depends on those corrections surviving future scrapes.

### IV. Python, Minimal Dependencies

All processing scripts are written in Python. Dependencies MUST be well-maintained,
widely used libraries chosen for the smallest footprint that does the job (e.g. a
plotting/mapping library rather than a full web framework); heavier dependencies
(databases, web servers, cloud SDKs) require explicit justification before being
introduced.

Rationale: Matches the project's stated implementation approach and keeps the tool
runnable by a small volunteer team without infrastructure to maintain.

### V. Test-First Development (Red-Green) (NON-NEGOTIABLE)

New functionality — a new script (Principle II) or new behavior added to an existing
one — MUST be developed test-first using the red-green cycle:

- Write a failing test that demonstrates the missing behavior (red) before writing the
  implementation.
- Write the minimal code needed to make that test pass (green).
- Refactor only once the test is green, without changing behavior.

Constraints on how this is done:

- Tests MUST run via `pytest` (`uv run pytest`) and MUST NOT read, write, or depend on
  real data in `data/` or `.env`; use fixtures or synthetic data shaped like real
  member records, never actual scraped data (Principle I).
- Bug fixes SHOULD also start with a failing test that reproduces the bug, following
  the same red-green cycle.
- Test code stays proportional to the project's size: prefer plain `pytest` functions
  and fixtures over additional test frameworks or infrastructure (Principle IV).

Rationale: Untested scraping and merge logic is exactly where Principle III
(preserving manual corrections) silently breaks. Writing the failing test first forces
the expected behavior to be stated before code exists, and provides the verification
that a single-maintainer project has no PR-review safety net to otherwise catch.

## Technology Constraints

- Language: Python 3, pinned once project tooling (e.g. `pyproject.toml`) exists.
- Data source: the Team Rynkeby Intranet website, accessed via scraping; access
  details and credentials are never committed to the repository.
- Local storage: a human-readable, diff-friendly format (CSV/JSON), not a database,
  unless a documented need arises.
- Output artifacts: static image maps and/or shareable interactive (zoomable) maps;
  an `.ics` calendar file of member birthdays; rider pairing suggestions based on
  location and seasons of participation.
- Testing: `pytest`, run via `uv run pytest`; no additional test framework or
  infrastructure without documented need (Principle IV, Principle V).

## Development Workflow

- Given the project's small scope and maintainer count, formal PR review is not
  required, but changes to scraping or data-merge logic (Principle III) SHOULD be
  manually verified against a sample of real data before being relied on, in addition
  to the automated tests required by Principle V.
- Each script SHOULD be runnable and testable independently of the others, in line
  with Principle II.
- New functionality MUST have a failing test written before implementation begins,
  per Principle V's red-green cycle; `uv run pytest` MUST pass before a change is
  considered done.

## Governance

This constitution supersedes ad hoc practice for this project. Amendments are made by
editing this file directly and MUST update the version and Last Amended date per the
versioning policy below. Before relying on changes that touch data scraping, local
storage, or any artifact shared outside the team, self-review the change against the
Core Principles above, in particular Principle I.

Versioning policy: MAJOR.MINOR.PATCH — MAJOR for removing or redefining a principle,
MINOR for adding a principle or materially expanding guidance, PATCH for wording or
clarification fixes that don't change meaning.

**Version**: 2.0.0 | **Ratified**: 2026-08-15 | **Last Amended**: 2026-08-16
