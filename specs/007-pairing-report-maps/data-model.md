# Phase 1 Data Model: Pairing Report Maps

No changes to `scripts/schemas/applicant_record.schema.json` or any persisted
`.yaml` record — this feature, like 006 before it, is purely derived/read-only over
data `rkby_records.load_existing_records` already returns (research.md §4: no new
geocoding, no record mutation). The only new persisted artifacts are the map PNG
files described below and the extended report file
(`contracts/report-output.md`)/its PDF export (unchanged mechanism, new content).

## Training Cluster *(revised)*

**Source**: Computed — a connected component of the latest season's Rider-role pool
(`scripts/rkby_pairing/clusters.py::find_training_clusters`), unchanged except for
minimum size.

**Membership rule** (FR-001/FR-002, Acceptance Scenarios 1.1-1.4):
- Pool: latest-season records with `classify_role(role) == "rider"` (any
  `num_previous_seasons`), `excluded is not True`, `ignore is not True`, geocoded
  (`latitude`/`longitude` both set) — **unchanged from before this feature**.
- Two pool members are linked if `haversine_km(a, b) <= cluster_radius_km` (default
  `5`, `--cluster-radius-km`) — **unchanged**.
- A cluster is one connected component of **at least 1** linked member (previously
  at least 3, research.md §1) — **the only rule that changes**. A single isolated
  rider is now its own one-member cluster instead of being dropped from the report
  entirely.
- Non-Rider members are still never candidates for cluster membership (Acceptance
  Scenario 1's parity with the old Acceptance Scenario 2.3) — they're simply never
  nodes in the graph, unaffected by the minimum-size change.

**Fields** (unchanged): `member_match_keys: list[str]`, `centroid: tuple[float,
float]`.

**Cardinality**: Zero or more per latest season; exactly as many as there are
connected components in the eligible-rider proximity graph (was: only components of
size ≥ 3). Report ordering (`sorted(groups, key=sorted)`, unchanged) determines each
cluster's `<n>` used both in its `### Cluster <n>` heading and its `cluster_<n>.png`
map filename (Cluster Map, below).

## Eligible Member Pool (context/overview) *(new, derived, not stored)*

**Source**: Computed once per report run — every record in the latest season's
`load_existing_records` result for which `scripts.rkby_pairing.eligibility.
is_eligible_base` is `True`.

**Rule** (FR-006/FR-007, research.md §3): `excluded is not True`, `ignore is not
True`, `latitude is not None and longitude is not None`. No role restriction — this
is the superset FR-007 explicitly calls out ("not restricted to riders"), reusing the
identical function `rkby_pairing/eligibility.py` already exposes.

**Used by**:
- **Overview Map** (below) — this pool *is* the overview map's full membership.
- **Cluster Map** (below) — this pool, filtered to whoever's pixel position lands
  inside a given cluster's rendered frame, is the "other current-season members of
  any role" FR-005 requires alongside that cluster's own riders.

## Cluster Map *(new)*

**Source**: Computed and rendered per Training Cluster (one PNG per cluster with at
least one member — i.e., every cluster, since the minimum is now 1).

**Framing** (FR-003, research.md §2 promoted helpers):
- `center, zoom = zoom_for_bounding_box(cluster_member_points, padding_km=PADDING_KM,
  min_width_km=DEFAULT_MIN_WIDTH_KM, canvas_size=CANVAS_SIZE)` — identical sizing
  formula 002 already uses for its own detail maps (handles the "very large single
  cluster" Edge Case by widening past the floor as needed).
- `frame_records = records_within_frame(eligible_member_pool, always_include=
  set(cluster.member_match_keys), center, zoom, canvas_size=CANVAS_SIZE, edge_margin_px
  =EDGE_MARGIN_PX)` — the cluster's own riders are always drawn (they define the
  frame); any other eligible member (any role) whose position lands inside the frame
  is drawn too (FR-005), consistent with how 002's own detail maps already behave.

**Rendering** *(updated post-launch — faces, not pins)*: `render_photo_layer(s_dir,
canvas, frame_records, center, zoom)` — individual circular member photos (the Team
Rynkeby mascot standing in for anyone without a photo on file), with same-scale
overlaps (including the exact-same-address pair Edge Case) drawn as offset side-by-side
circles exactly as 002's own photo maps already render, via the promoted
`scripts.rkby_maps.photo_map` module (mirrors `pin_map.py`'s promotion, Decision 2).

**Output**: `<RKBY_DATA_DIR>/reports/maps/cluster_<n>.png`, `<n>` = this cluster's
1-based position in the same sorted order `render_report` already numbers its
`### Cluster <n>` headings by (Decision 5, research.md) — so a cluster's heading and
its map filename always agree.

**Cardinality**: Exactly one per Training Cluster present in a given run (SC-002).
Zero when there are zero Training Clusters (Edge Cases: "no attempt to render one").

## Overview Map *(new)*

**Source**: Computed and rendered once per report run, independent of Training
Clusters and New Riders/Suggested Pairings (FR-008).

**Framing** (FR-006, research.md §2 promoted helper): `center, zoom =
overview_center_and_zoom(eligible_member_pool, min_width_km=DEFAULT_MIN_WIDTH_KM)` —
the same bounding-box-with-degenerate-input-fallback logic 002's own overview pin map
already uses (falls back to `DEFAULT_CENTER`, geographic center of Germany, and the
`min_width_km` floor's zoom when `eligible_member_pool` is empty — Acceptance
Scenario 3.3).

**Rendering** *(updated post-launch — faces, not pins)*: `render_photo_layer(s_dir,
canvas, eligible_member_pool, center, zoom)` — same circular-photo/overlap-offset
rendering as Cluster Maps, over the full pool instead of one cluster's frame.

**Output**: `<RKBY_DATA_DIR>/reports/maps/overview.png`.

**Cardinality**: Exactly one per report run, always produced even when
`eligible_member_pool` is empty (Acceptance Scenario 3.3, SC-003) — report generation
never fails for lack of plottable members.

## Pairing Report (output file) *(extended)*

See `contracts/report-output.md` for the full structure contract. In addition to
006's existing `## New Riders` and `## Training Clusters` sections: one new `## Team
Overview` section (Overview Map image, placed first — FR-008); each `### Cluster <n>`
subsection gains its own Cluster Map image (FR-003). Regenerated in full on every run
exactly as before — the Markdown, its embedded map references, and the map PNG files
themselves are all rewritten together, so they can never reference a stale or
missing image (FR-010).

## PDF Export (derived output file) *(unchanged mechanism)*

`$RKBY_DATA_DIR/reports/rider_pairings.pdf` — unchanged code path
(`scripts/rkby_pairing/pdf.py`). Now also embeds the Overview Map and Cluster Map
images, purely because they're now present in the Markdown it renders (research.md
§7) — no change to `render_pdf` itself.
