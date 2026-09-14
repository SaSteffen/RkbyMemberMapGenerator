# Phase 1 Data Model: Applicant Note Field

This feature adds exactly one field to the **Applicant Record** entity already defined
in full by specs/001-scraper-persistence/data-model.md. Nothing else in that data model
(Season, Photo Asset, Run Log, Local Data Repository) changes.

## Applicant Record — added field

| Field | Type | Required | Write rule |
|---|---|---|---|
| `note` | string \| null | no | Frozen once non-empty (fill-empty-only, same rule as `address`/`phone`/`role`). Raw text from the applicant list table's `Note` column, stored as scraped. `null`/absent until first observed as non-blank. |

Placed in `_RECORD_FIELD_ORDER` (`scripts/rkby_records.py`) directly after `role`, next
to the other fields sourced straight from the list-row rather than the detail popup.
Existing persisted records without a `note` key are backfilled with `note: null` the
next time any run re-writes them (research.md §5) — no migration needed.

## Merge / conflict behavior

`note` is added to `_CONFLICT_FIELDS` in `scripts/scrape_applicants.py`, which already
drives, for `address`/`phone`/`birthday`/`role`:

- **Fill-empty-only merge** (`merge_record`): an existing non-empty `note` is never
  overwritten by a later scrape.
- **Existing-vs-scraped conflict logging** (`_conflicting_fields` in `persist_records`):
  a non-empty scraped `note` that disagrees with an existing non-empty `note` is logged
  as a warning, existing value kept — same as any other conflict field.
- **Within-scrape duplicate handling** (`deduplicate_scraped_rows`): two rows matching
  the same person with disagreeing non-empty `note` values are treated as a meaningful
  conflict (flagged, neither persisted this run), same as any other conflict field.

## Schema

`scripts/schemas/applicant_record.schema.json` gains:

```json
"note": {
  "type": ["string", "null"],
  "description": "Free-text internal note entered by a team admin against this applicant directly in the intranet applicant list table's Note column, or null if none has been recorded."
}
```

No changes to `required`, to `allOf`, or to any other property.
