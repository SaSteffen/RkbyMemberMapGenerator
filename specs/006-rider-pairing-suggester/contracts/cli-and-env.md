# Contract: CLI & Environment Variables

The external interface of `scripts/generate_rider_pairings.py` — what the maintainer
(and any future script) can rely on.

## Invocation

```bash
# Compute pairings for the latest season and write reports/rider_pairings.md
uv run scripts/generate_rider_pairings.py

# Same, tuned, and also export a PDF from the freshly-written Markdown
uv run scripts/generate_rider_pairings.py --max-suggestions 5 --cluster-radius-km 8 --pdf

# Skip computation entirely; render whatever reports/rider_pairings.md currently
# contains (including hand-edits) to reports/rider_pairings.pdf
uv run scripts/generate_rider_pairings.py --pdf-only
```

| Argument | Required | Format | Default | Behavior |
|---|---|---|---|---|
| `--max-suggestions` | no | positive integer | `3` | Upper bound on how many Suggested Pairings each New Rider gets (FR-006). No effect with `--pdf-only`. |
| `--cluster-radius-km` | no | positive number | `5` | Two current-season Riders are linked into the same Training Cluster when their home locations are within this many kilometers (FR-007). No effect with `--pdf-only`. |
| `--pdf` | no | flag (no value) | absent (no PDF) | After writing `reports/rider_pairings.md` as normal, also renders `reports/rider_pairings.pdf` from it (FR-012). |
| `--pdf-only` | no | flag (no value) | absent | Skips the pairing computation entirely and renders the report's *current* on-disk Markdown content to `reports/rider_pairings.pdf` (FR-012). Mutually pointless (but not rejected) alongside `--max-suggestions`/`--cluster-radius-km`, since no computation runs to apply them to. |

There is no season selector — this script only ever processes "the latest season"
(FR-001); there is no way to regenerate an older season's pairings.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Run completed. A season with zero New Riders and/or zero Training Clusters is a normal, expected outcome (still writes a report saying so), not a failure. |
| non-zero | Run aborted: missing/invalid `RKBY_DATA_DIR`, an existing persisted record failing schema validation (mirrors every other script's `InvalidExistingRecordError` handling), or `--pdf-only` requested when `reports/rider_pairings.md` doesn't exist yet (nothing to render). |

## Environment variables

| Variable | Required | Contains | Notes |
|---|---|---|---|
| `RKBY_DATA_DIR` | yes | Absolute path to the local, git-backed data repository root | Same variable every other script uses. Must contain a `seasons/` folder with at least one season for a default (non-`--pdf-only`) run to produce a non-trivial report. |

No intranet credentials are used or required, and no new network calls are made at
all — this script never talks to the Team Rynkeby intranet, the Nominatim geocoding
endpoint, or any tile server (FR-011). It only reads local YAML records and local photo
files already on disk.

## Auto-commit behavior

If `RKBY_DATA_DIR` is a git work tree, a run that writes/updates
`reports/rider_pairings.md` (i.e., every run except `--pdf-only`) stages and commits
exactly that one file — never `reports/rider_pairings.pdf`, which stays gitignored and
untouched by version control (research.md §11). A no-op (nothing staged) run creates no
commit; a commit failure is logged as a warning and never changes the run's exit code
— identical semantics to `rkby_records.auto_commit`'s existing behavior used by every
other script. `--pdf-only` never auto-commits anything, since it never writes to
`reports/rider_pairings.md`.

## Output contract

See `report-output.md` for the generated Markdown/PDF file's structure.
