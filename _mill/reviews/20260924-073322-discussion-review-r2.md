MILL_REVIEW_BEGIN
# Review: Remove batch review (plan-review.batch / code-review.batch)

```yaml
duration_s: 271.1
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:scope] mill-plan/SKILL.md enumeration misses 3 live `--holistic-only` sites
**Demoted-from:** BLOCKING
**Section:** Scope > In > Skills > `mill-plan/SKILL.md`
**Issue:** The bullet names only line ~473 and lines ~528-530, but the same file uses `--holistic-only` as an operative dispatch argument at line 471 (`<args> = --holistic-only`) and again at line 558 ("exactly as step 2's dispatch above"), and references the doomed per-batch scope printing at line 510 ("a per-batch scope, should batch plan review ever be enabled, prints one line per scope"). Once `--holistic-only` is dropped from `millpy-review-plan.py`, lines 471 and 558 dispatch a flag that no longer exists.
**Fix:** Enumerate mill-plan/SKILL.md by grepping the file itself for `--holistic-only|--no-holistic|roles.plan-review.batch` rather than citing fixed line numbers, so all operative dispatch sites are caught, not just the descriptive ones.

## Verdict

APPROVE
mill-plan/SKILL.md's explicit line-citation list is verified incomplete, leaving dead CLI flags in dispatch text.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
