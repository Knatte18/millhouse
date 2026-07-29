MILL_REVIEW_BEGIN
# Review: Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (per harness-reported model ID)
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] commit_sha length check: Scope and Decision text contradict each other
**Section:** Scope > In (bullet 5) vs Decisions > "commit_sha: brief wording + one finalize gap"
**Issue:** Scope explicitly requires the new validation to accept "either a 40-char SHA-1 or a 64-char SHA-256 hex string, not hardcoded to 40," but the Decision restates the same fix as checking for "a well-formed 40-char hex SHA" — silently dropping the SHA-256 branch the Scope bullet warned against hardcoding away. Testing (§Testing, `_implementer_common.py` case) only exercises the 40-char path, so the discrepancy isn't caught either.
**Fix:** Reconcile the two passages — either both explicitly state "40-or-64-char hex," or the Scope bullet's future-proofing language is dropped as unnecessary; whichever is chosen, the Testing bullet should name a concrete expected regex/length set so a plan writer doesn't have to guess which of the two conflicting descriptions to implement.

### [NOTE] Real-remote fixture placement (unit_tests/ vs integration_tests/) left as an open confirm-with-mill-plan item
**Section:** Testing > `_archive_tag.py`
**Issue:** CLAUDE.md states `unit_tests/` uses "in-memory/tempfile fixtures; no real git/LLM," yet the plan is to extend `test-archive-tag-conflict.py` (already in `unit_tests/`, already using real local git) with a bare-repo "remote" and simulated push rejections, and the discussion punts the unit-vs-integration placement question to mill-plan rather than deciding now.
**Fix:** Non-blocking since it's explicitly flagged for mill-plan and other consolidation mechanics are deferred the same way elsewhere in this discussion; consider pre-deciding it here to save a plan-review round-trip, but not required.

## Verdict

GAPS_FOUND
One GAP: contradictory 40-char vs 40-or-64-char commit_sha validation spec between Scope and Decisions.
MILL_REVIEW_END
