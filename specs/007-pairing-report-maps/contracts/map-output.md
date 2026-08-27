# Contract: Generated Map Files Output

What a team organizer (or a future script) can rely on when reading the PNG files
under `<RKBY_DATA_DIR>/reports/maps/`, produced by
`scripts/generate_rider_pairings.py`.

## File layout

```
<RKBY_DATA_DIR>/reports/
├── rider_pairings.md    # unchanged (006) -- committed to the RKBY_DATA_DIR git repo
├── rider_pairings.pdf   # unchanged (006) -- only after --pdf/--pdf-only, never committed
└── maps/                 # NEW (this feature) -- never committed, see "Git handling" below
    ├── overview.png       # exactly one per run
    ├── cluster_1.png       # one per Training Cluster present this run
    ├── cluster_2.png
    └── ...
```

## Regeneration semantics (FR-010)

Every run of `scripts/generate_rider_pairings.py` (without `--pdf-only`) that reaches
the report-writing step:

1. Deletes every existing file under `reports/maps/` (the whole directory's
   contents, not a filename-prefix-matched subset — a prior run's cluster count or
   numbering may no longer match this run's).
2. Writes a fresh `overview.png`.
3. Writes a fresh `cluster_<n>.png` for every Training Cluster this run found, `<n>`
   1-based in the same order those clusters are numbered in
   `rider_pairings.md`'s own `### Cluster <n>` headings.

`--pdf-only` never touches `reports/maps/` — it only re-renders the PDF from the
Markdown file's current on-disk content (unchanged 006 behavior), so it never
regenerates map images either.

## Naming (FR-003, FR-006)

- `overview.png` — stable name, always present after a non-`--pdf-only` run,
  regardless of how many members it ends up depicting (even zero — see below).
- `cluster_<n>.png` — `<n>` matches the corresponding `### Cluster <n>` heading in
  `rider_pairings.md` exactly. A cluster's number is *not* stable across runs if the
  underlying cluster list changes shape (a cluster merging, splitting, appearing, or
  disappearing shifts later clusters' numbers) — this mirrors how the `### Cluster
  <n>` headings themselves are already unstable across such changes (006).

## Content contract

- **overview.png**: every member of the run's Eligible Member Pool (data-model.md) —
  every current-season member of any role who is not excluded, not opted out, and
  successfully geocoded — plotted as their own circular photo (the Team Rynkeby
  mascot placeholder standing in for anyone without a photo on file), with two or
  more overlapping at this map's zoom level (e.g. members sharing an address) drawn
  as offset side-by-side circles rather than one covering the other. Zero members
  still produces a valid PNG, centered on Germany's geographic center at the
  configured minimum-width zoom (Acceptance Scenario 3.3) — never a missing file,
  never a script failure.
- **cluster_<n>.png**: that Training Cluster's own rider members (always plotted,
  regardless of frame position — they define the frame), plus any other Eligible
  Member Pool member of any role whose position lands inside the rendered frame, for
  context (FR-005). A cluster of exactly one rider still produces a valid PNG framed
  around that one rider at the configured minimum width.
- Both variants use the exact same circular-photo styling, placeholder-mascot
  fallback, overlap-offset behavior, scale bar, and OSM attribution
  `generate_member_maps.py`'s own photo maps already use (FR-004) — a reader who's
  seen one map type in this project recognizes the other immediately. *(Updated
  post-launch: originally rendered as role-colored pins; switched to member photos
  for a more personal, recognizable map.)*

## A member with no address / ungeocoded address (FR-009)

Simply absent from every map this feature produces — no placeholder pin, no error,
no effect on any other member's rendering. Never blocks report or map generation.

## Git handling (FR-011)

`reports/` is already unconditionally listed in `RKBY_DATA_DIR`'s own `.gitignore`
(`scripts.rkby_report.frame.ensure_reports_dir_and_gitignore`, established by 006).
`generate_rider_pairings.py`'s auto-commit step force-adds only
`reports/rider_pairings.md` (`force=True`) — it never force-adds anything under
`reports/maps/`, so those files exist on disk inside `RKBY_DATA_DIR` but are never
staged, never committed, and never show up as anything but untracked/ignored in
`git status` run inside `RKBY_DATA_DIR`. They are also never written anywhere in this
project's own code repository (`RkbyMemberMapGenerator`) — `RKBY_DATA_DIR` is always
an external, gitignored-at-the-top-level path, unchanged from every other feature.
