# Feature Specification: Applicant Scraper & Data Persistence

**Feature Branch**: `001-scraper-persistence`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "the scraper and data persistence. credentials for the website shall be available as environment variables. the website is https://intranet.team-rynkeby.com/team/applicants, which contains a list of applicants for each season. there are links to select the season. a backend fetch is made to retrieve the aplicants data: for season 2025/26 the request url is: 'https://intranet.team-rynkeby.com/Ajax/team_application_manager.php?tableSettings=true&teamid=740&season=1181&filter_status=&page=0', we might have to fetch several pages. i want the scraper to be able to be run several times in a row without destroying persisted data or overwriting it changes were made after first run 'by hand'. photos of the team meambers are available from that page as well: click on te small member photo to go to a popup that contains a larger one. i only wnat to save data for member that are not in status 'no' (where disapproved by someone to take part in the team). we might have to deduplicate entries (by first and last name). we might have to set the status of an entry as 'ignore' manually somehow in the persisted data, so that it does not get recreated each time we run the script. Ignored members wil not be considered further in all other scripts, since they are not part of the team. suggest a proper persistence format for the base data and the images that is easy for humans to handle. personally, i think json or yaml sounds fine. in any way, we need a schema to check correctness and help with editing. images are links to files. the peristence must have its own folder for each season in any case. Since we do keep the data of people out of this repo, we keep it in a separate folder (set via env var) that is a git repo also (will not be pushed anywhere, just for backup. if you can think of a better history-aware format, tell me. lastly: i need tests cases on unit level for the edge cases and happy path of all this. no actual scraping though for testing. we can save example requests as references, containig obfuscated data."

## Clarifications

### Session 2026-08-15

- Q: If fetching a season's applicant pages fails partway through a run (e.g. page 3 of
  5 errors out), should the run keep whatever pages it already fetched successfully, or
  discard everything from that run and leave the previously persisted data completely
  untouched? → A: All-or-nothing rollback — discard all newly-fetched applicant data
  from that run; previously persisted data stays completely untouched until a full
  season fetch succeeds.
- Q: When a member's full-resolution photo can't be fetched, should that member's other
  data still be persisted, or should the whole member be skipped/retried until the
  photo also succeeds? → A: Persist without the photo now; log the failure as a
  warning; retry the photo automatically on a later run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-time scrape of a season (Priority: P1)

As the team data maintainer, I run the scraper against a chosen season so that every
currently-approved (non-"no") applicant's profile data and photo end up saved locally,
ready for the map, pairing, and birthday-calendar tools to use later.

**Why this priority**: Without this, there is no local data at all. This is the
foundational capability every other story and every downstream script depends on.

**Independent Test**: Run the scraper once against a season with no prior local data
for that season. Verify a season folder is created containing one persisted record
(with photo) per applicant whose status is not "no", and no record at all for any
"no"-status applicant.

**Acceptance Scenarios**:

1. **Given** no local data exists yet for a season, **When** the scraper is run
   against that season, **Then** a season folder is created containing one persisted
   record and photo for every applicant whose status is not "no", and no record for
   any applicant whose status is "no".
2. **Given** an applicant list that spans multiple result pages, **When** the scraper
   runs, **Then** applicants from every page are persisted, not only the first page.
3. **Given** no season is specified, **When** the scraper is run on a date in
   January–July of year Y, **Then** it defaults to the season labeled "(Y-1)/Y"; and
   **Given** it is run on a date in August–December of year Y, **Then** it defaults to
   the season labeled "Y/(Y+1)".
4. **Given** a retained applicant's full-resolution photo cannot be fetched, **When**
   the scraper runs, **Then** their other profile data is still persisted, the missing
   photo is logged as a warning, and the photo is retried automatically on a later run.

---

### User Story 2 - Re-run without losing manual corrections (Priority: P1)

As the maintainer, after hand-correcting a field (e.g. a birthday) or replacing a
member's photo, I run the scraper again so that newly-appeared applicants get picked
up without my corrections being lost or overwritten.

**Why this priority**: This is the core "safe to re-run" guarantee the feature exists
to provide. Without it, routine re-scraping destroys manual cleanup work and the local
data can never be trusted as the editable source of truth.

**Independent Test**: Manually edit a field and replace a photo in an already-persisted
record, re-run the scraper against the same season, and verify the edited field and
photo are unchanged while any genuinely new applicants are still added.

**Acceptance Scenarios**:

1. **Given** a persisted record whose field was manually corrected, **When** the
   scraper re-runs and the intranet still returns some value for that field, **Then**
   the persisted value remains the manually corrected one.
2. **Given** a persisted photo file was manually replaced, **When** the scraper
   re-runs, **Then** the manually placed photo file is not overwritten.
