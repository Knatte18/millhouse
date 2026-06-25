MILL_REVIEW_BEGIN
# Review: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation -- holistic

```yaml
verdict: APPROVE
reviewer_model: claude-sonnet-4-6
reviewed_file: plan/ + plugins/mill/scripts/ + plugins/mill/unit_tests/
date: 2026-06-25
```

## Findings

### [NIT] `_delete_remote_branch` in cleanup checks one error pattern; abandon checks two

Location: `plugins/mill/scripts/millpy-cleanup.py` lines 414-423 vs `plugins/mill/scripts/millpy-abandon.py` line 126.

- The plan's Shared Decision documents two git stderr patterns that indicate an already-absent remote ref: `"remote ref does not exist"` and `"unable to delete ... remote ref does not exist"`.
- `millpy-abandon.py` checks both patterns (with `and "unable to delete" not in stderr_lower`) before calling `sys.exit`, making the toleration explicit.
- `_delete_remote_branch` in `millpy-cleanup.py` checks only `"remote ref does not exist"`. Errors that match `"unable to delete"` but not the substring are printed as non-fatal warnings rather than silently tolerated.
- Functionally harmless: git's full "unable to delete" message always contains "remote ref does not exist" as a substring, so the single-pattern guard suffices in practice. The inconsistency is with documented intent, not with runtime behavior.
- Suggested fix: add `or "unable to delete" in stderr_lower` to the tolerant condition, or update the comment to note that the single pattern subsumes the other.

## Verdict

APPROVE
MILL_REVIEW_END
