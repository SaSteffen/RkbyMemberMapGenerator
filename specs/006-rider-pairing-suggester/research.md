# Phase 0 Research: Rider Pairing Suggester

## §1 Script and package layout

**Decision**: `scripts/generate_rider_pairings.py` (thin CLI) + `scripts/rkby_pairing/`
(internal package: `roles.py`, `eligibility.py`, `ranking.py`, `clusters.py`,
`report.py`, `pdf.py`).

**Rationale**: Matches the `rkby_maps/`+`generate_member_maps.py` (002) and
`rkby_report/`+`report_member_analytics.ipynb` (005) precedent exactly: one script is
the artifact (Constitution II), and everything that can be unit tested without a CLI
harness lives in a private package next to it. Splitting the package by concern
(who's eligible / how they're ranked / how clusters form / how it's rendered / how it's
exported to PDF) keeps each module focused and each concern's tests independent.

**Alternatives considered**: A single flat module. Rejected — this feature has five
genuinely distinct concerns (eligibility, ranking, clustering, Markdown rendering, PDF
export) each with their own edge cases (spec.md's Edge Cases section lists at least one
per concern); one file would mix unrelated test setups the way 002/005 already avoided.

## §2 Reusing existing infrastructure

**Decision**: Reuse, unchanged, via direct cross-package import:

- `scripts.rkby_records`: `discover_seasons`, `load_existing_records`,
  `canonical_match_keys`, `auto_commit`, `setup_run_logger`.
- `scripts.rkby_report.geo.haversine_km` — the proximity metric for both ranking
  (new rider ↔ mentor candidate) and clustering (rider ↔ rider).
- `scripts.rkby_report.frame.ensure_reports_dir_and_gitignore` — bootstraps
  `$RKBY_DATA_DIR/reports/` and its `.gitignore` entry; this feature's report lands in
  the same shared `reports/` folder feature 005's exported HTML already uses.

**Rationale**: `rkby_interactive_map/merge.py` already imports `scripts.rkby_maps.
geocoding.geocode_record_if_needed` directly from another feature's private package,
establishing that a small, genuinely reusable function doesn't have to be promoted into
`rkby_records.py` (or duplicated) the moment a second feature needs it — a direct
cross-package import is an accepted pattern in this codebase already. Both functions
reused here (`haversine_km`, `ensure_reports_dir_and_gitignore`) are already
module-level public names (no leading underscore) in `rkby_report`, signaling they were
left reusable on purpose.

**Alternatives considered**: Promoting both into `rkby_records.py` (mirroring how
`canonical_match_keys` itself was promoted there in 005). Rejected — `canonical_match_
keys` was promoted because it's identity-resolution logic tightly coupled to the
`applicant_record` schema itself (every feature touching cross-season identity needs
exactly it); `haversine_km` and the reports-dir bootstrap are generic enough, and small
enough, that a direct import costs less than a promotion (no change to 005's existing
files, no re-export shim, no risk of regressing 005's own tests). Duplicating a second
`haversine_km`/`ensure_reports_dir_and_gitignore` was also considered and rejected —
that's the exact real-vs-anticipated duplication distinction Principle II draws, and
this is real (two features, identical need, identical formula/behavior).

## §3 Cross-season "has ridden as a Rider" resolution (FR-003)

**Decision**: For each latest-season candidate record, the "has ridden before" check
is: latest-season `role` normalizes to Rider (§4), **or** any *other, earlier* season's
record for the same canonical identity has `role` normalizing to Rider. Identity
resolution reuses `canonical_match_keys`, but — unlike `rkby_report.frame.
build_member_season_frame` and `rkby_interactive_map.merge.merge_seasons`, which only
resolve identity across *eligible* (not excluded/ignored) records — this feature builds
`canonical_match_keys` over **every** raw record `load_existing_records` returns for
every season, eligible or not. The excluded/ignored/geocoded eligibility filter
(FR-002/FR-003) only gates whether a record can be *this season's* new rider or mentor
candidate; it must not gate whether an *earlier* season's record counts as historical
evidence that someone rode before — spec.md's FR-003 says "a record for the same
person... shows role Rider in any earlier scraped season," with no eligibility
qualifier on that earlier record.

**Rationale**: A person could have been excluded or self-ignored in an earlier season
yet still have genuinely ridden that season — their historical fact of having ridden
doesn't retroactively become false because of a later opt-out or a later-season "no"
status. Using the full raw record set for identity resolution also can't miss an
`alias_match_keys` link that happens to be declared on an excluded/ignored record.

**Alternatives considered**: Reusing `build_member_season_frame`'s eligible-only
resolution. Rejected per the reasoning above — it would silently under-count "has
ridden before" for anyone excluded/ignored in a past season, contradicting FR-003's
plain wording and spec.md Edge Cases' explicit alias-resolution scenario (which doesn't
condition on the aliased record's own eligibility).

## §4 Recognized role spellings (FR-002/003/004, Edge Cases)

**Decision**: A role is "Rider" / "Service Crew" / "Supporter" if `role.strip().lower()`
matches one of `scripts.rkby_maps.rendering.ROLE_COLORS`'s three keys (`"rider"`,
`"service crew"`, `"supporter"`) — imported directly rather than re-declared. Any other
value (`None`, blank, `"Coach"`, a typo) is "unrecognized" and disqualifies that
specific season's record from counting as rider evidence in *either* direction (can't
make someone a new rider, can't make them a mentor candidate, can't count as historical
"has ridden" evidence for FR-003) — exactly spec.md's Edge Cases wording.

