# Phase 0 Research: Applicant Scraper & Data Persistence

Each unknown from the Technical Context is resolved below as Decision / Rationale /
Alternatives considered.

## 1. HTTP client & session handling

**Decision**: `requests`, using a single `requests.Session()` for the whole run (login
once, reuse cookies for every page + photo fetch).

**Rationale**: De facto standard, well-maintained, tiny API surface, and its `Session`
object gives free cookie-jar handling for the login → paginated-fetch → photo-fetch
flow without any extra state management. Matches Constitution IV (minimal, well-known
dependency).

**Alternatives considered**: `httpx` (adds async support this single-run CLI script
doesn't need); stdlib `urllib` (would mean hand-rolling cookie/session handling for no
real benefit).

## 2. Authentication mechanism

**Decision**: Session-cookie auth via an HTML login form: POST username/password (read
from `RKBY_INTRANET_USERNAME` / `RKBY_INTRANET_PASSWORD`) to the intranet's login
endpoint, keep the resulting session cookie on the shared `requests.Session`, then issue
the AJAX/page requests as that authenticated session. If the response to the first
authenticated request looks like a login page instead of applicant data, treat it as an
auth failure and abort before writing anything.

**Rationale**: Matches how the site is described (a standard members-only intranet with
its own login), and the spec's own Assumptions section defers the exact form fields/
endpoint to implementation-time empirical discovery — this isn't knowable from the spec
or without live authenticated access, which planning must not do (Principle I: no real
member data / credentials touched outside a real run). The chosen design isolates this
behind one `IntranetClient.login()` call so the rest of the code only depends on "we
have an authenticated session," not on the exact form mechanics.

**Alternatives considered**: A pre-obtained/pasted session token — rejected; the spec's
Assumptions explicitly state the tool performs its own login rather than requiring a
pre-obtained token.

**Follow-up needed during implementation**: a one-time interactive/manual inspection of
the real login form and the `team_application_manager.php` response shape (HTML
fragment vs. JSON) to pin down selectors, which then get captured as the obfuscated
fixtures FR-021 requires. This is implementation work, not a planning blocker.

## 3. Applicant list response shape & parsing

**Decision**: Treat the `team_application_manager.php` response as an HTML fragment
(consistent with the `tableSettings=true` query param, typical of a server-rendered
admin table refreshed via AJAX) and parse it with `BeautifulSoup4` using the stdlib
`html.parser` backend (no `lxml` dependency needed).

**Rationale**: `bs4` is the standard, well-maintained choice for exactly this kind of
"pull structured rows out of an HTML table" task, and `html.parser` avoids adding a
compiled dependency. Encapsulating parsing behind one `parse_applicant_rows(html) ->
list[ScrapedRow]` function means that if the real response turns out to be JSON
instead, only that one function changes.

**Alternatives considered**: `lxml` (faster, but a heavier/compiled dependency for a
low-volume, run-occasionally script — not justified); regex scraping (too fragile for
HTML).

**Open question for implementation**: whether every field (address, phone, birthday) is
present directly in the list-table row, or whether some require an additional
per-applicant detail request. Resolved empirically; the `IntranetClient`/parsing split
already anticipates an optional per-applicant detail fetch without changing the
persistence layer.

## 4. Full-resolution photo retrieval

**Decision**: Model as a two-step fetch per retained applicant: (1) resolve the
full-resolution image URL from the same row/detail HTML (the anchor the thumbnail's
popup link points to), (2) `GET` that URL and stream the bytes to disk. Both steps live
behind one `fetch_photo(row) -> bytes | None` call; any failure in either step is caught
there, logged as a warning, and returns `None` rather than raising — satisfying
FR-005's "one applicant's photo failure must not affect anything else."

**Rationale**: Keeps the all-or-nothing rollback (FR-018, page-fetch failures) cleanly
separate from the independently-retryable, non-fatal photo failures (FR-005) by giving
them different failure-handling code paths from the start.

**Alternatives considered**: Treating photo fetch as fatal to the whole run — rejected,
contradicts FR-005 and the clarification answer on partial photo failure.

## 5. Season label ↔ intranet season id resolution

**Decision**: Fetch the applicants page's season-selector HTML once per run and parse
its links to build a `{label: season_id}` map (the team id is read from the same
links), then resolve the requested/default label against that map. Error clearly if the
label isn't found (e.g., site hasn't opened the season yet).

