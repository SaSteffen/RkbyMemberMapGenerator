# Phase 0 Research: Pairing Report Maps

Every "NEEDS CLARIFICATION" that would normally start this phase is already resolved
by spec.md's own Assumptions section and by re-reading the existing 002/006
implementations this feature builds on. What follows are the concrete design
decisions this plan turns those resolutions into.

## 1. Removing the Training Cluster minimum (FR-001/FR-002)

**Decision**: Change `scripts/rkby_pairing/clusters.py`'s `find_training_clusters` to
call `find_overlap_groups(..., min_group_size=1)` instead of `min_group_size=3`. No
other line in that function changes.

**Rationale**: `find_overlap_groups` (`scripts/rkby_maps/clustering.py`) already
accepts an arbitrary `min_group_size` — it was generalized for exactly this kind of
reuse when 006 added training clusters on top of 002's overlap-detection algorithm.
`min_group_size=1` returns every connected component, including a component of one —
precisely "a cluster of exactly one rider" (spec.md, Key Entities § Training Cluster).
No new code path, no new parameter to add.

**Alternatives considered**: Adding singleton riders as a separate pass alongside
`find_overlap_groups`'s output (e.g., "run the existing size-3 call, then union in
whoever's missing") — rejected as needless complexity; the function already does
exactly what's needed via an argument it already accepts.

**Consequence for existing tests**: `tests/unit/test_rkby_pairing_clusters.py`
currently has three assertions that encode the old 3-minimum as correct behavior:
`test_two_nearby_riders_with_no_third_nearby_form_no_cluster` (asserts `clusters ==
[]` for a 2-person group), `test_cluster_radius_km_changes_which_groups_qualify`
(asserts `narrow == []` where the two closest members would now form a 2-member
cluster), and `test_excluded_ignored_and_ungeocoded_riders_are_never_cluster_nodes`
(asserts `clusters == []` where "a"/"b" would now form a 2-member cluster). These
must be rewritten (not just left passing) as part of the tasks-phase red-green cycle —
they currently assert the exact behavior FR-001 requires this feature to remove.

## 2. Reusing the existing map-rendering pipeline (FR-004)

**Decision**: Promote the overlap-aware pin-rendering plumbing that already exists,
privately, inside `scripts/generate_member_maps.py` into a new shared module
`scripts/rkby_maps/pin_map.py`:

- `CANVAS_SIZE`, `DEFAULT_MIN_WIDTH_KM` — unchanged values, moved as-is.
- `DETAIL_MAP_PADDING_KM` / `DETAIL_MAP_EDGE_MARGIN_PX` → renamed `PADDING_KM` /
  `EDGE_MARGIN_PX` (no longer detail-map-specific once a second caller uses them for
  cluster maps). *Both are gone post-launch*, replaced by a single `FRAME_PADDING_PX`
  (002 research.md §5 addendum); this feature's callers moved with them.
- `_pixel_positions` → `pixel_positions` (public).
- `_group_position` → `group_position` (public). *Removed post-launch* — the centroid
  math moved into `rkby_maps/declutter.py` (002 research.md §8 addendum).
- `_records_within_frame` → `records_within_frame` (public) — this is the exact
  function FR-005 needs: "other current-season members of any role who fall within
  the same geographic area," already implemented for 002's own detail maps.
- `_draw_pin_layer` → `render_pin_layer` (public) — draws individual role-colored
  pins, with same-scale overlaps handled by 002's own overlap rendering (FR-014-style
  handling), already implemented for 002. *Post-launch* that handling is a decluttered
  grid rather than a merged fallback pin (002 research.md §8 addendum), and this
  feature renders faces via `render_photo_layer` rather than pins — both changes reach
  it through the shared module, with no separate decision here.
- `_overview_center_and_zoom` → `overview_center_and_zoom` (public) — bounding-box
  framing with the empty-member-set fallback to Germany's geographic center
  (`DEFAULT_CENTER`), already implemented for 002's overview map and directly reusable
  for this feature's overview map (FR-006) with the same degenerate-input handling
  Edge Cases/Acceptance Scenario 3.3 require.

`generate_member_maps.py` is refactored to import these from `rkby_maps.pin_map`
instead of defining its own copies; its behavior is unchanged (existing tests for it
keep passing, only their import lines move).