**Rationale**: `ROLE_COLORS`' keys are already this project's one existing source of
truth for "what counts as a recognized role spelling," maintained by 002 and reused
as-is by nothing else yet; reusing the dict's keys (not its values) avoids a second,
driftable list of the same three strings. The `.strip().lower()` normalization matches
`role_color()`'s own normalization exactly, so behavior stays consistent with how the
rest of the project already treats role text.

**Alternatives considered**: A private `{"rider", "service crew", "supporter"}` set
in `rkby_pairing/roles.py`. Rejected — real duplication of `ROLE_COLORS`' keys with no
independent reason to diverge; a future fourth role color would otherwise need to be
added in two places to stay consistent.

## §5 Ranking mentor candidates for a new rider (FR-005)

**Decision**: For a given new rider, every eligible mentor candidate gets a sort key,
ascending:

1. `distance_km` — `haversine_km` between the two members' cached coordinates.
2. `age_gap_sort` — absolute year difference in `birthday`, or `math.inf` if either
   birthday is unknown (pushes unknown-age-gap pairs behind every pair with a known
   gap, but never excludes them).
3. `same_sex_sort` — `0` if both `sex` values are known and equal, else `1` (same-sex
   pairs sort ahead of everyone else, unknown-sex pairs land alongside opposite-sex
   pairs — never penalized further, never a tie-break either).

Candidates are sorted by this tuple and the top `--max-suggestions` (default 3) are
kept; a new rider with fewer eligible candidates than the cap gets all of them
(including zero, per SC-001/Edge Cases — the new rider still appears in the report).

**Rationale**: FR-005 explicitly orders the three factors "primary/secondary/tertiary,"
which is a lexicographic multi-key sort in plain terms. `distance_km` is a real-valued
float that's effectively always distinct between two different addresses, so in
practice the second and third keys mostly matter as this ranking's documented,
deterministic tie-break behavior rather than changing outcomes on typical data — which
matches spec.md's own framing of factors 2 and 3 as strictly lower-priority than
proximity, never able to override it. Using `math.inf`/`1` (rather than, say, raising
or dropping the factor) satisfies the Edge Cases requirement that an unknown birthday
or sex never blocks a pairing or the whole run — the pair is still ranked, just never
favored on that specific factor over a pair where it's known.

**Alternatives considered**: A weighted composite score (e.g.
`distance_km + 0.1*age_gap`). Rejected — spec.md's ordering ("primary... secondary...
tertiary") describes strict priority, not a tunable trade-off; a composite score could
let a large age gap overcome a small distance difference, which contradicts "proximity
... as the primary factor."