**Rationale**: Avoids hardcoding a `season label → numeric id` table that would need a
manual code change every year; the mapping already exists on the page the tool visits
anyway. This is *not* the "auto-discover all seasons" feature the spec's Assumptions
explicitly puts out of scope — it's the minimum lookup needed to resolve the one label
being scraped this run, done as a side effect of visiting a page the tool already needs.

**Alternatives considered**: Hardcoding `TEAM_ID = 740` and a static season-label→id
table in source — rejected, brittle (silently wrong every new season until someone
remembers to update it) and no more private than reading it off the same page.

## 6. Persistence format & granularity

**Decision**: One YAML file per applicant record (filename = the normalized
first+last-name matching key, e.g. `jane-doe.yaml`), plus one photo file per applicant,
inside a per-season folder:

```
<RKBY_DATA_DIR>/seasons/<season-slug>/
├── applicants/
│   ├── jane-doe.yaml
│   └── john-smith.yaml
├── photos/
│   ├── jane-doe.jpg
│   └── john-smith.jpg
└── logs/
    └── 2026-08-15T120000.log
```

Each YAML file carries a `# yaml-language-server: $schema=...` header line pointing at
the JSON Schema (see contracts/), so editors like VS Code get inline validation and
autocomplete while hand-editing — directly serving the "schema to help with editing"
ask.

**Rationale — this is the "better history-aware format" the user asked about**: one
file per person means the *existing git repository* (already required by the spec to
be a git repo) gives free, precise history: `git log <file>` shows exactly when that
one person's data changed and by what diff, hand-edits and scraper-writes are both
visible as normal commits/diffs, and two people's edits never collide in the same file.
A single big per-season JSON/YAML blob would make every scraper run touch one giant
file, burying human edits in noisy diffs and making `git blame` on one person useless.
Per-record files also make the overwrite-protection and "ignore" rules (FR-009, FR-011)
trivial to reason about and test: each rule is "read one small file, maybe write one
small file," not "surgically patch one field inside a large structure."

**Rationale — YAML over JSON**: both satisfy FR-019 ("human-readable... hand-editable");
YAML was picked because it supports comments (useful for a maintainer leaving a note on
a record) and has less punctuation noise for a non-developer hand-editing a birthday or
address. `PyYAML`'s parsed output is a plain `dict`, so the same JSON Schema validates
both without needing a YAML-specific schema language.

**Alternatives considered**: one JSON/YAML file per season (rejected above); a CSV per
season (rejected — doesn't cleanly support the nested excluded/ignore/photo-ref shape
FR-012 requires, and multi-line address fields are awkward in CSV); a SQLite database
(rejected outright — not human-hand-editable without tooling, violates Constitution
III's "easy to inspect and hand-edit without special tooling" and IV's "no database
unless a documented need arises," and no such need exists here).

**Auto-commit, conditional on git being detected**: see §14 below — after weighing it
against "explicitly not building this," the decision was revised to have the scraper
commit its own changes automatically when `RKBY_DATA_DIR` is a git repo, since doing so
strictly adds to (never replaces) the per-record-file history benefit described above.

## 7. Schema validation

**Decision**: `jsonschema` validating one JSON Schema document (`applicant-record.
schema.json`, see contracts/) against each record's parsed YAML dict.

**Rationale**: Small, well-maintained, does exactly FR-017's job (reject structurally
invalid hand-edits before merging) without pulling in a modeling framework the project
doesn't otherwise need. `jsonschema` works directly on the plain dicts `PyYAML` and the
scraper's own in-memory records already are — no extra translation layer.

**Alternatives considered**: `pydantic` (a full modeling/validation framework — heavier
than needed for "validate a hand-edited dict against a schema," and the schema-first
approach means the JSON Schema file itself, not a Python class, is the artifact editors
use for inline hand-editing help).

## 8. Merge / overwrite-protection algorithm

**Decision**: A record's persisted fields are frozen once non-empty (FR-009): the merge
step only ever fills a currently-empty/unset field from a new scrape, or creates a
brand-new file for a not-yet-seen match key. The `status` field is treated as one of
these frozen fields too — it is set once at first persistence and never rewritten by
later scrapes. The "went to *no*" signal (FR-015) is carried by a **separate**
`excluded` boolean + `excluded_observed_at` timestamp pair that the merge step sets the
first time a scrape observes `no` for an already-persisted, non-ignored record, leaving
every other field (including the frozen `status` text) untouched — matching FR-015's
"its other fields are left unchanged."

