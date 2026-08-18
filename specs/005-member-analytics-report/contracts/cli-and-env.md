# Contract: CLI & Environment Variables

The external interface of `scripts/report_member_analytics.ipynb` — a notebook, not a
CLI script, so "invocation" means how it's opened/run and how its output is exported.

## Running it

```bash
uv run --with jupyter jupyter lab scripts/report_member_analytics.ipynb
```

Then, inside Jupyter: **Run All**. No CLI arguments and no interactive prompts —
every season under `<RKBY_DATA_DIR>/seasons/` is loaded and analyzed on every run
(mirrors 003's "no season selector, no variant selector" precedent). There is no
notion of a non-zero exit code for a notebook; a cell raising an exception (e.g.
`RKBY_DATA_DIR` unset) stops execution at that cell and shows the traceback inline,
the same as any other notebook error.

## Environment variables

| Variable | Required | Contains | Notes |
|---|---|---|---|
| `RKBY_DATA_DIR` | yes | Absolute path to the local, git-backed data repository root | Same variable every other script uses. Must already exist and contain a `seasons/` folder with at least one season (an empty `seasons/` folder produces an empty frame and empty charts, not an error — mirrors 002's "nothing to process" handling). |

No intranet credentials are used or required, and no new network calls are made at
all — this feature never talks to the Team Rynkeby intranet, Nominatim, or any tile
server; it only reads what's already on disk (FR-007).

## Exporting

```bash
uv run jupyter nbconvert --to html --execute \
  --TagRemovePreprocessor.remove_cell_tags='{"remove-cell"}' \
  scripts/report_member_analytics.ipynb \
  --output-dir "$RKBY_DATA_DIR/reports"
```

Produces one self-contained `.html` file under `$RKBY_DATA_DIR/reports/` (created if
missing) — every chart and summary table from a fresh, current-data execution, in one
file a recipient can open in any browser without Jupyter, Python, or this repo
installed (FR-014). This file:

- Is never written inside the git repository — always under `RKBY_DATA_DIR`, gitignored
  the same way `maps/`/`.tile_cache/`/`interactive_map/` already are (research.md §4,
  §10).
- Shows aggregated counts, rates, and distributions only — never a per-member roster
  of names alongside personal fields (FR-015).
- Never contains the FR-017 data-gap list: the notebook cell that displays it carries
  a `remove-cell` tag, and `--TagRemovePreprocessor.remove_cell_tags` strips that cell
  (source and output alike) before the HTML is written (research.md §11). Omitting
  this flag would leak that list into the export — it is not optional.

## Keeping the committed notebook output-free

A `nbstripout` pre-commit hook (research.md §4) strips every cell's output from
`report_member_analytics.ipynb` before it can be committed — running the notebook
locally against real data and saving it never risks committing real member-derived
numbers or charts. This is enforced by tooling, not left to convention.

This is a different guarantee from the `remove-cell` tag above: `nbstripout` governs
what reaches **git** (no cell's output, ever); the tag governs what reaches the
**exported HTML** (every cell except the one tagged `remove-cell`). A maintainer
running the notebook interactively in Jupyter sees the FR-017 data-gap list normally
either way — neither mechanism hides anything from them, only from git and the export
respectively.

## Data contract this feature depends on

Reads, per season, exactly what 001/002 already guarantee:

1. `<RKBY_DATA_DIR>/seasons/<season-label>/applicants/*.yaml`, schema-valid per
   `applicant_record.schema.json`.
2. `excluded`/`ignore` flags present and accurate (001's contract) — this feature
   enforces the skip itself (FR-002), same as every other consuming script does.
3. `latitude`/`longitude`, when present, already geocoded and cached by a prior
   `generate_member_maps.py` run (002) — this feature never geocodes anything itself
   (FR-007).

This feature writes nothing back to any of the above.
