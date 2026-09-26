MILL_REVIEW_BEGIN
# Review: Post-merge teardown: keep PR notes, remove checkpoint branches

```yaml
duration_s: 25.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewed_file: /home/knatte/Code/millhouse/wts/merge-teardown-hygiene/_mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] git-pr argument parsing not covered for `--pr-notes <path>`
**Section:** Decisions / Fold pr-notes via a scratch stash; Technical context **Issue:** git-pr's Step 9 argument rule ("strip/ignore `--skip-task-branch-guard`, then take the first remaining non-flag token as the base branch") would read the `<path>` value of `--pr-notes` as the base branch; the discussion only adds Step 9 body-append behaviour and names no change to the argument-parsing rule. **Fix:** State that the argument step strips `--pr-notes <path>` (flag and value) before base-branch selection, and that `--pr-notes` is order-independent relative to the base token.

## Verdict

REQUEST_CHANGES
One design gap: git-pr argument parsing would misread the `--pr-notes` path as the base branch.
MILL_REVIEW_END