3. **Given** a new applicant appears on the intranet who was not present in the
   previous run, **When** the scraper re-runs, **Then** a new record is added for them.

---

### User Story 3 - Marking a record ignored (Priority: P2)

As the maintainer, I mark a wrongly-included or unwanted record as "ignore" so it stops
being touched or recreated by the scraper, and is excluded from every other script that
consumes this data.

**Why this priority**: Needed to keep the dataset clean of noise (test entries,
mistakenly captured entries, edge cases) without fighting the scraper on every run.

**Independent Test**: Mark a persisted record "ignore", re-run the scraper against the
same season multiple times, and verify the record is never modified and never
duplicated even if the same person still appears in the scrape.

**Acceptance Scenarios**:

1. **Given** a persisted record is marked "ignore", **When** the scraper re-runs and
   that same person still appears in the scraped applicant list, **Then** their
   persisted record is not modified in any field.
2. **Given** a persisted record is marked "ignore", **When** any other script reads the
   persisted data, **Then** that record is excluded from that script's processing.

---

### User Story 4 - Automatic exclusion on disapproval (Priority: P2)

As the maintainer, I want to be warned when someone I already saved gets disapproved on
a later scrape, so I know to review them, without the tool silently deleting their data.

**Why this priority**: Keeps the roster accurate over time and surfaces status changes
that matter for team membership, while protecting past manual work.

**Independent Test**: Persist a record with a non-"no" status, then have a later scrape
observe status "no" for that same applicant, and verify the record remains present but
is marked excluded with an observed-at timestamp, and a warning appears in that run's
log.

**Acceptance Scenarios**:

1. **Given** a persisted, non-ignored record whose status was previously not "no",
   **When** a later scrape observes status "no" for that same applicant, **Then** the
   record is marked excluded, the date/time the exclusion was observed is recorded, its
   other fields are left unchanged, and a warning-level entry is written to that run's
   log.
2. **Given** a persisted record already marked "ignore", **When** a later scrape
   observes status "no" for that applicant, **Then** no exclusion flag or log entry is
   added and the record is left completely untouched (the manual "ignore" flag takes
   precedence).

---

### User Story 5 - Deduplicating repeated entries within a season (Priority: P3)

As the maintainer, I don't want the same person appearing twice in a season's data
because of overlapping scrape pages or duplicate applications.

**Why this priority**: Keeps the dataset clean and correct, but affects a rarer edge
case than the P1/P2 stories above.

**Independent Test**: Feed the scraper a mocked applicant list containing the same
first and last name twice within one season, and verify only one persisted record
results.

**Acceptance Scenarios**:

1. **Given** the same first and last name appears twice in one season's scraped list
   with consistent details, **When** the scraper runs, **Then** only one persisted
   record exists for that person.
2. **Given** the same first and last name appears twice but other available details
   conflict meaningfully, **When** the scraper runs, **Then** the case is flagged with
   a warning-level entry in the run log rather than silently merged.

---

### User Story 6 - Credentials and storage location kept out of the repository (Priority: P3)

As the maintainer, I configure intranet credentials and the local data folder purely
through environment variables, so nothing sensitive ever lands in source control.

**Why this priority**: A direct requirement of the project's privacy principle, though
it is an enabling/configuration concern rather than a workflow of its own.

**Independent Test**: Run the scraper with credentials and the data-folder path set
only via environment variables (no config file in-repo), confirm it authenticates and
persists successfully, and confirm the repository contains no trace of credentials or
personal data.

**Acceptance Scenarios**:

1. **Given** valid credentials and a data folder path are set as environment variables
   and nowhere else, **When** the scraper runs, **Then** it authenticates successfully
   and writes to the configured folder.
2. **Given** a required environment variable is missing, **When** the scraper is run,
   **Then** it fails clearly before making any network request or writing any file,
   rather than partially running.

---

### Edge Cases

- What happens if the scraper is run with required environment variables missing or
  invalid? It fails clearly before any network request or file write (Story 6, AC2;
  FR-023).
- What happens if a network or authentication failure occurs partway through fetching a
  multi-page applicant list? The entire run's newly-fetched applicant data is discarded
  and the season's persisted data is left exactly as it was before the run — never
  partially updated or corrupted (FR-018).
- What happens when a person's status flips to "no" but they are already marked
  "ignore"? The "ignore" flag takes precedence; nothing changes (Story 4, AC2).
- What happens when a hand-edited persisted file no longer matches the schema right
  before a scrape run needs to write to it? The run refuses to write over or lose the
  existing data and surfaces a clear validation error instead.
- What happens when the larger photo can't be fetched for one applicant? That
  applicant's other data is still persisted, the failure is flagged as a warning in the
  run log, and the photo is retried on a later run rather than failing the whole run or
  blocking that applicant's other data (FR-005, FR-016).
