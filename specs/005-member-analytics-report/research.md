# Phase 0 Research: Member Analytics Report

## §1. Output medium & execution environment

**Decision**: A Jupyter notebook, `scripts/report_member_analytics.ipynb`, run via
`uv run --with jupyter jupyter lab` (or any Jupyter-compatible editor pointed at the
project's `.venv`), executed top-to-bottom with "Run All".

**Rationale**: The request named this format directly ("what i want is osmething that
can for instance be a python notebook, anything easy to start and export") — a
notebook is the standard, well-maintained, widely-used way to get exactly that:
inline charts next to the code that produced them, re-runnable cell-by-cell while
exploring, and a built-in path to a shareable static export (§2). No lighter-weight
alternative gets both "easy to start, see charts inline" and "exportable to something
a non-technical teammate can open" with less machinery.

**Alternatives considered**:
- *A plain CLI script writing PNG files* (like `generate_member_maps.py`): rejected —
  loses the notebook's explicit request and its interactive, cell-by-cell exploration
  value; would need its own ad hoc multi-chart layout/export logic that Jupyter+
  nbconvert already provides for free.
- *A small local web dashboard* (e.g. `streamlit`/`dash`): rejected — a running
  server is a much heavier dependency than Constitution IV's "smallest footprint"
  allows for a single-maintainer, run-on-demand tool, and isn't what was asked for.

## §2. Compute/render split (how this satisfies Constitution V in a notebook)

**Decision**: Every piece of logic that can be *wrong* — eligibility filtering,
age-at-season, distance, cross-season identity/retention matching, aggregation into
season summaries/trends/retention tables — is a plain, pure Python/pandas function in
`scripts/rkby_report/{frame,aggregate,geo,buckets}.py`, fully covered by `pytest`
against synthetic fixtures, written test-first. The notebook's cells, and
`rkby_report/plots.py`'s chart-builder functions, only call those already-tested
functions and hand the result to matplotlib — they don't decide anything themselves.

**Rationale**: Notebook cells aren't natural `pytest` units, but Constitution V is
NON-NEGOTIABLE and applies to "new functionality," not to "every line in every file."
Splitting compute from render lets 100% of the actual risk (a wrong retention number,
a member silently dropped instead of bucketed as "unknown") live in code that's
directly unit-testable, while the notebook and the plotting layer — which can only be
*visually* wrong, not *numerically* wrong, once fed correct data — get lighter
smoke-level tests (a chart builder runs without raising, given synthetic aggregated
input). This is the same split 002 already uses: its CLI's `main()` orchestration
isn't exhaustively unit-tested either, because the logic that can actually be wrong
(projection math, clustering, geocoding, rendering) already is, in `rkby_maps/`.

**Alternatives considered**:
- *Test the notebook itself* (e.g. `nbconvert --execute` in CI, or `nbval`): rejected
  as the primary test strategy — adds a new dependency and a slow, all-or-nothing
  check that can't isolate *which* computation is wrong. Kept only as a manual
  end-to-end sanity check in quickstart.md, on top of (not instead of) the real
  `pytest` coverage.

## §3. Charting library

**Decision**: `matplotlib` only.

**Rationale**: Every chart this feature needs (bar charts for role/gender/age-bucket/
distance-bucket counts, line charts for season-to-season trends, bar charts for
retention rates and their splits) is a standard matplotlib chart type. It's the most
widely-used, best-maintained Python plotting library and pandas already has
first-class `.plot()` integration with it — no extra glue code needed.

**Alternatives considered**:
- *`seaborn`*: rejected — a thin convenience layer over matplotlib for exactly the
  chart types this feature needs; would be a second dependency for no capability this
  feature actually requires (Constitution IV).
- *`plotly`*: rejected — heavier, aimed at interactive/web-embedded charts; this
  report's charts are static, viewed inside the notebook or an exported HTML
  snapshot, not embedded in a live web page.

## §4. Keeping real data out of git (the notebook-output leak risk)

**Decision**: Add `nbstripout` as a dev-only dependency and wire it in as a new
`pre-commit` hook (alongside the existing ruff/Conventional-Commit hooks in
`.pre-commit-config.yaml`) so every cell's output is stripped from
`report_member_analytics.ipynb` before it can be committed. Separately, the *executed*
report a maintainer actually wants to look at or hand to someone is written by the
export step (§6) to a new `reports/` folder inside `RKBY_DATA_DIR` — a sibling of
`seasons/`/`maps/`/`interactive_map/`, gitignored via the same mechanism 002 already
uses (`data-model.md`'s auto-managed `<RKBY_DATA_DIR>/.gitignore`) — never inside the
git repo at all.

**Rationale**: A `.ipynb` file embeds every cell's rendered output (chart images,
printed tables) directly in the JSON that gets saved to disk. Running this notebook
locally against real data and then `git add`-ing it — an easy, natural mistake — would
otherwise commit real member-derived distributions straight into git history, which
Constitution Principle I (NON-NEGOTIABLE) flatly forbids. Relying on "always clear
outputs before saving" as a human convention isn't a strong enough guarantee for a
NON-NEGOTIABLE principle; a pre-commit hook makes it structurally impossible instead
of merely a habit. This mirrors 001/002's existing pattern of using tooling (schema
validation, fill-empty-only writes) to enforce a privacy/correctness rule rather than
trusting memory alone.

**Alternatives considered**:
- *Convention only ("always clear outputs")*: rejected — exactly the kind of
  easy-to-forget manual step Constitution I's NON-NEGOTIABLE status argues against
  relying on.
- *Store the notebook outside git entirely*: rejected — then the actual orchestration
  code (which cells exist, what they call) isn't version-controlled at all, unlike
  every other script in this repo.

## §5. Hamburg city-center reference point & distance metric

**Decision**: A single fixed constant, `HAMBURG_CENTER = (53.5507, 9.9930)` (Hamburg
Rathaus/city hall — the conventional "city center" landmark), defined once in
`rkby_report/geo.py`. Distance is straight-line (great-circle/haversine), computed
in-house as a small pure function; no new dependency.

**Rationale**: The spec (Assumptions) already settled on "a single fixed landmark
coordinate" and "straight-line, not driving distance" — this just picks the concrete
point and confirms the implementation approach. Haversine distance from a lat/lon pair
is ~10 lines of standard-library math (`math.radians`/`sin`/`cos`/`atan2`), exactly the
kind of well-understood formula 002 already chose to implement in-house (Web Mercator
projection) rather than add a dependency for (Constitution IV).

**Alternatives considered**:
- *`geopy`* (or similar): rejected — a whole library for one formula this project
  already has precedent for writing directly.
- *A driving-distance API*: rejected outright — a new third-party network call for
  every member, in tension with Constitution I's "no third-party upload" default (the
  only carved-out exception is address-text geocoding, and only for producing
  coordinates in the first place, not for measuring distances between them), and
  contradicts FR-007's "no new network calls" requirement.