**Rationale**: FR-004 requires cluster/overview maps to reuse "basemap tiles,
role-colored member markers, and same-location/overlap handling" — not a
lookalike reimplementation. The logic already exists and is already exactly right;
it's simply private to one script. Promoting it is the "shared logic MAY be factored
into a small shared module once duplication is real and causing bugs — not in
anticipation of it" carve-out Constitution Principle II already grants, and mirrors
the precedent already set when `canonical_match_keys` was promoted out of
`rkby_interactive_map/merge.py` into `rkby_records.py` for feature 005/006
(`rkby_records.py`'s own docstring cites this exact justification).

**Alternatives considered**:
- Reimplementing equivalent pin/overlap/frame logic inside a new `rkby_pairing`
  module — rejected: duplicates ~80 lines and risks drifting from FR-004's
  byte-for-byte reuse requirement the moment either copy is touched later.
- Having `rkby_pairing/maps.py` import `generate_member_maps.py`'s private
  (underscore-prefixed) functions directly — rejected: reaching into another
  script's private implementation details breaks the "independent scripts" boundary
  Principle II describes, and the leading underscore is a signal those names are not
  a public interface.

## 3. One shared eligibility pool for "context members" and the overview map (FR-005/FR-007)

**Decision**: Both "other current-season members of any role" shown for context on a
cluster's map (FR-005) and the overview map's own membership (FR-006/FR-007) are
computed from the exact same set: every latest-season record for which
`scripts.rkby_pairing.eligibility.is_eligible_base` is `True` (not excluded, not
opted out via `ignore`, successfully geocoded), with no role filter. This function
already exists, is already unit-tested, and already matches FR-007's stated rule
verbatim ("not excluded, not opted out, successfully geocoded").

**Rationale**: Both requirements cite the same underlying rule; computing the pool
once and reusing it for both purposes makes that equivalence provably true rather
than an assertion that two independently-maintained filters happen to agree today.

**Alternatives considered**: Deriving the "context members" pool separately (e.g.,
scoped narrower, or re-deriving eligibility inline in `rkby_pairing/maps.py`) —
rejected: no functional requirement calls for them to differ, and doing so risks
exactly the kind of silent, driftable inconsistency User Story 1 is fixing for
Training Clusters themselves.

## 4. No new geocoding calls (FR-009, FR-012)

**Decision**: This feature does not call `scripts.rkby_maps.geocoding.
geocode_record_if_needed` (or otherwise contact Nominatim). It uses whichever
`latitude`/`longitude` is already cached on a record — the same read-only posture
`generate_rider_pairings.py` already has today (`_log_skipped_members` already logs
and skips a record with no cached coordinates; that behavior is unchanged). A member
with no cached coordinates is simply left off every map this feature produces
(FR-009) — never geocoded on the spot.

**Rationale**: FR-012 requires this script to run independently of
`generate_member_maps.py` having already processed the season — it does not require
this script to take over that script's geocode-on-demand responsibility too. Doing so
would duplicate Nominatim's request throttling and the fill-empty-only cache-write
logic (`research.md` of 002) a second time, for a behavior no functional requirement
in spec.md actually asks for. A team that wants every current member's coordinates
resolved before running the pairing report still runs `generate_member_maps.py`
first, exactly as today; this feature changes nothing about that relationship other
than no longer *requiring* it to have happened.

**Alternatives considered**: Adding geocode-on-demand to `generate_rider_pairings.py`
too — rejected as unrequested scope creep with a real cost (a second place that must
correctly rate-limit and cache-write Nominatim calls, Constitution Principle I's
geocoding exception conditions applying twice instead of once).

## 5. Map file layout, naming, and regeneration (FR-010/FR-011)

**Decision**: Map PNGs live under `<RKBY_DATA_DIR>/reports/maps/`:
- `overview.png` — the one overview map per run.
- `cluster_<n>.png` — one per Training Cluster, `<n>` matching the report's own
  `### Cluster <n>` heading numbering (1-based, same deterministic sort order
  `render_report` already applies via `enumerate(clusters, start=1)`).

Every run first clears `reports/maps/`'s contents, then writes a fresh set — not a
`glob()`-and-unlink pass keyed by a stable filename prefix (`generate_member_maps.
py`'s own approach), because this feature's cluster count and numbering can both
change between runs (a cluster gaining/losing members shifts every later cluster's
`<n>`), so a full clear is the only way to guarantee no stale, wrongly-numbered file
survives a run in which the cluster list shrank or reordered.

`reports/` is already unconditionally gitignored inside `RKBY_DATA_DIR` by
`scripts.rkby_report.frame.ensure_reports_dir_and_gitignore` (which
`generate_rider_pairings.py` already calls on every run). `generate_rider_pairings.
py`'s `auto_commit` call only force-adds `reports/rider_pairings.md` specifically
(`force=True`) — it is never told about `reports/maps/`, so those files are written
locally and simply stay untracked, satisfying FR-011/the Assumptions section's "not
committed to the local data repository's git history" with zero new `.gitignore`
entries needed.

**Rationale for the directory choice**: `reports/maps/` keeps this feature's output
inside the directory tree `generate_rider_pairings.py` already owns
(`reports/`), rather than reaching into `maps/pins/`/`maps/photos/` —
directories `generate_member_maps.py` owns, deletes from, and recreates on its own
schedule. Mixing the two would put FR-012's independence at risk (a
`generate_member_maps.py` run could delete this feature's files, or vice versa) for
no benefit.

**Alternatives considered**: `maps/pairing/` under the member-map generator's
existing `maps/` tree — rejected per the ownership/independence argument above.
Season- or timestamp-suffixed filenames — rejected: `reports/rider_pairings.md`
itself is already a stable, always-overwritten filename (contracts/report-output.md,
006), and stale-file cleanup is simpler with a full-directory clear than with a
suffix scheme that would need its own stale-suffix cleanup logic.

## 6. Report structure placement (FR-003, FR-008)

**Decision**: `render_report` gains one new top-level section, `## Team Overview`,
placed immediately after the intro line and before `## New Riders`, containing only
the overview map image. Each `### Cluster <n>` subsection under `## Training
Clusters` gains its own cluster's map image, placed directly under the heading,
before that cluster's member roster — the same relative position the New Rider/
Suggested Contact `<img>` tags already occupy relative to their own text (`report.py`
today).

**Rationale**: FR-008 requires the overview map to read as "distinct, prominent...
independent of and separate from the per-cluster maps and the per-new-rider...
content" — a section of its own, ahead of the other content, satisfies that directly.
Image-before-roster on each cluster mirrors the existing photo-before-contact-details
convention already established for New Riders and Suggested Contacts, so a reader
encounters the same visual pattern (picture, then details) throughout the whole
report rather than a new one just for clusters.

**Alternatives considered**: Placing the overview map at the very end of the report —
rejected, "prominent" reads more naturally as early/first than last for a document a
reader scans top-to-bottom.

## 7. Image path resolution in the Markdown/PDF output

**Decision**: Since `reports/rider_pairings.md` and `reports/maps/*.png` share the
same parent directory (`reports/`), image `<img src="...">` paths are simply
`maps/overview.png` / `maps/cluster_<n>.png` — no `../` prefix needed (unlike member
photo references, which live under `seasons/<label>/` and therefore do need one).
`scripts/rkby_pairing/pdf.py`'s existing `render_pdf` already resolves relative
`<img>` paths against the `.md` file's own directory (`pisa.CreatePDF(..., path=str(
md_path))`) — this works unchanged for the new map images with no code change to
`pdf.py`.

**Rationale**: Simplest path expression that is correct for the chosen directory
layout (Decision 5); confirmed the existing PDF path-resolution mechanism already
covers it, so `pdf.py` needs no change and stays a "renders whatever the `.md`
currently says" component regardless of what images that Markdown happens to
reference.

## 8. Testing approach

**Decision**: New tests follow the two patterns this project already has:
- Pure logic (cluster-to-filename numbering, pool selection, section-assembly
  order) — plain synthetic in-memory records, no network mocking, matching
  `tests/unit/test_rkby_pairing_clusters.py`/`test_rkby_pairing_report.py`'s existing
  style.
- Anything that actually stitches a basemap (an end-to-end
  `render_overview_map`/`render_cluster_map` call, or a `generate_rider_pairings.py`
  CLI run that produces real PNG files) — mock OSM tile HTTP responses with the
  `responses` library exactly as `tests/unit/test_generate_member_maps_cli.py` and
  `tests/unit/test_detail_fetch.py` already do; assert on the output `Image.open(...)
  .size`/existence, not pixel-exact rendering, matching those tests' existing
  assertions style.

**Rationale**: Reuses established, already-reviewed patterns rather than introducing
a third testing approach for what is functionally the same kind of code (map
rendering) 002 already has full coverage conventions for.