- What happens when two different real people happen to share the same first and last
  name? They are flagged for human review rather than silently merged into one record.
- What happens when an applicant reapplies in a later season? They are treated as an
  independent new record in that later season's own folder, not linked to any record
  from a prior season.
- What happens to an applicant who was "no" (and thus never persisted) in one run, but
  is approved in a later run? They are persisted for the first time on the run that
  observes the approved status, like any other new applicant.
- What season does the scraper use by default when run right at the July/August
  boundary? July still belongs to the January–July bucket of the season that ends that
  year; the new season's bucket only starts in August (FR-022).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST fetch the list of applicants for a specified season from the
  intranet, retrieving every page of results for that season, not just the first page.
- **FR-002**: System MUST authenticate to the intranet using credentials read
  exclusively from environment variables; no credential value may be written into any
  file inside the source code repository.
- **FR-003**: System MUST exclude from persistence any applicant whose status is "no"
  (disapproved) at the time they are first seen.
- **FR-004**: System MUST capture, for each retained applicant, their available profile
  data (first name, last name, address, phone number, birthday) and current
  application status.
- **FR-005**: System MUST attempt to retrieve and persist the full-resolution photo for
  each retained applicant — the image shown after opening that member's photo popup —
  not only the small thumbnail shown in the applicant list. A photo-fetch failure for
  one applicant MUST NOT prevent that applicant's other data from being persisted, nor
  affect any other applicant; a missing photo MUST be retried automatically on a
  subsequent run.
- **FR-006**: System MUST persist retained applicants' data and photos in a folder
  dedicated to the season being scraped, kept separate from every other season's data.
- **FR-007**: System MUST store all persisted applicant data and photos outside the
  source code repository, at a location determined by an environment variable.
- **FR-008**: System MUST be safe to run repeatedly for the same season: no run may
  delete, corrupt, or silently discard previously persisted data.
- **FR-009**: System MUST NOT overwrite any field in an existing persisted record that
  already holds a value; a newly scraped value is only written into a field that is
  currently empty/unset, or into a brand-new record for an applicant not yet persisted.
- **FR-010**: System MUST let a human mark any persisted record as "ignore" directly
  within the persisted data.
- **FR-011**: System MUST leave every field of an "ignore"-marked record completely
  untouched on all future runs, and MUST NOT recreate that person's record even if they
  reappear in a later scrape of the same season.
- **FR-012**: Persisted data MUST carry enough information (an "ignore" flag and an
  excluded/disapproved flag) for other scripts to identify and skip members who are not
  part of the team. Implementing that exclusion logic inside those other scripts is
  outside this feature's scope.
- **FR-013**: System MUST detect when the same person appears more than once within a
  single season's scraped applicant list (matched by normalized first and last name)
  and persist a single consolidated record rather than duplicates.
- **FR-014**: When a scraped name matches an existing persisted record but other
  available scraped details conflict meaningfully with that record, system MUST flag
  the case for human review in the run log rather than silently merging or silently
  discarding the new data.
- **FR-015**: When a previously-persisted, non-ignored applicant's status is observed
  to have changed to "no" on a later scrape, system MUST mark their persisted record as
  excluded (rather than deleting it or changing its other fields) and record the
  date/time the change was observed.
- **FR-016**: System MUST write a run log for every execution (by default a
  timestamped file), recording at warning level each notable occurrence, including a
  newly observed status-to-"no" exclusion, an unresolved possible-duplicate match, and a
  per-applicant photo-fetch failure.
- **FR-017**: System MUST validate persisted data against a defined schema, catching
  structurally invalid hand-edits and refusing to silently write over or lose existing
  valid data when validation fails.
- **FR-018**: System MUST treat fetching a season's applicant list as all-or-nothing: if
  retrieving any page of that list fails or is interrupted partway through a run, the
  run MUST discard all newly-fetched applicant data from that run and leave the
  season's previously persisted data completely unchanged, rather than applying a
  partial update. (Per-applicant photo-fetch failures are handled separately, per
  FR-005 — they do not trigger this rollback.)
- **FR-019**: Persisted data and photo files MUST be stored in a human-readable,
  structured, hand-editable form (e.g. JSON or YAML), accompanied by a schema that can
  be used to validate and assist manual editing.
- **FR-020**: System MUST deduplicate/match applicants only within the season currently
  being scraped; it MUST NOT attempt to link or merge an applicant's record with any
  record in a different season's folder.