## §6. Age-at-season reference date

**Decision**: For a season labeled `YYYY_YY` (e.g. `2025_26`), age is computed as of
July 1 of the second year (`20YY`, e.g. 2026-07-01) — the month the ride to Paris
actually happens (REQUIREMENTS.md), i.e. each member's age *during that season's ride*,
not at scrape time or at today's date.

**Rationale**: The spec's Assumptions already settled on "age as of that season, not
today" — this picks one fixed, consistent reference date per season so every member in
a given season is compared on the same basis, and ties it to the one date in a season
that's actually meaningful (ride month) rather than an arbitrary Jan 1.

**Alternatives considered**:
- *Season-label's first year, Jan 1*: rejected — no more "correct" than the ride date,
  and less meaningful (nothing happens for the team on that date).
- *Age at scrape time*: rejected — scrape date is an artifact of *when the maintainer
  happened to run the scraper*, not a property of the season itself; two different
  scrapes of the same season could otherwise disagree.

## §7. Reusing cross-season identity resolution

**Decision**: Promote `rkby_interactive_map/merge.py`'s private
`_canonical_match_keys(eligible_by_season) -> dict[str, str]` into
`scripts/rkby_records.py` as a public `canonical_match_keys()`, unchanged in behavior.
`merge.py` is updated to import and call the shared version instead of defining its
own copy. `rkby_report/frame.py` calls the same shared function to resolve each
member's canonical identity across seasons before computing `retained_next_season`.

