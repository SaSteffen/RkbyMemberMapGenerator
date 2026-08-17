# Contract: CLI & Environment Variables

The external interface of `scripts/generate_interactive_map.py`.

## Invocation

```bash
uv run scripts/generate_interactive_map.py
```

No CLI arguments at all (FR-002: no season selector, no variant selector — this
script has exactly one artifact and one behavior, unlike `generate_member_maps.py`'s
two tuning flags). Every season under `<RKBY_DATA_DIR>/seasons/` is bundled into the
one generated artifact in every run.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Run completed. Individual season-record skips (no address, unresolvable address) do **not** change the exit code — logged and expected (FR-005, SC-007), not run failures. A run where every season has zero eligible members still exits `0` and produces a (near-empty) artifact. |
| non-zero | Run aborted before or during writing: missing/invalid `RKBY_DATA_DIR`, an existing persisted record failing schema validation, or `frontend/interactive-map/dist/index.html` missing (the frontend hasn't been built — see data-model.md § Frontend Build Output). |

## Environment variables

| Variable | Required | Contains | Notes |
|---|---|---|---|
| `RKBY_DATA_DIR` | yes | Absolute path to the local, git-backed data repository root | Same variable the scraper and `generate_member_maps.py` already use. Must already exist; an empty (or season-less) `seasons/` folder is a valid, if uninteresting, run. |

No intranet credentials are used or required — same as `generate_member_maps.py`,
this script only talks to the local data store, Nominatim, and the OSM tile server.

## Third-party network calls

Identical set and payload discipline to `generate_member_maps.py`
(`specs/002-map-generator/contracts/cli-and-env.md` § Third-party network calls),
reusing the exact same code paths and the exact same on-disk caches
(`.tile_cache/`, each record's `latitude`/`longitude`) — a warm cache from a prior
run of *either* script benefits the other:

| Endpoint | What's sent | When |
|---|---|---|
| `https://nominatim.openstreetmap.org/search` | The `address` field's text, for one member, one time ever (per address — cached afterward) | Only for eligible members whose record doesn't yet have `latitude`/`longitude` cached. |
| `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | Nothing but a tile coordinate — no member data of any kind | Only for tiles covering the one combined basemap image (research.md §2) not already present in `<RKBY_DATA_DIR>/.tile_cache/`. |

No other member field (name, photo, phone, birthday, address, email, etc.) is ever
sent to either endpoint, and none of them are written into the generated artifact
beyond what data-model.md's Bundled Map Data table lists (research.md §12).

## Auto-commit behavior

Mirrors `generate_member_maps.py`'s existing behavior: if `RKBY_DATA_DIR` is a git
work tree, a successful run stages and commits any newly-cached
`latitude`/`longitude` values under `seasons/*/applicants/`, plus a first-time
creation/update of the top-level `.gitignore` (adding `interactive_map/` alongside
the existing `maps/`/`.tile_cache/` entries). `interactive_map/` itself is never
staged. A run with nothing new to cache creates no commit; a commit failure is
logged as a warning and never changes the run's exit code.

## Output contract

See `output-artifact.md` for the generated folder layout and `map-data.schema.json`
for the exact shape of the bundled data payload.
