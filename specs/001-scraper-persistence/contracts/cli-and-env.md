# Contract: CLI & Environment Variables

The external interface of `scripts/scrape_applicants.py` — what other tooling, the
maintainer, and future scripts consuming the persisted data can rely on.

## Invocation

```bash
uv run scripts/scrape_applicants.py [--season SEASON]
```

| Argument | Required | Format | Behavior |
|---|---|---|---|
| `--season` | no | `YYYY-YY` or `YYYY/YY` (e.g. `2025-26` or `2025/26`) | Season to scrape. Normalized internally to hyphen form. When omitted, defaults per FR-022 (research.md §13). |

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Run completed. Note: individual photo-fetch failures or logged conflicts do **not** change the exit code — those are recoverable, retried/human-reviewable situations (see run log), not run failures. |
| non-zero | Run aborted before or during writing: missing/invalid environment variables (FR-023), authentication failure, a page-fetch failure mid-pagination (FR-018 rollback), or an existing persisted record failing schema validation (FR-017). In every non-zero case, the season's persisted data on disk is unchanged from before the run started. |

## Environment variables

| Variable | Required | Contains | Notes |
|---|---|---|---|
| `RKBY_INTRANET_USERNAME` | yes | Intranet login username | Never logged, never written to any file. |
| `RKBY_INTRANET_PASSWORD` | yes | Intranet login password | Never logged, never written to any file. |
| `RKBY_DATA_DIR` | yes | Absolute path to the local, git-backed data repository root | Must already exist as a directory (spec Assumptions: provisioning it is out of scope). All reads/writes for this feature happen under `<RKBY_DATA_DIR>/seasons/...`. |

All three are validated present *and* minimally usable (e.g. `RKBY_DATA_DIR` exists and
is a directory) before any network request or file write (FR-023). Missing/invalid →
exit non-zero with a message naming the missing/invalid variable(s); no partial run.

## Auto-commit behavior

If `RKBY_DATA_DIR` is a git repository (auto-detected — no configuration needed), a
successful run automatically stages and commits the changes it made under
`seasons/<season-label>/` at the end of the run (research.md §14). If `RKBY_DATA_DIR`
is not a git repository, this step is skipped silently — nothing else about the run
changes. A run that makes no changes (e.g. a repeat run with nothing new upstream)
creates no commit. A failure in the commit step itself (e.g. no git committer identity
configured) is logged as a warning in the run log and does **not** change the run's
exit code — the persisted data on disk is already valid and complete regardless of
whether the commit succeeded.

## Data contract for downstream scripts

Any other script (map generator, pairing suggester, birthday calendar — out of scope
for this feature) that later reads this persisted data should:

1. Read `<RKBY_DATA_DIR>/seasons/<season-label>/applicants/*.yaml`.
2. Validate each against `applicant-record.schema.json` (or trust it, since this
   feature guarantees every file it writes is schema-valid).
3. **Skip any record where `ignore == true` or `excluded == true`** — per FR-012, this
   feature only guarantees those flags are present and accurate; enforcing the skip is
   each consuming script's own responsibility.
4. Resolve `photo` (if non-null) as a path relative to that same season folder.

This file is the interface contract those future scripts are written against; this
feature does not implement any of those scripts itself.