## §6 Suggestion count cap (FR-006)

**Decision**: `--max-suggestions` CLI flag, positive integer, default `3` — matches
spec.md's Assumptions ("expected to be a configurable value... consistent with other
scripts in this project exposing tunable behavior via CLI flags," echoing
`generate_member_maps.py --min-width-km`'s exact pattern).

**Rationale**: Direct requirement from spec.md's Assumptions section; no alternative
considered since the spec is explicit about both the default and the mechanism.

## §7 Training cluster detection (FR-007, User Story 2)

**Decision**: Generalize `scripts.rkby_maps.clustering.find_overlap_groups` with two
new optional parameters, both defaulted to preserve 002's exact existing behavior:

```python
def find_overlap_groups(
    positions: dict[str, tuple[float, float]],
    radius: float,
    distance_fn: Callable[[tuple[float, float], tuple[float, float]], float] = _distance,
    min_group_size: int = 2,
) -> list[list[str]]:
    ...
    threshold = 2 * radius
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if distance_fn(positions[a], positions[b]) <= threshold:
                union(a, b)
    ...
    return [members for members in components.values() if len(members) >= min_group_size]
```

`rkby_pairing/clusters.py` calls it as
`find_overlap_groups(positions, radius=cluster_radius_km / 2, distance_fn=haversine_km,
min_group_size=3)`, where `positions` maps `match_key` to `(latitude, longitude)` for
the current season's eligible Rider-role pool only (§4) — Service Crew/Supporter
members are never nodes in this graph at all, so they can never end up "in" a cluster
regardless of where they live (Acceptance Scenario 2.3). `--cluster-radius-km` is a new
CLI flag, positive float, default `5` (km) — a starting heuristic for "close enough to
plausibly train together," deliberately configurable since spec.md's Assumptions
explicitly defers the exact number to this planning phase.

**Rationale**: 002's existing `find_overlap_groups` is already exactly the
connected-components algorithm this feature needs — the only differences are the
distance metric (pixel-space Euclidean vs. real-world haversine) and the minimum group
size (2, for "these two pins visually collide," vs. 3, "a training cluster requires at
least three people," Acceptance Scenario 2.2). Both existing call sites in
`generate_member_maps.py` (`_draw_pin_layer`/`_draw_photo_layer`) pass only `positions`
and `radius` positionally/by-keyword, so adding two optional trailing parameters with
behavior-preserving defaults is a strictly additive change — `tests/unit/
test_clustering.py`'s existing cases keep passing unmodified. `radius` (not a raw
`threshold`) is kept as the primary parameter to avoid touching either existing call
site; `cluster_radius_km / 2` at the pairing call site reproduces the "distance ≤
2×radius" formula transparently as a plain distance-threshold check.

**Alternatives considered**: A second, independent union-find implementation in
`rkby_pairing/clusters.py`. Rejected — this is the second consumer of the identical
~15-line algorithm, the same real-duplication bar 002's `rkby_records.py` and 005's
`canonical_match_keys` promotion both already cleared; duplicating it here would be
exactly the kind of anticipatory-turned-real duplication Principle II warns against
once it's happened twice. A density-based clustering library (e.g. scikit-learn's
DBSCAN). Rejected on Constitution IV grounds — a heavy dependency for a problem this
project's own ~15-line union-find already solves at this data scale (~200 members).

## §8 Report format, location, and photo handling (FR-008/009/013)

**Decision**: One stable-named file, `$RKBY_DATA_DIR/reports/rider_pairings.md` — no
season or timestamp in the filename. Every run fully overwrites it (idempotent
regeneration, like every other generated artifact), relying entirely on FR-014's
auto-commit into the `RKBY_DATA_DIR` git history to keep a previously hand-edited
version recoverable (spec.md Edge Cases: "the working copy no longer shows the
hand-edited version... it remains recoverable from the data repository's git
history"). Each mentioned person's photo (when their latest-season record's own
`photo` field points at an existing file) is embedded as a standard Markdown image
reference, path-relative from `reports/` to `seasons/<season>/<photo>`; when no photo
is on file, the person's line simply carries no image — unlike the map generator, this
report never substitutes the mascot placeholder (spec.md Edge Cases: "the report still
generates normally, simply without an image"). Contact info (name, address, phone
and/or email) is always shown in full per FR-009 — no field withheld.

