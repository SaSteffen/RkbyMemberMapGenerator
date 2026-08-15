<!--
Sync Impact Report
- Version change: (unratified template) → 1.0.0
- Rationale for MAJOR: initial ratification — the prior file contained only unfilled
  [PLACEHOLDER] tokens, so this is the first substantive constitution, not an amendment.
- Principles added:
  - I. Member Data Privacy First (NON-NEGOTIABLE)
  - II. One Script, One Artifact
  - III. Local Data Is the Editable Source of Truth
  - IV. Python, Minimal Dependencies
- Sections added: Technology Constraints, Development Workflow, Governance
- Sections removed: none
- Templates checked for alignment:
  - .specify/templates/* — not modified by this command (out of scope per scope guard);
    no outdated principle references found requiring a follow-up.
- Deferred TODOs: none — all placeholders resolved from req.md and user answers.
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

Rationale: The entire input to this tool is personal data. A privacy lapse — an
accidental commit, an over-shared map, a leaked credential — directly harms team
members' trust and safety, and is the single largest risk this project carries.

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

## Technology Constraints

- Language: Python 3, pinned once project tooling (e.g. `pyproject.toml`) exists.
- Data source: the Team Rynkeby Intranet website, accessed via scraping; access
  details and credentials are never committed to the repository.
- Local storage: a human-readable, diff-friendly format (CSV/JSON), not a database,
  unless a documented need arises.
- Output artifacts: static image maps and/or shareable interactive (zoomable) maps;
  an `.ics` calendar file of member birthdays; rider pairing suggestions based on
  location and seasons of participation.

## Development Workflow

- Given the project's small scope and maintainer count, formal PR review is not
  required, but changes to scraping or data-merge logic (Principle III) SHOULD be
  manually verified against a sample of real data before being relied on.
- Each script SHOULD be runnable and testable independently of the others, in line
  with Principle II.

## Governance

This constitution supersedes ad hoc practice for this project. Amendments are made by
editing this file directly and MUST update the version and Last Amended date per the
versioning policy below. Before relying on changes that touch data scraping, local
storage, or any artifact shared outside the team, self-review the change against the
Core Principles above, in particular Principle I.

Versioning policy: MAJOR.MINOR.PATCH — MAJOR for removing or redefining a principle,
MINOR for adding a principle or materially expanding guidance, PATCH for wording or
clarification fixes that don't change meaning.

**Version**: 1.0.0 | **Ratified**: 2026-08-15 | **Last Amended**: 2026-08-15
