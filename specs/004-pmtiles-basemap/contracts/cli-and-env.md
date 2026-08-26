# Contract: CLI & Environment Variables

The external interface of `scripts/generate_interactive_map.py`. Supersedes
`specs/003-interactive-photo-map/contracts/cli-and-env.md` for the fields listed
below; everything else in that document (invocation, no CLI args, `pnpm`
prerequisite, auto-commit behavior) is unchanged by this feature.

## Invocation

```bash
uv run scripts/generate_interactive_map.py
```

Unchanged: no CLI arguments (FR-002 of spec 003).

## New required input: the PMTiles basemap file

| Path | Required | Contains |
|---|---|---|
| `<RKBY_DATA_DIR>/basemap.pmtiles` | yes | One maintainer-supplied PMTiles v3 archive (data-model.md § PMTiles Basemap File) |

Not an environment variable — a fixed, documented file path under the existing
`RKBY_DATA_DIR`, checked before any other generation work.

Exit codes (supersedes spec 003's table — adds one new failure cause):

| Code | Meaning |
|---|---|
| `0` | Run completed, same conditions as spec 003 (per-record skips don't change exit code). |
| non-zero | Every spec-003 abort condition, **plus**: `<RKBY_DATA_DIR>/basemap.pmtiles` missing, unreadable, or failing the header check (FR-003, data-model.md § PMTiles Basemap File § Validation) — checked before the `pnpm` build step, so a missing basemap file fails fast without waiting on a frontend build. |

## Third-party network calls (changed)

Supersedes spec 003's table:

| Endpoint | What's sent | When |
|---|---|---|
| `https://nominatim.openstreetmap.org/search` | The `address` field's text, for one member, one time ever (per address — cached afterward) | Only for eligible members whose record doesn't yet have `latitude`/`longitude` cached. **Unchanged by this feature.** |
| ~~`https://tile.openstreetmap.org/{z}/{x}/{y}.png`~~ | — | **Removed.** The interactive map no longer fetches or bakes OpenStreetMap raster tiles at generation time (FR-002, SC-001) — its basemap now comes entirely from the maintainer-supplied local `basemap.pmtiles` file. `generate_member_maps.py` (a separate script) still uses this endpoint for its own static maps; unaffected by this feature. |

No other member field is ever sent to either remaining endpoint, matching spec
003's existing minimization guarantee unchanged.

## Output contract

See `output-artifact.md` for the generated folder layout and
`map-data.schema.json` for the exact shape of the bundled data payload — both
superseded for this feature relative to their spec-003 versions.