**Rationale**: The function is a pure transform over `alias_match_keys`/`match_key`
fields already on every record — it has no dependency on the interactive map's
stricter "must have resolved coordinates" eligibility filter (§8), so it's directly
reusable as-is. Two independent features now need the exact identical logic; that's
precisely the "duplication is real, not anticipated" threshold Constitution Principle
II sets for factoring something into the shared module — the same threshold that
justified creating `rkby_records.py` in the first place (002's research.md §10). This
is a pure refactor: `merge.py`'s existing test coverage for this function must keep
passing unmodified in behavior, just re-pointed at the shared import.

**Alternatives considered**:
- *Re-implement the same resolution logic inside `rkby_report/`*: rejected — would be
  the exact kind of real, immediate duplication Principle II says to factor out, not
  anticipate.
- *Import `_canonical_match_keys` directly from `rkby_interactive_map.merge`*:
  rejected — reaches into another feature's private (underscore-prefixed) internal
  function and its internal package, coupling two otherwise-independent scripts
  instead of depending on the one module that's explicitly meant to be shared.

## §8. Eligibility filter is narrower than the interactive map's

**Decision**: `rkby_report/frame.py` defines its own eligibility filter — a record is
included whenever `excluded` is false and `ignore` is false. Unlike
`rkby_interactive_map/merge.py`'s `_resolve_eligible_records`, it does **not** also
require a non-null `address` or successful geocoding, and it never calls
`geocode_record_if_needed` (or writes anything back to a record).

**Rationale**: The interactive map needs every member it shows to have plottable
coordinates, so its stricter filter (and its side-effecting geocode-and-cache-on-read
step) makes sense there. This report's role/age/gender views (FR-003/FR-004/FR-005)
have no such requirement — a member missing only their address or geocode should still
be counted everywhere except the distance view, where they fall into the explicit
"unknown/not geocoded" category (FR-006). Reusing the stricter filter would silently
undercount every other view, and reusing the geocode-on-read behavior would violate
FR-007's "no new geocoding lookups, read-only" requirement outright.

**Alternatives considered**:
- *Reuse `_resolve_eligible_records` as-is*: rejected for the reasons above — wrong
  eligibility semantics for four of this feature's five views, and a read/write
  requirement conflict with FR-007.

## §9. Age and distance bucket boundaries

**Decision**: Fixed constants in `rkby_report/buckets.py`:
- Age brackets: `<20`, `20-29`, `30-39`, `40-49`, `50-59`, `60+`, plus `unknown` for no
  birthday on file.
- Distance brackets (from Hamburg center): `0-10km`, `10-25km`, `25-50km`, `50-100km`,
  `100km+`, plus `unknown/not geocoded` for no coordinates on file.

**Rationale**: The spec asks for age/distance *splits* without prescribing exact
boundaries (a reasonable-default area, not a scope-changing decision) — these are
standard decade-wide demographic brackets and distance bands sized to the "relatively
wide area around Hamburg" REQUIREMENTS.md describes, each wide enough to hold a
meaningful member count per bracket for a ~200-person team without over-fragmenting
the charts. Both live as named constants in one file so they're trivial to retune
later without touching any computation logic.

**Alternatives considered**:
- *Continuous histograms with library-chosen bins*: rejected as the primary view —
  auto-chosen bin edges would shift between runs/seasons as the data changes, making
  season-to-season comparison (User Story 2) and retention splits (User Story 3)
  harder to read consistently; fixed brackets stay stable across every run.

## §10. Export path

**Decision**: `uv run jupyter nbconvert --to html --execute
scripts/report_member_analytics.ipynb --output-dir "$RKBY_DATA_DIR/reports"`
(documented in `contracts/cli-and-env.md` and `quickstart.md`) — a fresh, from-source
execution that never touches the committed notebook's own saved cell state.

**Rationale**: `nbconvert --execute` runs every cell fresh from the current data and
writes a single self-contained HTML file — exactly FR-014's "single file that can be
opened and read without re-running any analysis," satisfied by handing that one HTML
file to someone, and it comes for free once `nbconvert` (already needed to open/run
the notebook at all) is a dependency. Writing straight to `$RKBY_DATA_DIR/reports/`
means the export step can never produce a file inside the git repo by construction.
HTML (over PDF) was subsequently confirmed directly with the maintainer via
`/speckit-clarify` (spec.md § Clarifications, 2026-08-18) — this section's reasoning
is what that confirmation ratified.

**Alternatives considered**:
- *Export the currently-open notebook's already-rendered outputs* (no `--execute`):
  rejected — could silently export stale results if the maintainer forgot to re-run a
  cell after a data change; `--execute` guarantees the export matches current data.
- *PDF output*: left available as an option (`nbconvert` supports `--to pdf`) but not
  the default — PDF export requires a LaTeX toolchain, an unnecessary heavy
  dependency for a single-maintainer tool when HTML already satisfies "open and read"
  in any browser.

## §11. FR-017: the notebook-only data-gap list, and keeping it out of the export

**Decision**: `rkby_report.aggregate.data_gaps(df) -> pandas.DataFrame` — a pure
function over the already-built frame (§6-§8) that returns one row per (member,
season) with at least one missing field needed by a view (`role` unknown, `sex`
unknown, `age_bucket` unknown, or `distance_bucket` unknown/not-geocoded), with a
`missing_fields` column listing which. The notebook cell that displays it is tagged
`remove-cell` in the notebook's cell metadata. The export command (research.md §10,
`contracts/cli-and-env.md`) is extended with nbconvert's built-in tag-stripping
preprocessor:

