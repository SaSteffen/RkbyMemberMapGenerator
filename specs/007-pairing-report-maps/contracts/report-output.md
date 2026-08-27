# Contract: Generated Pairing Report Output (extended)

Extends `specs/006-rider-pairing-suggester/contracts/report-output.md`, which fully
covers `## New Riders` and the pre-existing parts of `## Training Clusters`. This
document covers only what this feature (007) changes: the new `## Team Overview`
section, the map image now embedded in each Training Cluster, and the removed
3-member minimum. Everything in 006's contract not mentioned below is unchanged.

## Markdown structure (changed portions only)

```markdown
# Rider Pairing Suggestions — <season label>

Generated <ISO date>. Hand-edit this file freely — re-running the script overwrites
it, but every prior version stays recoverable from this repository's git history.

## Team Overview

<img src="maps/overview.png" alt="Team overview map" width="100%">

## New Riders
... (unchanged from 006)

## Training Clusters

### Cluster 1 (<N> riders)

<img src="maps/cluster_1.png" alt="Cluster 1 map" width="100%">

- **<First> <Last>** — <address> — <phone>/<email>
  <img src="../seasons/<season>/<photo path>" alt="<First> <Last>" width="80">
- ...

<!-- "No training clusters found this season." when there are none -- unchanged;
     no map is rendered or referenced in that case. -->
```

Notes on the new/changed structure:

- **`## Team Overview`** is a new top-level section, placed immediately after the
  intro line and *before* `## New Riders` — first thing a reader scans to, matching
  FR-008's "distinct, prominent... independent of and separate from the per-cluster
  maps and the per-new-rider... content." It contains exactly one image reference,
  `maps/overview.png` (relative to `rider_pairings.md`'s own directory — both live
  under `reports/`, so no `../` prefix, unlike the member-photo references under
  `seasons/`). This section is always present and always contains that image
  reference, even when the underlying map depicts zero members (contracts/
  map-output.md) — the section itself is never conditionally omitted.
- **Per-cluster map image**: each `### Cluster <n>` subsection gets one
  `<img src="maps/cluster_<n>.png" ...>` line, placed directly under the heading,
  before that cluster's member roster — mirroring where each entry's own photo
  `<img>` tag already sits relative to its text elsewhere in this file. `<n>` always
  matches the heading's own number.
- **Heading text for a single-member cluster**: `### Cluster <n> (1 rider)` — the
  existing `f"### Cluster {index} ({len(cluster.member_match_keys)} riders)"`
  template already pluralizes correctly (or, if a hand-reviewer wants perfect
  English, this is the one line implementers should special-case for "1 rider" vs.
  "N riders"; either rendering is acceptable to this contract, "riders" alone is not
  a defect).
- **No training clusters at all**: unchanged from 006 — "No training clusters found
  this season." is shown, with **no** `## Team Overview` change (that section is
  independent, per FR-008, and still renders its overview map even when Training
  Clusters is empty) and **no** cluster map file is written or referenced.

## PDF export contract (unchanged mechanism, new content)

`reports/rider_pairings.pdf` continues to be a direct rendering of
`rider_pairings.md`'s content at export time, now including the Team Overview and
per-cluster map images alongside the existing member photos — same relative-path
resolution mechanism (`xhtml2pdf`'s `path=str(md_path)`), no code change to
`scripts/rkby_pairing/pdf.py` required for this to work (research.md §7).

## What did not change

- File names/locations for `rider_pairings.md`/`rider_pairings.pdf`, their
  overwrite-in-full-on-every-run semantics, their auto-commit/gitignore treatment —
  all unchanged from 006's contract.
- `## New Riders` section structure, contact-info-in-full policy, suggested-contact
  ordering — unchanged from 006's contract.
- Each Training Cluster member's own contact-info/photo rendering — unchanged from
  006's contract; only the section-level minimum-size gate and the new map image are
  new.
