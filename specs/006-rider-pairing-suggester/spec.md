# Feature Specification: Rider Pairing Suggester

**Feature Branch**: `006-rider-pairing-suggester`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "lets work on a member pairing generator, see description in the readme. i only want to connect riders together. pairings are relevant for new riders 81st season only)! even if someone is a service team member in the latest season, but that person is a good mentor if they were a rider previously. ideally i want to suggest more than one new contact for each rider. most relevant factors i think (please correct me if you think otherwise): proximity, low age gap, ideally same sex but not as important. i also think that maybe we can suggest \"training clusters\". people living close together"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Suggest experienced contacts for a new rider (Priority: P1)

A team organizer wants every new rider joining in the most recently scraped season
("the latest season") to have a short list of experienced people nearby they can
reach out to for advice — someone who has actually ridden to Paris before, lives
close enough to plausibly train together or carpool, and is still part of the team
this season (whether they're riding again or have moved into a Service Crew role).

**Why this priority**: This is the entire point of the feature — everything else
(training clusters) is additive. Without this, there is no artifact to hand to new
riders at all.

**Independent Test**: Run the script against a data set containing a mix of new
riders, returning riders, and a former rider now on Service Crew, all with known
addresses. Confirm every eligible new rider gets a non-empty, ranked list of
suggested contacts, and that every suggested contact has ridden before (currently or
in a past season) and is present in the latest season's roster.

**Acceptance Scenarios**:

1. **Given** a new rider (role Rider, zero previous seasons) in the latest season and
   an experienced rider (role Rider, 2+ previous seasons) living nearby in the same
   season, **When** the script runs, **Then** the experienced rider appears in the
   new rider's suggested contacts.
2. **Given** a person whose role in the latest season is Service Crew but who rode as
   a Rider in an earlier season, **When** the script runs, **Then** that person is
   still eligible to be suggested as a contact for a new rider.
3. **Given** a person who is a new rider themselves (zero previous seasons, role
   Rider this season), **When** the script runs, **Then** that person is never
   suggested as a contact for another new rider.
4. **Given** a new rider with several eligible contacts within a reasonable
   distance, **When** the script runs, **Then** more than one suggested contact is
   returned for that new rider, ordered with the closest/best match first.
5. **Given** a member (new rider or candidate contact) who is marked `excluded`,
   `ignore`d, or has no successfully geocoded address, **When** the script runs,
   **Then** that member never appears as a new rider needing pairing nor as a
   suggested contact.

---

### User Story 2 - Surface training clusters of nearby riders (Priority: P2)

A team organizer wants to spot groups of three or more current-season riders
(new and experienced alike) who live close enough together that they could
realistically train together, independent of the one-to-one mentor suggestions.

**Why this priority**: Explicitly called out by the requester as a "maybe" — useful,
but the mentor pairing in User Story 1 already delivers the feature's core value on
its own and can ship without this.

**Independent Test**: Run the script against a data set with a tight geographic
group of three or more riders and confirm they are reported together as one
cluster, separately from the individual mentor suggestions.

**Acceptance Scenarios**:

1. **Given** three or more current-season riders whose home locations are all close
   to one another, **When** the script runs, **Then** they are reported as a single
   training cluster.
2. **Given** two riders who live close together but no third rider nearby,
   **When** the script runs, **Then** no training cluster is reported for them (a
   cluster requires at least three people).
3. **Given** a Service Crew member or Supporter living inside an otherwise
   qualifying geographic cluster of riders, **When** the script runs, **Then** that
   person is not included in the cluster (clusters are riders-only, matching the
   "only connect riders together" scope of this feature).

---

### Edge Cases

- A new rider has no eligible contacts within any reasonable distance (e.g., they
  live far from everyone else): the script still reports them with as many
  candidates as exist, even if that list is short or empty, rather than silently
  omitting them — the organizer needs to know this rider was hard to match.
- A candidate contact's or new rider's birthday is unknown: the pairing is still
  produced (proximity still applies), the age-gap factor is simply not used to rank
  that particular pair.
- A candidate contact's or new rider's sex is unknown: the pairing is still
  produced; the same-sex tie-breaker is simply not applied to that pair.
- A person's `role` text doesn't match "Rider"/"Service Crew"/"Supporter" in any
  recognized spelling (unrecognized/blank role): they are not treated as a rider for
  either the new-rider or mentor-candidate pool.
- A person's identity resolves across seasons via `alias_match_keys` (e.g., a name
  change): their rider history is still found under the resolved identity when
  checking "was this person a Rider in an earlier season."
- The same experienced contact is a good match for many new riders: they may appear
  in more than one new rider's suggestion list — there is no cap on how many new
  riders one contact is suggested to.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST determine "the latest season" as the most recent season
  found in the scraped local data store, and MUST only produce pairings for that
  season's roster.
- **FR-002**: System MUST identify "new riders" as latest-season records where the
  role is Rider, the number of previous seasons is known and equal to zero, the
  record is not excluded or ignored, and the address has a successfully geocoded
  location.
