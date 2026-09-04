# Batch: git-commit-staging-verification

```yaml
task: 'mill-implementer: commit_sha transcription/truncation and final-status-line reliability'
batch: git-commit-staging-verification
number: 2
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch closes GitHub issue #923: a `git mv`/edit-then-stage race that let a
commit for a moved file land with stale pre-edit content, caught only by the
implementer's own optional `git diff --cached` self-check in the one observed
incident. `git-commit/SKILL.md` is the single shared commit path used by every
commit in the repo (implementer per-card commits included), so this fix belongs
in the skill, not in the implementer brief. The check used is `git diff --quiet
-- <files>` (unstaged diff against the just-staged paths) rather than the
issue's literally-suggested `git diff --cached --quiet` — `--cached --quiet`
only confirms *something* is staged, not that it matches the working tree, and
would not have caught the reported incident. No code dependents; this is the
only batch touching `git-commit/SKILL.md`.

## Cards

### Card 2: Add mandatory post-stage staging-verification step to git-commit

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `## Rules` section, immediately after the existing bullet `- Stage
  files individually: `git add file1 file2` — never `git add .` or `git add
  -A`.` and before the next bullet (`- Commit with title + bullet-point
  format...`), insert a new bullet:

  ```
  - **Verify the stage before committing.** After staging, run `git diff
    --quiet -- <the same paths just staged>`. A non-zero exit means the
    working tree still has changes beyond what was staged for those paths --
    the add/edit race this step exists to catch (a `git mv`/edit not yet
    reflected in the index at stage time). On a non-zero exit, re-run `git add`
    for those exact paths once and re-check; if the second check is still
    non-zero, halt and report the mismatch instead of committing.
  ```

  Do not modify the "If on `main`/`master`..." bullets, the push instructions,
  or any other existing bullet in `## Rules`. Do not touch `## Pre-commit
  steps` — that section is explicitly scoped to steps that run *before*
  staging (Lint, Codeguide sync); this is a post-stage, pre-commit step and
  belongs in `## Rules` where staging is first mentioned.
- **Commit:** `docs(git-commit): add mandatory post-stage staging-verification step`

## Batch Tests

`verify: null`. `git-commit` is a prose `SKILL.md` with no python backing (a
grep of `plugins/mill/scripts/` confirms no helper module implements its
logic) — there is no executable surface to test. Correctness is verified by
the plan/code review loop (see the overview's Shared Decisions).