```bash
uv run jupyter nbconvert --to html --execute \
  --TagRemovePreprocessor.remove_cell_tags='{"remove-cell"}' \
  scripts/report_member_analytics.ipynb --output-dir "$RKBY_DATA_DIR/reports"
```

**Rationale**: FR-017 requires this list to be visible while working in the notebook
but absent from the FR-014 export. `nbconvert --execute` runs and displays *every*
cell by default, including this one — so without an explicit exclusion mechanism, the
gap list would leak straight into the exported HTML, contradicting FR-017 and FR-015
alike. `TagRemovePreprocessor` is nbconvert's own built-in, first-party mechanism for
exactly this "show it live, strip it from the export" need — no new dependency, since
`nbconvert` is already required for the export path itself (§10). It's orthogonal to,
and layered on top of, `nbstripout`'s pre-commit stripping (research.md §4):
`nbstripout` keeps *every* cell's output out of what gets *committed to git*;
`--TagRemovePreprocessor` keeps *this one cell* out of what gets *exported*. A
maintainer running the notebook interactively still sees the gap list normally — only
the committed source (no outputs at all, any cell) and the exported HTML (every cell
except this one) are restricted, each by its own mechanism.

**Alternatives considered**:
- *A separate, untracked cell the maintainer manually deletes before exporting*:
  rejected — relies on remembering a manual step for a NON-NEGOTIABLE privacy rule
  (Constitution Principle I), the same reasoning research.md §4 already rejected for
  the commit-output problem.
- *Print the gap list to `stderr`/logging instead of a normal cell output*: rejected —
  `nbconvert --execute` still captures and embeds a cell's stderr stream in the
  export by default; this doesn't actually solve the leak without the same kind of
  tag-based (or equivalent config-based) exclusion, so it adds complexity without
  removing the real fix.
- *Write the gap list to the season's `logs/` folder instead of showing it in the
  notebook*: rejected — FR-017 asks for it in the notebook specifically, and writing
  into `seasons/<label>/logs/` would break this feature's read-only-except-`reports/`
  footprint (data-model.md § Local Data Repository) for no benefit over a cell the
  maintainer already has open.
