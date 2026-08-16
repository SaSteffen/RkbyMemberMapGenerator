# Contract: CLI & Environment Variables

The external interface of `scripts/generate_member_maps.py` — what the maintainer (and
any future script) can rely on.

## Invocation

```bash
uv run scripts/generate_member_maps.py [--min-width-km KM] [--no-scale-bar]
```

Every season under `<RKBY_DATA_DIR>/seasons/` is processed in one run; there is no
season selector, no variant selector, and no other switch (FR-002, FR-018) — the two
below are the only CLI surface this script has, ever.

| Argument | Required | Format | Default | Behavior |
|---|---|---|---|---|
| `--min-width-km` | no | positive number | `50` | Lower bound, in kilometers, on the real-world width every generated map (overview and detail) must cover (FR-010). |
| `--no-scale-bar` | no | flag (no value) | absent (scale bar shown) | Suppresses the bottom-right scale indicator (FR-008/FR-009) on every map this run generates. |

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Run completed. Individual member skips (no address, unresolvable address, no photo) do **not** change the exit code — those are logged and expected (FR-006, SC-002), not run failures. |
| non-zero | Run aborted before or during writing: missing/invalid environment variables, or an existing persisted record failing schema validation (mirrors the scraper's `InvalidExistingRecordError` handling — refuses to write over data it can't trust). |

## Environment variables

| Variable | Required | Contains | Notes |
|---|---|---|---|
| `RKBY_DATA_DIR` | yes | Absolute path to the local, git-backed data repository root | Same variable the scraper uses. Must already exist and contain a `seasons/` folder with at least one season for this script to do anything (an empty `seasons/` folder is a valid, if uninteresting, run — nothing to process, exit `0`). |

No intranet credentials are used or required — this script never talks to the Team
Rynkeby intranet, only to the local data store, the Nominatim geocoding endpoint, and
the OSM tile server (research.md §2, §3).

## Third-party network calls

| Endpoint | What's sent | When |
|---|---|---|
| `https://nominatim.openstreetmap.org/search` | The `address` field's text, for one member, one time ever (per address — cached afterward) | Only for members whose record doesn't yet have `latitude`/`longitude` cached. |
| `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | Nothing but a tile coordinate — no member data of any kind | Only for tiles not already present in `<RKBY_DATA_DIR>/.tile_cache/`. |

No other member field (name, photo, phone, birthday) is ever sent anywhere — this is
the documented, narrowly-scoped exception to Principle I's "no third-party upload"
rule that spec.md's Assumptions section calls for (see plan.md Constitution Check).

## Auto-commit behavior

Mirrors the scraper's existing behavior (`specs/001-scraper-persistence/contracts/
cli-and-env.md` §Auto-commit behavior), scoped to what this feature writes: if
`RKBY_DATA_DIR` is a git work tree, a successful run stages and commits any
newly-cached `latitude`/`longitude` values under `seasons/*/applicants/`, plus a
first-time creation/update of the top-level `.gitignore`. `maps/` and `.tile_cache/`
are never staged — both are covered by that same `.gitignore` (FR-017). A run with
nothing new to cache creates no commit; a commit failure is logged as a warning and
never changes the run's exit code.

## Output contract

See `map-output.md` for the generated-file naming and folder-layout contract.
