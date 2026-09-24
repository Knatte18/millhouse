MILL_REVIEW_BEGIN
# Review: Remove batch review (plan-review.batch / code-review.batch)

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [BLOCKING:scope] mill-plan/SKILL.md enumeration misses 3 live `--holistic-only` sites
**Section:** Scope > In > Skills > `mill-plan/SKILL.md`
**Issue:** The bullet names only line ~473 and lines ~528-530, but the same file uses `--holistic-only` as an operative dispatch argument at line 471 (`<args> = --holistic-only`) and again at line 558 ("exactly as step 2's dispatch above"), and references the doomed per-batch scope printing at line 510 ("a per-batch scope, should batch plan review ever be enabled, prints one line per scope"). Once `--holistic-only` is dropped from `millpy-review-plan.py`, lines 471 and 558 dispatch a flag that no longer exists.
**Fix:** Enumerate mill-plan/SKILL.md by grepping the file itself for `--holistic-only|--no-holistic|roles.plan-review.batch` rather than citing fixed line numbers, so all operative dispatch sites are caught, not just the descriptive ones.

## Verdict

REQUEST_CHANGES
mill-plan/SKILL.md's explicit line-citation list is verified incomplete, leaving dead CLI flags in dispatch text.
MILL_REVIEW_END
