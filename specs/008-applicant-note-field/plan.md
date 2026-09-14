# Implementation Plan: Applicant Note Field

**Branch**: `008-applicant-note-field` | **Date**: 2026-09-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-applicant-note-field/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Read the intranet applicant list table's existing "Note" column (already present in the
HTML alongside Address/Phone/Role, which the scraper already reads from that same row)
and persist it as a new optional `note` field on the applicant record, governed by the
scraper's existing fill-empty-only merge, ignore-freeze, and schema-validation rules
(specs/001-scraper-persistence). No new network request, popup fetch, script, or
dependency — this is a same-script, same-request field addition, mirroring how `role`
was added in commit `dfa18cb`.

## Technical Context

**Language/Version**: Python 3.11+ (unchanged — existing `scripts/scrape_applicants.py`)

**Primary Dependencies**: None added. Reuses `beautifulsoup4` (row parsing), `PyYAML`
(persistence), `jsonschema` (schema validation) already in place per
specs/001-scraper-persistence's research.md.

**Storage**: Local filesystem only — one more key (`note`) in the existing per-applicant
YAML record under `<RKBY_DATA_DIR>/seasons/<season-label>/applicants/`. No schema/format
change beyond one new optional property.

**Testing**: `pytest`, extending the existing obfuscated fixtures in `tests/fixtures/`
(`applicants_page_1.html` already has an (empty) `Note` column per the real table's
header shape) — no real network calls.

**Target Platform**: Unchanged — Linux/macOS developer machine, run on demand via `uv run`.

**Project Type**: Single CLI script (Constitution II) — extends the existing scraper
script, does not add a new one.

**Performance Goals**: Unchanged — not performance-sensitive (research.md of 001 applies).

**Constraints**: Same as specs/001-scraper-persistence (no credentials/personal data in
the source repo; safe to re-run with zero side effects on unchanged data; note text is
real personal/free-text member data, so fixtures MUST use obfuscated/synthetic text,
never real scraped notes).

**Scale/Scope**: One new field on one existing record schema; no new entities, files, or
scripts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Member Data Privacy First | `note` is persisted the same way as every other field: locally under `RKBY_DATA_DIR`, never in the source repo. It is not an address, so it is never sent to any third-party geocoding lookup or any other external service. Test fixtures use synthetic note text, never real scraped notes. | PASS |
| II. One Script, One Artifact | Extends the existing `scripts/scrape_applicants.py`; no new script, mode, or flag. | PASS |
| III. Local Data Is the Editable Source of Truth | `note` follows the exact fill-empty-only merge rule already governing address/phone/role/etc. (FR-003 here = FR-009 of 001); an "ignore"-marked record's `note` is never touched (FR-004 here = FR-011 of 001). | PASS |
| IV. Python, Minimal Dependencies | Zero new dependencies. | PASS |
| V. Test-First Development (Red-Green) | New parsing/merge/validation behavior for `note` gets failing tests first, following the same pattern as the existing `role`/`additional_roles` field tests in `tests/unit/test_parsing.py` and `tests/unit/test_store_merge.py`. | PASS |

No violations to justify — Complexity Tracking is not needed.

**Post-Phase-1 re-check**: data-model.md and contracts/ confirm this stays a one-field,
same-script, same-request addition with no new dependency or structural need. Gates
above still PASS unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/008-applicant-note-field/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
scripts/
├── scrape_applicants.py             # extended: read + persist the Note column (no new file)
└── schemas/
    └── applicant_record.schema.json # extended: adds the `note` property

tests/
├── unit/
│   ├── test_parsing.py              # extended: Note column -> row["note"] (mirrors role/Address parsing)
│   ├── test_store_merge.py          # extended: fill-empty-only + ignore-freeze for `note`
│   └── test_schema_validation.py    # extended: `note` accepted by the schema
└── fixtures/
    └── applicants_page_1.html       # extended: give at least one row a non-blank Note value
```

**Structure Decision**: No new files at the script or test-module level — this is a
one-field extension of the existing `scripts/scrape_applicants.py` (Constitution II),
its existing schema, and its existing test modules, matching exactly how `role` was
added to the same script in commit `dfa18cb` (a table-column field, read from the same
list-page HTML, with no new request).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — the Constitution Check gates above all pass with no exceptions needed.
This section is intentionally empty.