**Rationale**: A stable filename matches spec.md's Edge Cases scenario literally — it
describes *overwriting the same file* and relying on git history, not writing
season-stamped files side by side (contrast with `generate_member_maps.py`'s
season-prefixed PNGs, which persist every season's own output simultaneously by
design — this report only ever concerns "the latest season," so there is nothing to
keep multiple copies of on disk). Reusing each record's own `photo` field directly
(rather than a placeholder) matches the person being displayed here always being a
*latest-season* record — the same record supplies name/address/phone/email/photo
together, so no cross-season photo lookup is ever needed even though the "has ridden
before" check (§3) does look across seasons.

**Alternatives considered**: Per-new-rider files (one Markdown file per person).
Rejected per spec.md's own Assumptions ("a single Markdown file... since
privacy-minimization does not apply here, there's no need to split it up"). Embedding
photos as base64 data URIs inside the Markdown. Rejected — plain relative-path image
links are what every Markdown viewer and this feature's own PDF renderer (§9) already
resolve correctly against the local filesystem, and base64 would bloat a
hand-editable text file for no benefit here (no need to ship the file standalone).

## §9 Markdown-to-PDF conversion (FR-012)

**Decision**: Two new pure-Python runtime dependencies — `markdown` (Markdown → HTML)
and `xhtml2pdf` (HTML → PDF, built on `reportlab`) — invoked from `rkby_pairing/pdf.py`
as a two-step conversion: render the report's current on-disk `.md` content to HTML,
then render that HTML (with image `src` paths resolved relative to the `.md` file's own
directory) to `reports/rider_pairings.pdf`.

**Rationale**: Both packages install from PyPI with no system-level native libraries
(no Cairo/Pango/GTK, no headless browser, no LaTeX toolchain, no `wkhtmltopdf` binary)
— the best fit for Constitution IV's "smallest footprint... well-maintained, widely
used" bar on a volunteer team's assorted machines (Linux/macOS/Windows) where `uv sync`
needs to "just work." `markdown` is the de facto standard pure-Python Markdown parser;
`xhtml2pdf` reuses `reportlab` (a mature, pure-Python PDF-generation library) under the
hood, so no image-format handling is reinvented — `Pillow` is already a project
dependency and satisfies `reportlab`'s own image needs. Doing the conversion as a
distinct, callable step (not folded into report generation) is what makes FR-012's
"independently of and without re-running the pairing computation" requirement trivial:
`--pdf-only` (contracts/cli-and-env.md) reads whatever `.md` content is currently on
disk — hand-edited or not — and never touches season data at all.

**Alternatives considered**: `weasyprint` (HTML/CSS → PDF). Rejected — while more
CSS-capable, it depends on Cairo/Pango/GDK-Pixbuf system libraries that aren't
guaranteed present on a volunteer's machine and complicate `uv sync`/`pyproject.toml`
portability across Linux/macOS/Windows, in tension with Constitution IV's
minimal-footprint bar for a project maintained without dedicated infrastructure
support. Shelling out to an external `pandoc` (optionally with a LaTeX or
`wkhtmltopdf` backend) binary via `subprocess`, mirroring `rkby_records.auto_commit`'s
existing `git` subprocess pattern. Rejected — `git` is already an assumed, required
part of this project's own data-repository workflow (`RKBY_DATA_DIR` is described as
git-backed throughout), whereas `pandoc`/a PDF backend would be this project's *first*
dependency on a tool outside the Python/`uv` toolchain purely for this one feature,
and its absence would silently break only the optional PDF path with an
environment-specific failure mode harder to diagnose than a plain `uv sync` dependency
resolution. Server-side/headless-browser rendering (e.g. Playwright/Chromium).
Rejected outright on Constitution IV grounds — far too heavy for a single-file,
single-run PDF export.

