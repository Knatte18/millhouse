# Review: mill-merge / fixer teardown recovery

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md (round 2)
date: 2026-05-27
```

## Findings

### [NOTE] `_status.read_full` raises ValueError, not FileNotFoundError
**Section:** Technical Context — mill-go/SKILL.md bullet
**Issue:** The discussion states "This crashes on `FileNotFoundError` when `status_path` is gone." `_status.read_full` (line 629–630 of `_status.py`) does its own `status_path.exists()` check and raises `ValueError`, not `FileNotFoundError`.
**Fix:** Update the description to `ValueError`; the proposed `if not status_path.exists():` guard is identical regardless, so no fix logic changes.

## Verdict

APPROVE
One minor NOTE on exception-type description; all technical claims verified against source; fix logic is correct throughout.