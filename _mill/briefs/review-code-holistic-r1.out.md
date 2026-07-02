Confirmed — `remove_safe` (used via `_worktree.remove_safe`) internally calls `_junction.strip_all_in_worktree` before the actual removal, satisfying the CLAUDE.md junction-strip-before-remove invariant automatically. Everything checks out. Final review below.

```
MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-02
```

## Findings

### [NIT] compute_baseline docstring omits ValueError from junction collision
**Location:** `plugins/mill/scripts/_verify_baseline.py:122-124`
**Issue:** The "Raises" section documents `RuntimeError` (rev-parse/worktree add) and `OSError` (junction creation), but `_junction.create` (`_junction.py:189-197`) actually raises `ValueError` when `link_path` already exists — a real path this function can hit in step 5.
**Fix:** Add `ValueError: link_path already exists (dependency dir collision)` to the docstring's Raises section. No functional impact — both callers (`millpy-implement.py`, `millpy-merge-in-subagent.py`) already catch broad `Exception`.

## Verdict

APPROVE
All 8 batches faithfully implement the plan; contracts, tests, and shared decisions are consistently applied across batch boundaries.
MILL_REVIEW_END
```