- **FR-021**: Automated unit tests MUST cover the happy path and the edge cases above
  (overwrite protection, ignore handling, status-flip exclusion, within-season
  deduplication, schema validation failure, all-or-nothing run rollback on a
  mid-pagination failure, per-applicant photo-fetch failure, and missing/invalid
  environment variables) using recorded example request/response fixtures with
  obfuscated data, and MUST NOT make real network calls to the intranet.
- **FR-022**: The season to scrape MUST be an optional argument to each run. When it is
  omitted, system MUST default to the season computed from the current date: a date in
  January through July of year Y defaults to the season labeled "(Y-1)/Y"; a date in
  August through December of year Y defaults to the season labeled "Y/(Y+1)".
- **FR-023**: System MUST verify that all required environment variables (credentials,
  local data folder path) are present and usable before performing any network request
  or file write; if any are missing or invalid, it MUST exit with a clear error and
  make no partial changes.

### Key Entities

- **Season**: One team application period (e.g. "2025/26"), identified by a season
  identifier, owning its own dedicated local folder that holds only that season's
  applicants, photos, and logs.
- **Applicant Record**: One person's persisted data for one season — first name, last
  name, address, phone number, birthday, current status, an excluded flag (set
  automatically on a status-to-"no" observation) with an observed-at timestamp, a
  manual "ignore" flag, and a reference to their photo file.
- **Photo Asset**: The full-resolution image file for one applicant, stored locally on
  disk and referenced from that applicant's record.
- **Run Log**: A per-execution, timestamped record of warning-level occurrences (status
  exclusions observed, unresolved possible-duplicate matches) produced every time the
  scraper runs.
- **Local Data Repository**: The separate, git-backed folder (outside this codebase,
  location set by an environment variable) holding every season's applicant records,
  photos, and logs — used for durable local storage and, via its own git history, for
  recoverable change history and backup.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A team admin can scrape a season's applicants and end up with one
  correctly-persisted, photo-included local record for every non-"no" applicant, in a
  single run.
- **SC-002**: Running the scraper twice in a row for the same season with no upstream
  changes results in zero changes to any already-persisted field or photo.
- **SC-003**: 100% of manual field or photo corrections made after a run survive every
  subsequent run until a human changes them again.
- **SC-004**: A record marked "ignore" remains completely unchanged and is never
  recreated, across any number of subsequent runs.
- **SC-005**: Every run — whether it completes or fails partway through — leaves each
  season's persisted data in a valid, non-corrupted state matching the defined schema.
- **SC-006**: Every status-to-"no" exclusion and every unresolved possible-duplicate
  match is visible afterward in that run's log, without needing to inspect the
  persisted data files directly.
- **SC-007**: No credential value or personal member data is ever present in the source
  code repository, at any point in its history.

## Assumptions

- The season to scrape is an optional input to each run; when provided explicitly it
  overrides the date-based default (FR-022). The tool does not need to auto-discover
  the full list of seasons by scraping the season-selector links itself.
- Resolving a season label (e.g. "2025/26") to whatever identifier the intranet
  actually needs (as seen in the example request, a numeric season id alongside a team
  id) is a technical mapping to be worked out during planning/implementation — the spec
  only fixes which season label is chosen by default.
- The exact set and shape of network requests needed to retrieve applicant data and
  photos (how many pages, how the full-resolution photo is actually fetched per
  member, whether a season-id lookup is needed, etc.) is not fully known yet and will
  be determined empirically, e.g. via interactive exploration of the live site, during
  implementation. The design should expect a potentially large number of requests per
  run (one or more per page, plus roughly one per retained applicant's photo).
- Intranet credentials are a username and password pair (or equivalent single-user
  credential), supplied via environment variables; the tool performs its own login
  rather than requiring a pre-obtained session token.
- "Already holds a value" for the overwrite-protection rule (FR-009) means: any field
  that is empty/unset gets filled in by the scraper; once a field holds any value
  (whether set by a prior scrape or by hand), only a human can change it thereafter.
- The excluded flag set on a status-to-"no" observation (FR-015) is a distinct marker
  from the manual "ignore" flag; a maintainer can later decide to manually delete,
  ignore, or reinstate an excluded record.
- The observed-at timestamp for an exclusion is the date/time the scraper detected the
  change, since the intranet's applicant list is not assumed to expose its own
  status-change timestamp.
- The local data repository (the git-backed folder outside this codebase) already
  exists as a git repository before the scraper is first pointed at it; provisioning or
  initializing that repository is not part of this feature.
- Exact persisted file granularity (e.g. one file per applicant vs. one file per
  season) and the precise schema definition are technical design decisions to be
  resolved during planning, bound only by the requirement that the format stay
  human-readable, hand-editable, and schema-validated (FR-019).
- Building the map, rider-pairing, or birthday-calendar scripts that will later consume
  this persisted data is out of scope for this feature (they are separate scripts per
  project convention).
