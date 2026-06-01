# Review: smoke-test-psmux

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-06-01
```

## Findings

### [NOTE] Config validation step overstates what it verifies
**Section:** Testing → Config validation
**Issue:** The step claims to "confirm `_llm_claude._invoke` routes through psmux when called from the real dispatch path," but `test-claude-psmux.py` invokes `millpy-claude-sub.py` as a subprocess directly — it never exercises `_llm_claude._invoke`.
**Fix:** Reword to "confirm psmux still works after the flip" (what the test actually proves), or note that dispatch routing is separately covered by existing `test-llm-claude.py` unit tests.

## Verdict

APPROVE
All confirmed bugs match source code; decisions are grounded and complete; testing is specific.