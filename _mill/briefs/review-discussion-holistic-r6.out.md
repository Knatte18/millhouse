MILL_REVIEW_BEGIN
# Review: Ask the parent session when stuck (parent_thread)

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-25
```

## Findings

### [BLOCKING:consistency] go-holistic-cap retry cites the wrong fixer step
**Section:** Decision `converted-sites`, `go-holistic-cap` row.
**Issue:** The retry cell says the re-dispatch uses "the same args as step 4's fixer," but the inline args given (`--scope holistic --review-file <path> --round <H>`, no `--nits-only`/`--prior-blocking`) match `holistic-review.md` step 5 (the `REQUEST_CHANGES` fixer), not step 4 (the `APPROVE`-path NIT-only fixer, which always adds `--nits-only --prior-blocking <path>`). Rounds-exhausted (step 7) only fires when step 5's `REQUEST_CHANGES` path is still returning, so step 4 was never dispatched this round; a plan writer following the "step 4" cross-reference would add `--nits-only`, which is wrong for a round with unresolved BLOCKINGs.
**Fix:** Change the citation to "step 5's fixer" (or drop the step reference and rely on the inline args, which are already correct).

## Verdict

REQUEST_CHANGES
Fix the go-holistic-cap fixer-step citation before plan writing.
MILL_REVIEW_END