**Rationale**: Directly implements FR-009 and FR-015 as written, and keeps "why did this
field freeze" auditable: a field's presence/absence, not a timestamp comparison,
decides whether the scraper may touch it.

## 9. Duplicate / conflict handling

**Decision**: Matching key = `normalize(first_name) + "-" + normalize(last_name)`
(lowercase, diacritics stripped via `unicodedata` NFKD, non-alphanumerics → `-`).

- **Within one scrape** (Story 5 AC1/AC2): rows sharing a match key are compared
  field-by-field (address/phone/birthday, case/whitespace-normalized). If none of the
  fields that are non-empty on both sides disagree, they're merged into one candidate
  before persistence. If any do disagree, the run logs a warning with both rows' raw
  values and neither row is persisted this run (avoids guessing which is authoritative).
- **Against the persisted store** (FR-014): same field-by-field comparison between the
  new scrape and the existing record. No conflict → normal fill-empty-fields merge
  (§8). Conflict → the run logs a warning containing the full newly-scraped snapshot (so
  a human has what they need to hand-resolve it) and the existing persisted file is left
  completely untouched — never silently overwritten, never silently discarded.

**Rationale**: Directly implements FR-013/FR-014/FR-020 and Story 5. Logging the full
conflicting snapshot (rather than just "conflict detected") means the human reviewer
doesn't have to re-scrape or dig through the intranet by hand to resolve it — it's a
verbatim requirement of "the record is left in a valid, non-corrupted state" (SC-005)
without also being useless to a human.

## 10. All-or-nothing rollback (FR-018) & schema-invalid existing file (FR-017)

**Decision**: Split the run into a pure-fetch phase and a pure-merge/write phase.
`fetch_all_pages()` does only network + parsing and returns an in-memory list; it never
touches disk. Only if *every* page for the season fetches successfully does the run
proceed to load+validate the season's existing persisted records and merge the new data
in. If loading an existing record fails schema validation, or if any page fetch raises,
the run aborts before writing anything for that season — the directory on disk is
byte-for-byte what it was before the run started.

**Rationale**: Directly implements FR-017 and FR-018 by construction (there's no
disk-write code path reachable before both preconditions hold), rather than relying on
try/except cleanup after partial writes.

## 11. Logging

**Decision**: Python stdlib `logging`, one `WARNING`+-level `FileHandler` per run
writing to `<season>/logs/<run-timestamp>.log` (filename e.g.
`2026-08-15T143000.log`), plus an `INFO`-level stream handler to the console so an
interactive run shows progress.

**Rationale**: Satisfies FR-016 with zero extra dependencies; stdlib `logging` already
does per-handler level filtering and timestamped records.

## 12. Testing strategy (no real network calls)

**Decision**: `pytest` + `responses` (dev-only dependency) to intercept every
`requests` call in unit tests by URL, returning recorded/obfuscated fixture HTML/bytes
from `tests/fixtures/`. Fixtures are hand-authored or captured-then-obfuscated example
`team_application_manager.php` responses and a login page, with all real names/
addresses/phone numbers/photos replaced by synthetic placeholder data before being
committed.

