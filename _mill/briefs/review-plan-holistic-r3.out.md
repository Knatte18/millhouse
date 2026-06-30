Based on a thorough cross-check of all three batch files against the cited source files (`_marker.py`, `wiki/_client.py`, `wiki/__init__.py`, `millpy-review-discussion.py`, `_review_discussion.py`, `mill-start/SKILL.md`, `mill-go/SKILL.md`, `millpy-implement.py`, `millpy-fix.py`, `_implementer_common.py`, `_status.py`, and the four unit-test files), I verified line numbers, function signatures, exception hierarchies, existing test patterns, and the Batch Index DAG. All factual claims in the plan check out against the actual code. No BLOCKING issues found.

Two NIT-level gaps worth fixing before implementation:

MILL_REVIEW_BEGIN
# Review: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize -- holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [NIT] Card 1 Context omits mill-go/SKILL.md despite citing its dispatch contract
**Location:** Batch 1 / Card 1
**Issue:** Requirements repeatedly reference mill-go/SKILL.md's "## Agent-mode dispatch" `<args>` semantics; per that section's own step 2/step 6, finalize is invoked with "the same standard arguments" as prepare, so `--max-rounds` is actually also passed to the finalize call (harmlessly, since `--stage finalize` ignores it) -- not "never sent" as the card's phrasing implies.
**Fix:** Add `plugins/mill/skills/mill-go/SKILL.md` to Card 1's Context so the implementer can verify this is inert rather than assuming finalize never receives the flag.

### [NIT] Card 4's task_data retry test under-specifies side_effect call count
**Location:** Batch 2 / Card 4, `test_task_data_retries_on_cold_daemon()`
**Issue:** After Card 2's fix, `task_data()` makes 3 total `list_tasks_brief` calls (1 fail + 1 retry-success inside its internal `slug_from_branch()` call, plus 1 more direct call from `task_data()` itself) -- a naively copied 2-item `side_effect` list (mirrored from the sibling `slug_from_branch` test) will raise `StopIteration` on the third call.
**Fix:** Specify a 3-item `side_effect` list (`[WikiStartupError, tasks, tasks]`) or an `itertools.repeat`-based side_effect for this specific test.

## Verdict

APPROVE
Plan is well-grounded in source; only two NIT-level specificity gaps, neither blocking.
MILL_REVIEW_END
