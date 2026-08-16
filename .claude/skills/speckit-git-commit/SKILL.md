---
name: "speckit-git-commit"
description: "Commit the artifacts a Spec Kit phase (specify/clarify/plan/tasks/checklist/analyze/constitution/converge/implement/taskstoissues) just wrote, using this repo's commit conventions."
argument-hint: "(no arguments — operates on whatever the triggering phase changed)"
compatibility: "Requires spec-kit project structure with .specify/ directory"
metadata:
  source: "project-authored for RkbyMemberMapGenerator — not a vendored Spec Kit template"
user-invocable: true
disable-model-invocation: false
---

Commit whatever a Spec Kit phase just wrote to disk. Callable directly, or as
the `speckit.git.commit` hook — wired up as an `after_*` hook for every phase
in `.specify/extensions.yml` (`after_specify`, `after_clarify`, `after_plan`,
`after_tasks`, `after_checklist`, `after_analyze`, `after_constitution`,
`after_converge`, `after_implement`, `after_taskstoissues`).

Different phases touch different parts of the repo, so this splits the
current diff into up to three independent scopes and commits each
separately (atomic, Conventional-Commits-style commits) rather than one
blanket commit:

1. **Feature directory** — `specs/<feature-dir>/` (spec.md, plan.md,
   research.md, data-model.md, contracts/, tasks.md, checklists/, quickstart.md).
   Covers specify, clarify, plan, tasks, checklist, analyze, converge,
   taskstoissues.
2. **Constitution** — `.specify/memory/constitution.md`. Covers constitution.
3. **Everything else currently dirty** — e.g. `scripts/`, `tests/`,
   `pyproject.toml`. Covers implement.

## Steps

1. Resolve the feature directory from `.specify/feature.json`'s
   `feature_directory` field. If that file is missing or unreadable, fall
   back to the most recently modified directory under `specs/`.
2. Compute the three scopes above from `git status --porcelain`:
   - Scope A: paths under the resolved feature directory.
   - Scope B: `.specify/memory/constitution.md`, if changed.
   - Scope C: everything else reported dirty, excluding Scope A/B paths.
     `data/` and `.env`/`*.env` are gitignored already and won't appear here;
     if anything under those ever does show up unexpectedly, stop and warn
     instead of touching it (constitution Principle I).
3. For each non-empty scope, in order A, B, C:
   a. Stage it by explicit path (`git add -- <paths>`) — never `git add -A`
      or `git add .` for the whole repo in one shot; each scope is staged
      and committed on its own.
   b. Review the staged diff (`git diff --cached -- <paths>`). If anything
      looks like real member data (names, addresses, phone numbers,
      birthdays, photo files) rather than spec prose or source code, stop
      and warn instead of committing that scope.
   c. Create a Conventional Commits-style commit for that scope alone:
      - Scope A: `docs: <describe what changed>` (e.g. `add <feature> spec`,
        `add <feature> plan`, `add <feature> tasks`, `apply /speckit-clarify
        answers`, `add <feature> checklist`).
      - Scope B: `docs: <describe the constitution change>` (e.g. `amend
        constitution to v<version>`).
      - Scope C: `feat`/`fix`/`refactor`/`test`/`chore` as appropriate to what
        actually changed (this is implementation code, not docs).
      Every commit message ends with:
      ```
      Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
      ```
4. If every scope is empty, stop and report that there is nothing to commit
   — do not create an empty commit.
5. Do not push, and do not pass `--no-verify` — let the repo's pre-commit
   hooks (ruff, Conventional Commit message check) run normally. If a hook
   fails on a scope, fix the issue, re-stage that scope, and create a new
   commit rather than amending.
6. Report the resulting commit hash(es) and subject line(s).
