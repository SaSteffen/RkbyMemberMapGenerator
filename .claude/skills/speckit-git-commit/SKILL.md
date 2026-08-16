---
name: "speckit-git-commit"
description: "Commit the current feature's Spec Kit artifacts (spec, plan, tasks, checklists) to git using this repo's commit conventions."
argument-hint: "(no arguments — operates on the current feature directory)"
compatibility: "Requires spec-kit project structure with .specify/ directory"
metadata:
  source: "project-authored for RkbyMemberMapGenerator — not a vendored Spec Kit template"
user-invocable: true
disable-model-invocation: false
---

Commit the current feature's Spec Kit artifacts to git. Callable directly, or
as the `speckit.git.commit` hook (see `after_specify` in
`.specify/extensions.yml`).

## Steps

1. Resolve the feature directory from `.specify/feature.json`'s
   `feature_directory` field. If that file is missing or unreadable, fall
   back to the most recently modified directory under `specs/`.
2. Run `git status --porcelain -- <feature_directory>`. If it reports nothing,
   stop and report that there is nothing to commit — do not create an empty
   commit.
3. Stage only that feature directory: `git add -- <feature_directory>`. Never
   `git add -A` or `git add .` — this repo's `data/` and `.env` (real member
   data and intranet credentials, constitution Principle I) must never be
   swept into a commit incidentally.
4. Review the staged diff (`git diff --cached -- <feature_directory>`). If
   anything looks like real member data (names, addresses, phone numbers,
   birthdays, photo files) rather than spec/plan/tasks prose, stop and warn
   instead of committing.
5. Create a Conventional Commits-style commit describing which Spec Kit stage
   produced the change (e.g. `docs: add <feature> spec`, `docs: add <feature>
   plan`, `docs: add <feature> tasks`), ending with:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   ```
6. Do not push, and do not pass `--no-verify` — let the repo's pre-commit
   hooks (ruff, Conventional Commit message check) run normally. If a hook
   fails, fix the issue and create a new commit rather than amending.
7. Report the resulting commit hash and subject line.