## §10 CLI surface (FR-012, contracts/cli-and-env.md)

**Decision**:

```bash
uv run scripts/generate_rider_pairings.py [--max-suggestions N] [--cluster-radius-km KM] [--pdf]
uv run scripts/generate_rider_pairings.py --pdf-only
```

`--pdf` (flag): after computing and writing the `.md` report as normal, also render
`reports/rider_pairings.pdf` from it. `--pdf-only` (flag): skip the pairing computation
entirely — read the existing `reports/rider_pairings.md` and render it to PDF; errors
(non-zero exit) if that file doesn't exist yet, since there is nothing to render.
`--max-suggestions`/`--cluster-radius-km` have no effect in `--pdf-only` mode (no
computation runs) — documented in the contract rather than raising, since a maintainer
re-running with old habitual flags shouldn't have to remember to drop them.

**Rationale**: Two clearly-named flags cover every FR-012 requirement (default
computation, computation + PDF, PDF-only-from-current-content) with the smallest CLI
surface, following `generate_member_maps.py`/`generate_interactive_map.py`'s existing
flag-based tuning pattern rather than introducing a subcommand structure this project
doesn't otherwise use.

**Alternatives considered**: A separate script entirely for PDF export (e.g.
`export_rider_pairings_pdf.py`). Rejected — Constitution II's "one script, one
artifact" reasoning treats the PDF as a rendering of the *same* artifact (the pairing
report), not a second artifact; splitting it into its own script would need to
duplicate config loading (`RKBY_DATA_DIR` resolution) for no real independence benefit,
whereas a mode flag on the existing script (already this project's pattern in spirit,
via `generate_interactive_map.py`'s optional `RKBY_BASEMAP_URL`-driven build variants)
keeps one entrypoint, one place to look.

## §11 Auto-commit scope (FR-014)

**Decision**: Auto-commit stages and commits exactly `reports/rider_pairings.md` — the
PDF is never staged (it's a derived, gitignored artifact, same treatment as the map
PNGs and 005's exported HTML report). A `--pdf-only` run performs no auto-commit at all
(nothing new was computed or written to a season record; the `.md` it read was either
already committed by a prior run or is a not-yet-committed hand-edit the maintainer is
choosing to export, not something this run should commit on their behalf).

**Rationale**: Directly matches FR-014's wording ("auto-commit the pairing report's
Markdown file... whenever the script writes or updates it") and the Assumptions
section's explicit "only the Markdown report is auto-committed... the exported PDF is
treated like this project's other rendered/derived output... gitignored, and not
itself committed."

## §12 Test fixtures

**Decision**: New `tests/fixtures/pairing_seasons/` directory — a multi-season
synthetic YAML fixture set covering: a new rider (0 previous seasons, geocoded) with
one or more nearby experienced Riders; a former-Rider-now-Service-Crew mentor
candidate (Acceptance Scenario 1.2); a new rider who is never suggested as a contact
for another new rider (Acceptance Scenario 1.3); an `excluded`/`ignore`d member and an
ungeocoded member, each absent from every role (Acceptance Scenario 1.5); an
unrecognized/blank-role record (§4); a birthday-unknown and a sex-unknown record
(ranking Edge Cases); an alias-linked identity spanning two seasons whose earlier
record shows role Rider (§3); and a tight three-plus-rider geographic group alongside a
non-rider living at the same location (User Story 2's Acceptance Scenarios).

**Rationale**: `tests/fixtures/report_seasons/` (feature 005) has `address: null` on
every record and no `num_previous_seasons` values — this feature can't reuse it without
either mutating a fixture set another feature's tests depend on staying exactly as-is,
or duplicating most of it anyway; a feature-scoped fixture directory is the existing
convention (005 itself introduced `report_seasons/` rather than reusing 002/001's
fixtures).
