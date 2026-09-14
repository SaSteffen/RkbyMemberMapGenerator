# Feature Specification: Applicant Note Field

**Feature Branch**: `008-applicant-note-field`

**Created**: 2026-09-14

**Status**: Draft

**Input**: User description: "the applicants table has a 'note' field => scrape that
one. it should follow the same rules that already govern every other optional profile
field the scraper captures: fill-empty-only merge, included in schema validation, left
completely untouched on records marked 'ignore', and covered by unit tests using
recorded/obfuscated fixtures with no real network calls."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture the internal note when scraping (Priority: P1)

As the team data maintainer, when I scrape a season, each applicant's internal "Note"
(free text a team admin has entered against them directly in the intranet's applicant
table) ends up in their persisted record, so I don't have to look it up on the intranet
separately every time I need it.

**Why this priority**: Without this, the note text simply isn't available locally at
all — the core capability this feature exists to add.

**Independent Test**: Scrape a season containing an applicant with a Note value set on
the intranet, and verify their persisted record's `note` field holds that text; scrape a
season containing an applicant with a blank Note, and verify their persisted record's
`note` field is `null`, not an empty string.

**Acceptance Scenarios**:

1. **Given** an applicant's intranet row has non-blank Note text, **When** the scraper
   persists a new record for them, **Then** that text is stored in the record's `note`
   field.
2. **Given** an applicant's intranet row has a blank Note, **When** the scraper persists
   a new record for them, **Then** the record's `note` field is `null`.
3. **Given** a persisted record created before this feature existed (no `note` field
   recorded yet), **When** the scraper re-runs and the intranet shows a Note for that
   applicant, **Then** the record is backfilled with that note.

---

### User Story 2 - Manual corrections and "ignore" survive re-runs (Priority: P2)

As the maintainer, after I hand-edit or clear a note, or mark a record "ignore", I
re-run the scraper so that my change is preserved exactly like every other field the
scraper already protects this way.

**Why this priority**: Reuses the scraper's existing safe-to-re-run guarantee
(specs/001-scraper-persistence, User Stories 2 and 3); without it, this new field would
be the one exception a maintainer has to remember not to trust.

**Independent Test**: Hand-edit a persisted record's `note`, re-run the scraper against
the same season, and verify the value is unchanged; separately, mark a record "ignore",
re-run the scraper, and verify its `note` is untouched even if the intranet shows a new
or different Note for that person.

**Acceptance Scenarios**:

1. **Given** a persisted record whose `note` already holds a value, **When** the scraper
   re-runs and the intranet still shows some Note text for that applicant, **Then** the
   persisted `note` value remains the existing one (fill-empty-only).
2. **Given** a persisted record is marked "ignore", **When** the scraper re-runs,
   **Then** its `note` field is not modified, regardless of what the intranet currently
   shows.

---

### Edge Cases

- What happens when the intranet's Note cell is blank? It is normalized to `null`, not
  an empty string (User Story 1, AC2), matching the convention already used for every
  other optional text field this scraper captures.
- What happens to a record persisted before this feature existed? It has no `note` key
  yet; the next scrape run backfills `note: null` or the observed text without touching
  any of that record's other fields (User Story 1, AC3), the same self-healing pattern
  already used when the `role` field was added.
- What happens when a note already holds a value and the intranet's Note text later
  changes? The persisted value is left exactly as it is (fill-empty-only) — the
  maintainer's or the previous scrape's value wins, same as address/phone/role today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST capture, for each retained applicant, the internal "Note" text
  from the intranet applicant list table's Note column.
- **FR-002**: A blank/whitespace-only Note MUST be normalized to `null` rather than
  persisted as an empty string.
- **FR-003**: Once a persisted record's `note` holds a value, System MUST NOT overwrite
  it on any later scrape (fill-empty-only merge), matching FR-009 of
  specs/001-scraper-persistence for every other optional field.
- **FR-004**: A record marked "ignore" MUST have its `note` left completely untouched by
  any future scrape, matching FR-011 of specs/001-scraper-persistence.
- **FR-005**: The `note` field MUST be part of the persisted record schema and validated
  the same way as the scraper's other optional fields.
- **FR-006**: Automated unit tests MUST cover: a newly-scraped note populating a new
  record, a blank Note normalizing to `null`, an existing manually-set note surviving a
  re-scrape unchanged, and a note being left untouched on a record marked "ignore" —
  using recorded/obfuscated fixtures, with no real network calls.

### Key Entities

- **Applicant Record** (extends specs/001-scraper-persistence's definition): gains one
  additional field, `note` — free-text internal note entered by a team admin against
  this applicant directly in the intranet's applicant table, or `null` if none has been
  recorded.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a scrape run, every retained applicant's persisted record carries
  whatever internal Note text was present for them on the intranet at the time they were
  first captured (or backfilled on a later run, per User Story 1 AC3).
- **SC-002**: Running the scraper again after a maintainer hand-edits or clears a note
  results in zero changes to that field.
- **SC-003**: A record marked "ignore" keeps its `note` value byte-for-byte unchanged
  across any number of subsequent scraper runs.

## Assumptions

- The intranet's Note column is a free-text field maintained by team admins directly in
  the applicant list table — distinct from the applicant-submitted "Motivation" text
  (which surfaces both as its own list-table column and, in fuller form, as "Motive for
  participation" on the detail popup's Team application tab, already captured as
  `motive_for_participation`). This feature only concerns the admin-facing Note column.
- This feature is a small, additive extension of the existing applicant scraper
  (specs/001-scraper-persistence): every rule defined there that isn't restated above
  (all-or-nothing pagination rollback, within-season deduplication, status-based
  exclusion, credentials via environment variables, etc.) continues to apply unchanged
  and is not repeated here.
- Exactly how the Note cell is located and read out of the list table's HTML (e.g. which
  `<td>` position or column-header lookup) is a technical detail to resolve during
  planning/implementation, the same way Address/Phone/Role are already read directly
  from that same table.
