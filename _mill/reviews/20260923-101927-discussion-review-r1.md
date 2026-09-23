MILL_REVIEW_BEGIN
# Review: mill-setup/wiki/docs/build-env: misc small bugs, round 3

```yaml
duration_s: 238.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [NIT:consistency] #1127 test-file claim contradicts repo state
**Demoted-from:** BLOCKING
**Section:** Decision `1127-denylist-shape` / Testing `#1127`
**Issue:** The Decision states "No unit test file exists yet for `_claude_settings.py` — mill-plan's batch adds one," but `plugins/mill/unit_tests/test-claude-settings.py` already exists and already covers `merge_permission_allowlist` and `MILL_SUBAGENT_TOOLS` in full (creation, preservation, idempotency, frontmatter-union checks). The Testing section's own hedge — "mirroring `merge_permission_allowlist`'s existing test conventions if a `test-claude-settings.py` pattern exists elsewhere ... if not, follow ..." — shows this wasn't actually confirmed before the flat Decision claim was written; the two sections disagree with each other and the Decision is the one that's wrong.
**Fix:** Correct the Decision to state the file exists and the batch extends it with `reconcile_destructive_denylist` coverage, not creates a new file — otherwise a plan writer risks scaffolding a duplicate/colliding file or overwriting existing coverage.

### [NIT:design] DESTRUCTIVE_DENY system-tree list completeness unstated
**Section:** Decision `1127-denylist-shape`
**Issue:** The prefix-matched system-tree set is limited to `/etc`, `/usr`, `/var`, `/boot`; other conventionally destructive roots (`/root`, `/opt`, `/bin`, `/lib`) are absent with no stated rationale for the cutoff, and the discussion gives no indication whether this list is the referenced issue's full proposal or the discussion's own paraphrase of it.
**Fix:** Confirm the list matches the source issue verbatim before mill-plan locks it in as "adopt as-is."

## Verdict

APPROVE
One BLOCKING: #1127's Decision section asserts a checked-but-false fact about existing test coverage.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
