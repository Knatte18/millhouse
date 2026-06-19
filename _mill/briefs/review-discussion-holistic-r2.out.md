MILL_REVIEW_BEGIN
# Review: Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-19
```

## Findings

### [NOTE] mill-merge-in brief-step placement skips step 5
**Section:** Scope / Gap B (mill-merge-in)
**Issue:** Scope says the trailing brief-commit goes "after step 4 Verify succeeds, before the success report," but the actual flow has step 5 (Codeguide update) between Verify (4) and Report (6); the discussion never names step 5, leaving the exact insertion point (after 5? new 5.5?) slightly underspecified.
**Fix:** State the step lands after step 5 Codeguide and before step 6 Report (i.e. as a new step 5.5 / start of step 6), and note Rollback covers "steps 2-5" so the post-5 brief commit is intentionally outside rollback (consistent with capturing successful state).

### [NOTE] git add error-behavior assumption left implicit for non-existent dir
**Section:** Decisions / Gap B guard
**Issue:** The guard rationale rests on `git add _mill/briefs/` failing with "did not match any files" when the dir is absent; this is asserted but the planner may instead reach for pathspec-magic (`':(exclude)'`) or `--ignore-unmatch`, diverging from the existing mill-go/mill-plan pattern.
**Fix:** Pin the guard form to the `if [ -d <wt>/_mill/briefs ]; then git -C <wt> add _mill/briefs/; fi` shape already given, and note `--ignore-unmatch` is rejected (silent, non-uniform with siblings).

## Verdict

APPROVE
Scope is precise and source-grounded; two NOTEs refine placement and guard mechanics only.
MILL_REVIEW_END