- **FR-003**: System MUST identify "mentor candidates" as latest-season records
  that are not excluded, not ignored, have a successfully geocoded location, are not
  themselves a new rider (per FR-002), and have ridden as a Rider at least once —
  either their role in the latest season is Rider, or a record for the same person
  (resolving name/identity changes across seasons the same way the rest of the
  project does) shows role Rider in any earlier scraped season.
- **FR-004**: System MUST NOT consider a member's current role alone (e.g., Service
  Crew, Supporter) as disqualifying them from the mentor-candidate pool, as long as
  FR-003's "has ridden before" condition is met.
- **FR-005**: For each new rider, system MUST rank all mentor candidates using, in
  order of importance: (1) geographic proximity between home locations — closer
  ranks better — as the primary factor, (2) smaller age gap as a secondary factor
  when both birthdays are known, and (3) matching sex as a tertiary tie-breaker only
  when both members' sex is known.
- **FR-006**: System MUST suggest more than one contact per new rider whenever more
  than one eligible mentor candidate exists, up to a configurable maximum (default:
  3), and MUST still report a new rider even when fewer candidates than the maximum
  are available (including zero).
- **FR-007**: System MUST identify "training clusters" of three or more
  current-season riders (any experience level, each meeting the same
  excluded/ignored/geocoded eligibility as above) whose home locations lie close
  enough together to plausibly train together, and MUST exclude non-riders from
  clusters even if they live inside the qualifying area.
- **FR-008**: System MUST persist its suggested pairings and training clusters to a
  local, human-readable output file(s) alongside the project's other generated
  artifacts, and MUST NOT commit that output to version control (member names,
  contact details, and approximate locations are personal data under the project's
  privacy rules).
- **FR-009**: System MUST include, per suggested pairing, enough information for the
  new rider to actually reach out (name and at least one available contact method
  such as phone or email) while omitting personal data not needed for that purpose
  (e.g., birthday, food restrictions, raw street address beyond what's needed to
  convey approximate distance/area).
- **FR-010**: System MUST exclude any member flagged `ignore: true` in the latest
  season from appearing anywhere in the output, whether as a new rider, a mentor
  candidate, or a training-cluster member — this is the existing mechanism by which
  a member can opt out.
- **FR-011**: System MUST be runnable independently of the other project scripts,
  reading only already-scraped and already-geocoded local data (no new scraping, no
  new geocoding calls).

### Key Entities

- **New Rider**: A latest-season member needing mentor suggestions — role Rider,
  zero previous seasons, eligible (not excluded/ignored, geocoded).
- **Mentor Candidate**: A latest-season member eligible to be suggested as a contact
  for one or more new riders — has ridden as a Rider at least once (this season or
  an earlier one), is not a new rider themselves, and is eligible.
- **Suggested Pairing**: A (new rider, mentor candidate) match, with its rank for
  that new rider and the proximity/age-gap/sex factors that produced the ranking.
- **Training Cluster**: A group of three or more current-season riders whose home
  locations lie close enough together to be reported as a group, independent of any
  mentor pairing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every new rider in the latest season who has at least one geocoded,
  eligible mentor candidate available receives at least one suggested contact.
- **SC-002**: At least 90% of new riders who have three or more eligible mentor
  candidates available receive the full configured number of suggestions (default
  3), not just one.
- **SC-003**: No suggested contact for any new rider is a person who has never
  ridden (currently or in a past season) — spot-checking any pairing's mentor
  candidate against team history always confirms prior or current rider status.
- **SC-004**: No suggested contact list, and no training cluster, ever includes a
  member who opted out (`ignore: true`) or was excluded from the season.
- **SC-005**: An organizer can hand a new rider their suggested contacts and every
  listed contact is reachable using only the information provided in the output
  (no need to look up additional data elsewhere).

## Assumptions

- "The 81st season" refers to whichever season is most recently scraped into the
  local data store (the last one returned by the project's existing season
  discovery), not a hardcoded literal season number — this keeps the feature working
  unchanged in future seasons.
- "Proximity" is measured as straight-line (great-circle) distance between two
  members' geocoded home coordinates, consistent with how the existing map generator
  already uses those coordinates — no travel-time or road-distance calculation.
- The default number of suggested contacts per new rider is 3, matching the
  requester's "more than one" ask; this is expected to be a configurable value
  (e.g., a CLI option) rather than a hardcoded constant, consistent with other
  scripts in this project exposing tunable behavior via CLI flags.
- A specific distance threshold for what counts as a "training cluster" (User Story
  2) is left as an implementation detail for the planning phase to define (e.g., a
  fixed radius or a density-based grouping), since no single number was specified
  and the feature is explicitly a "maybe" / lower-priority addition.
- Training clusters only ever contain riders (current-season role Rider, any
  experience level) — Service Crew and Supporter members are never included, even
  if they live inside a qualifying cluster's area, per the requester's "I only want
  to connect riders together" scope constraint applied consistently across both
  user stories.
- Output is a new, independent script (per this project's one-script-per-artifact
  principle), writing to the local data directory alongside the existing maps/
  and reports/ output folders — never committed to this repository, and never
  reusing another script's output location.
- If a new rider's or mentor candidate's birthday or sex is unknown, that specific
  ranking factor is simply skipped for affected pairings rather than blocking the
  pairing or the whole run.
