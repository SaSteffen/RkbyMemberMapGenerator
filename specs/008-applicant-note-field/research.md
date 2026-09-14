# Research: Applicant Note Field

This feature has no [NEEDS CLARIFICATION] markers — it's a small, well-understood
extension of an already-implemented scraper (specs/001-scraper-persistence). The
findings below are carried over from that feature's research plus direct inspection of
the current `scripts/scrape_applicants.py` and its fixtures, not fresh discovery.

## 1. Where the Note column lives

**Decision**: Read `Note` the same way `Address`/`Phone`/`Role` are already read — a
`<td>` in the same applicant-list `<tr>`, looked up by its `<th>Note</th>` header text
via the existing `cell = dict(zip(headers, tds))` mapping in `parse_applicant_rows`.

**Rationale**: specs/001-scraper-persistence's own research.md (§"Applicant list
shape") already documents the real table's header row as `Image, Created, Name, Email,
Phone, Jobtitle, Address, Zip, City, Country, Participated, Role, Age, Sex, Email send,
Motivation, Accept on teams, Note` — `Note` is the last column, already present on the
same response `parse_applicant_rows` parses today; `tests/fixtures/applicants_page_1.html`
already carries this header and an (empty) `<td>` per row. No new request, popup, or
endpoint is needed.

**Alternatives considered**: Reading it from the detail popup (like birthday/motive) —
rejected; the column is already in the list-page HTML the scraper fetches for every
other row field, so a second per-applicant request would be pure overhead for data
that's already there.

## 2. Blank-value normalization

**Decision**: `cell["Note"].get_text(strip=True) or None` — a blank/whitespace-only cell
becomes `None`, exactly like `role`'s existing `cell["Role"].get_text(strip=True) or
None`.

**Rationale**: Matches the convention every other optional scraped field already
follows (`role`, `phone`, `address`), so downstream code (schema, merge, "already holds
a value" checks) doesn't need a special case for `note`.

## 3. Merge and conflict-detection treatment

**Decision**: Treat `note` exactly like `address`/`phone`/`birthday`/`role` — add it to
`_CONFLICT_FIELDS` in `scripts/scrape_applicants.py`. This makes it participate,
for free, in:
- `merge_record`'s fill-empty-only merge (FR-003 here / FR-009 of 001),
- `_conflicting_fields`'s existing-vs-newly-scraped conflict detection and warning-log
  path (FR-014 of 001),
- `deduplicate_scraped_rows`'s within-scrape duplicate-conflict detection (Story 5 of
  001).

**Rationale**: `note` is sourced the same way (directly from the list-row HTML, no
popup fetch, no lazy "needs_x" fetch-gating like birthday/motive) as the fields already
in that tuple, so it needs no bespoke handling — reusing the tuple is the smallest
change that gets it the same guarantees.

**Alternatives considered**: Giving `note` its own lazy `_fetch_..._if_needed`-style
gate like the detail-popup fields (birthday, sex, motive) — rejected; there is no
separate fetch to gate, since the value already arrives with every row.

## 4. Schema shape

**Decision**: `"note": {"type": ["string", "null"], "description": "..."}`, unrequired,
inserted next to the other optional list-column fields (`role`) in
`scripts/schemas/applicant_record.schema.json`.

**Rationale**: Matches the existing shape of every other nullable optional string field
in that schema (`address`, `phone`, `role`, `email`, ...).

## 5. Backfilling records persisted before this feature

**Decision**: No migration script. Add `"note"` to `_RECORD_FIELD_ORDER` in
`scripts/rkby_records.py`; `_dump_record_yaml` already builds each record via
`{key: record.get(key) for key in _RECORD_FIELD_ORDER}` (`.get()`, not direct
indexing), so a record persisted before this feature existed simply gets `note: null`
backfilled the next time any run re-writes it — the same generic, already-in-place
mechanism `role`/`latitude` rely on (see the inline comment at
`scripts/rkby_records.py`'s `_dump_record_yaml`).

**Rationale**: Avoids one-off migration tooling (Constitution IV: minimal footprint) for
a case the scraper's existing merge path already handles.
