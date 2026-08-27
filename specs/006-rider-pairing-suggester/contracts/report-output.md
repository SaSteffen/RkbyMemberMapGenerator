# Contract: Generated Pairing Report Output

What a team organizer (or a future script) can rely on when reading
`<RKBY_DATA_DIR>/reports/rider_pairings.md` and the PDF exported from it.

## File layout

```
<RKBY_DATA_DIR>/reports/
├── rider_pairings.md    # committed to the RKBY_DATA_DIR git repo on every write (FR-014)
└── rider_pairings.pdf   # only present after --pdf/--pdf-only; gitignored, never committed
```

Both filenames are stable — never season- or timestamp-suffixed (research.md §8).
Every non-`--pdf-only` run fully overwrites `rider_pairings.md`; a prior hand-edited
version is never lost because it stays recoverable from `RKBY_DATA_DIR`'s own git
history (FR-014).

## Markdown structure

```markdown
# Rider Pairing Suggestions — <season label>

Generated <ISO date>. Hand-edit this file freely — re-running the script overwrites
it, but every prior version stays recoverable from this repository's git history.

## New Riders

### <First> <Last>
![<First> <Last>](../seasons/<season>/<photo path>)   <!-- only when a photo is on file -->

- Address: <address>
- Phone: <phone>          <!-- omitted if null -->
- Email: <email>          <!-- omitted if null -->

Suggested contacts:

1. **<First> <Last>** — <distance> km away<!--, N years apart--><!--, same sex-->
   - Address: <address>
   - Phone: <phone> / Email: <email>
2. ...

<!-- "No eligible contacts found nearby." when the list is empty -->

### <next New Rider>
...

## Training Clusters

### Cluster 1 (<N> riders)

- **<First> <Last>** — <address> — <phone>/<email>
  ![<First> <Last>](../seasons/<season>/<photo path>)
- ...

<!-- "No training clusters found this season." when there are none -->
```

Notes on the structure:

- **One `##` section per New Rider**, in a deterministic order (e.g. alphabetical by
  last name) — every New Rider appears even with an empty suggestion list (SC-001,
  Acceptance Scenario 1.4/Edge Cases).
- **Contact info is always shown in full** (FR-009): name, address, and whichever of
  phone/email are on file. Nothing is withheld for privacy-minimization — this file is
  for internal team use only and never leaves `RKBY_DATA_DIR` (Constitution Check row
  I).
- **Photo**: a Markdown image reference to the person's own `photo` field, path
  computed relative to the report file's own location
  (`reports/rider_pairings.md` → `../seasons/<season>/<photo path>`); simply omitted
  — no placeholder image — when the record has no photo on file (Edge Cases).
- **Suggested-contact ordering** matches `rank` (data-model.md § Suggested Pairing) —
  closest/best match first (Acceptance Scenario 1.4).
- **Ranking factors shown per suggestion** (distance always; age gap and same-sex only
  when known) are display-only annotations of already-computed values — they don't
  change the contract's parseability, only its readability for a human reader.
- **Training Clusters** section lists every Training Cluster (data-model.md), each
  member with the same full contact info + photo treatment as above. Riders-only —
  Service Crew/Supporter members never appear here even if geographically co-located
  (Acceptance Scenario 2.3).
- The whole file is plain, human-editable Markdown — no generated IDs, no HTML comments
  required at runtime (the `<!-- -->` lines above are illustrative of *optional*
  content, not literal markers the script emits or a re-run depends on parsing back
  out).

## PDF export contract

`reports/rider_pairings.pdf` is a direct rendering of `rider_pairings.md`'s content at
export time (research.md §9): same section structure, same text, same photos embedded
as images (resolved from the same relative paths the Markdown uses). It carries no
information not already in the Markdown — it exists purely so the report can be shared
as a single file with someone reading it outside a Markdown-aware tool (SC-005/SC-006).
Exporting never re-runs the pairing computation and never modifies
`rider_pairings.md` (FR-012) — running `--pdf-only` twice with no edit in between
produces byte-identical PDF content (modulo any timestamp `xhtml2pdf`/`reportlab`
itself embeds in the PDF's own metadata, which is not part of this contract).

## Skipped members

Every member excluded from any role in this report (excluded, ignored, or not
geocoded) is named in that run's log output — this feature reuses the same per-season
`logs/<run-timestamp>.log` convention every other script already writes to
(`rkby_records.setup_run_logger`), not a silent drop.