**Rationale**: `responses` mocks at the `requests` library boundary, so the
`IntranetClient` code under test is exercised exactly as it runs in production, with no
hand-rolled fake-session bookkeeping in every test. Matches FR-021 exactly ("recorded
example request/response fixtures with obfuscated data... MUST NOT make real network
calls").

**Alternatives considered**: `unittest.mock.patch` directly on `requests.Session.get`
— works but pushes response-shaping boilerplate into every test; rejected in favor of
`responses`' declarative fixture registration.

## 13. Default season computation (FR-022)

**Decision**: Pure function `default_season_label(today: date) -> str`: month 1–7 → 
`f"{Y-1}-{Y}"`, month 8–12 → `f"{Y}-{Y+1}"`, using hyphens as the canonical in-code/
on-disk separator (`2025-26`) rather than the display slash form (`2025/26`) to avoid
CLI shell-quoting friction; the CLI accepts either separator on `--season` input and
normalizes to hyphen form.

**Rationale**: Directly implements FR-022 and the July/August boundary edge case as a
small, trivially-unit-testable pure function with no I/O.

## 14. Auto-commit local data-repo changes after a successful run

**Decision**: After a run completes its writes for a season (fetch phase succeeded, no
FR-018 rollback), detect whether `RKBY_DATA_DIR` is a git repository via `git -C
<RKBY_DATA_DIR> rev-parse --is-inside-work-tree`. If it is:

1. `git -C <RKBY_DATA_DIR> add seasons/<season-label>` — staged scope is deliberately
   limited to the season folder this run touched, never `-A`/repo-wide, so the run
   never sweeps in unrelated in-progress edits a human may have staged elsewhere in the
   same data repo (e.g. mid-edit in another season's folder).
2. If `git status --porcelain -- seasons/<season-label>` shows nothing staged (a
   no-op re-run, per SC-002), skip the commit entirely — no empty commits.
3. Otherwise `git -C <RKBY_DATA_DIR> commit -m "scrape(<season-label>): <N> new, <M>
   excluded, <P> photos fetched — <run-timestamp>"` using counts already gathered for
   the run log (§11), so the commit message and the log agree.

If `RKBY_DATA_DIR` is not a git repository, the run completes exactly as before —
nothing git-related is attempted, and this is not an error.

If the `git commit` step itself fails (most likely: no committer identity configured
for that repo), it is caught and logged as a `WARNING` in the run log; it does **not**
change the run's exit code and does not touch or roll back the already-successfully
-written season data. The data on disk is already valid and complete at that point —
a local git-configuration problem shouldn't retroactively fail a successful scrape.

**Rationale**: The local data repo is explicitly described as "just for backup" and
never pushed anywhere (spec Assumptions), so an automatic local commit carries low
risk and is trivially reversible (`git revert`/`git reset`) if one is ever wrong.
Auto-committing only after this run's own validation/rollback guarantees already hold
(§10) means every auto-commit is, by construction, of already-schema-valid,
overwrite-protection-respecting data — it can't commit a partially-written or corrupt
state. This directly extends, rather than replaces, the "per-record YAML file is the
history-aware format" decision in §6: the maintainer still gets the same clean
per-person diffs, just without having to remember to run `git commit` by hand after
every run.

**Implementation note**: shells out to the `git` CLI via `subprocess`, rather than
adding a Python git library (e.g. `GitPython`) as a dependency — git is already
required to exist (the data repo is a git repo by the spec's own Assumptions), and this
is the only git interaction the whole feature needs, which doesn't justify a fifth
runtime dependency (Constitution IV).

**Alternatives considered**: always requiring git and failing if absent — rejected, the
user's instruction is explicitly conditional ("if git is detected"), and forcing every
`RKBY_DATA_DIR` to be a git repo isn't otherwise a requirement of this feature. An
opt-out environment variable to disable auto-commit — not added; the behavior is scoped,
local-only, and trivially reversible via normal git commands, so a dedicated toggle
would be speculative complexity ahead of anyone needing it.

## 15. Empirical findings from live-site inspection (implementation-time, US1)

The following resolves the open questions §2/§3/§4/§5 left for implementation, from a
one-time authenticated inspection of the real site (no real data persisted or
committed; only structural facts recorded here).

**Login** (§2): `POST /login` with fields `loginusername`, `loginpassword`, and three
fixed accompanying fields the form always sends: `UseMd5=UseMd5`,
`dologinnoredirect=dologinnoredirect`, `dologin=Login`. Session auth via cookies
(`PHPSESSID`, `csrf_token`) — no CSRF token needs to be read/replayed for this POST.
**Failure detection**: on failure the response stays on `/login` (an unauthenticated
`GET` of any protected page also redirects back to `/login`); the failure page also
contains an element with `class="error"` whose text is a human-readable message (not
matched on verbatim, only used as a secondary signal) — success is detected by the
response URL no longer being `/login`.

**Season/team resolution** (§5): the authenticated `GET /team/applicants` page embeds
a toggle-button group per season: `<label ... OnClick="get_season_data(<id>);"> <input
... value="<id>"><i></i><label-text></label>`, where `<label-text>` is either
`"Season YYYY/YY"` or `"Inactive"`. Parse with a regex over that pattern to build
`{"YYYY-YY": id}`. Team id comes from `<select id="team_group" name="team_group">`
(single `<option>` per team the account has access to; this account has exactly one:
`value="740"` text `"Hamburg"`, matching the spec's own example request). Confirmed:
season `"2025-26"` resolves to `season_id=1181`, matching the spec's example request
exactly.

**Applicant list shape** (§3): `GET /Ajax/team_application_manager.php` (params
`tableSettings=true, teamid, season, filter_status, page`) returns one `<table
id="applicants">` with a `<thead>` (`Image, Created, Name, Email, Phone, Jobtitle,
Address, Zip, City, Country, Participated, Role, Age, Sex, Email send, Motivation,
Accept on teams, Note`) and one `<tr>` per applicant in `<tbody>`.

- **Pagination is client-side only**: the server returns *every* applicant row for the
  season in a single response regardless of the `page` query param — `page` only seeds
  a jQuery DataTables `displayStart` UI hint in an inline `<script>`, it does not
  change which rows are present in the HTML (confirmed: `page=0` and `page=1`
  responses are byte-identical apart from that one hint value). `fetch_all_pages()`
  therefore does not need true multi-request pagination against the real site, but
  still loops defensively (fetch a page, stop once a subsequent page adds no
  previously-unseen row) rather than hard-coding "always exactly one fetch" — cheap,
  and keeps the multi-page fixture/rollback tests (FR-018) meaningful.
- **Address/phone are present directly in the row** (`Phone`, `Address`, `Zip`, `City`,
  `Country` columns) — no per-applicant detail fetch is needed for those. They are
  combined into the single `address` field as `f"{address}, {zip} {city}, {country}"`
  (each part omitted if blank).
- **Birthday is NOT present in the list view itself** — only an `Age` column (whole
  years). **Revision (post-implementation, live-site inspection via the row-click
  popup)**: it *is* available, on a per-applicant detail endpoint reachable from this
  table after all — `GET /Ajax/showparticipant.php?season=<season_id>&mplc=/team/
  applicants&userid=<applicant_id>`, the same request the site fires when a user
  clicks an applicant row to open its profile popup. `applicant_id` (`userid`) is read
  from `<span class="iddata" data-id="...">` inside the row's `Accept on teams` cell —
  present under both status renderings (toggle and finalized plain-text). The detail
  response contains `<p class="profile_birthday"><span>Birthday: </span>dd-mm-yyyy</p>`
  (European day-first order, confirmed against a known applicant's `Age` value);
  parsed and stored as ISO 8601 (`YYYY-MM-DD`) per data-model.md. Fetched lazily and
  only once per applicant — mirrors the existing photo-fetch pattern: skipped whenever
  a record already has a non-empty `birthday` (fill-empty-only, FR-009), and a fetch
  failure is logged as a warning and simply retried on a later run (FR-005) rather than
  aborting. This further revises the initial "leave null, no such endpoint exists"
  conclusion above (itself a revision of research.md §3's original detail-page-fetch
  contingency) — the endpoint exists, it just isn't linked from the table row the way a
  normal `<a href>` or `onclick` would be; it only became apparent by watching the
  network request the site's own UI makes on row click.
- **Status** (`Accept on teams` column) has two renderings that both need parsing: (a)
  an editable 3-way toggle (`Undecided`/`No`/`Yes`), where the selected option's
  `<label>` carries an extra `active` CSS class — read that label's text; (b) an
  already-finalized plain-text value, either `"User has approved"` or `"User has
  declined (Resend)"` (no toggle markup in that case). Both are normalized at parse
  time into one of three canonical, lowercase stored values: `"yes"` (Yes / User has
  approved), `"no"` (No / User has declined...), `"undecided"` (Undecided) — any other
  raw text is lowercased and stored as-is but never treated as `"no"` for FR-003/FR-015
  purposes (only an exact `"no"` excludes/flips a record). Storing normalized tokens
  rather than the raw site text keeps FR-003's "status is no" check and FR-015's
  status-flip check simple exact-string comparisons.
- **Name** is one cell, `"First Last"`; split on the first space into `first_name`/
  `last_name` (no structural separation is available for multi-word first names — an
  acceptable, documented limitation given the source data itself doesn't separate
  them).

**Photo — no popup page exists** (§4, revises the original decision): the thumbnail is
a CSS `background-image: url('/uploaded/webusers/<id>_<ts>_<rand>/<filename>?w=60')`
on a `<div class="profile-image-list">` in the row's `Image` cell (empty `style` when
no photo was ever uploaded). There is no separate anchor/popup page to fetch or parse.
The full-resolution image is the *same URL with the `?w=60` query string stripped* —
confirmed by fetching both: the thumbnail is ~2.5KB, the query-stripped URL is a full
~64KB JPEG at the original upload resolution. `fetch_photo()` is therefore a pure URL
transform (strip the `w` query param) plus one `GET`, not a two-step popup-then-image
fetch as originally modeled.
