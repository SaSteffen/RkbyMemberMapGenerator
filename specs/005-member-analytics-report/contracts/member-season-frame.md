# Contract: the member-season DataFrame

This is the interface between `rkby_report.frame.build_member_season_frame()` (the
one place all eligibility/age/distance/identity logic lives, research.md §2) and
everything downstream of it: `rkby_report.aggregate`'s summary/trend/retention
functions, `rkby_report.plots`'s chart builders, and the notebook's own cells. Every
downstream consumer depends on this shape and these guarantees — not on how the rows
were produced.

## Signature

```python
def build_member_season_frame(data_dir: Path) -> pandas.DataFrame: ...
```

- `data_dir`: same `RKBY_DATA_DIR` every other script reads (contracts below).
- Returns exactly the columns in data-model.md § Member-Season Observation, one row
  per (member, season) that passed the eligibility filter (excluded/ignore both
  false). No other filtering — a member missing a birthday, coordinates, or role is
  still a row, with the relevant column(s) null/`"unknown"` (see Guarantees).

## Guarantees

1. **Never silently drops a member for a missing field.** A null `birthday`, `sex`,
   `latitude`/`longitude`, or `role` produces a row with that field null (or an
   explicit `"unknown"` bucket) — never a missing row. Only `excluded`/`ignore`
   remove a member entirely (FR-002).
2. **One canonical identity per person, across every season.** `match_key` is always
   the *canonical* key (research.md §7) — two rows for the same real person, whose
   `match_key` changed between seasons via a recorded `alias_match_keys`, always share
   one `match_key` value in this frame. An *unrecorded* identity change is a known,
   accepted limitation (spec Edge Cases) — those rows keep their own distinct
   `match_key` values, same as the interactive map already treats them.
3. **`retained_next_season` is only ever computed against the immediately next
   discovered season.** For a member's row in the chronologically last discovered
   season, this column is `None` (unknown, not `False`) — there is no later season to
   check yet (spec Assumptions: retention is next-season-only, not any-later-season).
4. **Read-only.** This function never writes to any `.yaml` record and never performs
   a geocode lookup (FR-007) — it only reads `latitude`/`longitude` if already present.
5. **Deterministic given the same on-disk data.** Same `data_dir` contents in, same
   DataFrame out — no randomness, no dependence on wall-clock time (age is computed
   from each season's own fixed reference date, research.md §6, not "today").

## What callers must not assume

- Column order is not part of the contract, only column *names and types* (data-model.md).
- `age_bucket`/`distance_bucket`/`role`/`sex` string values are exactly the fixed
  vocabulary in `rkby_report.buckets` plus the raw `role`/`sex` text found in the
  data — callers must not assume a closed enum for `role`/`sex` beyond the possibility
  of `"unknown"` (spec Edge Cases: unrecognized role values are their own category).
