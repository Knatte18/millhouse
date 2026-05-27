# Review: V3 wiki adoption follow-up bugs

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-27
```

## Findings

### [GAP] test-junction.py claimed existing but doesn't exist
**Section:** Testing — `test-junction.py (existing, extend for #385)`
**Issue:** No `test-junction.py` exists in `plugins/mill/unit_tests/`; the full test listing confirms it is absent. A plan step written to "extend" this file will fail at implementation.
**Fix:** Change the label to `test-junction.py (new, create for #385)` so the plan writer generates a create step, not an extend step.

### [NOTE] test-wiki-protocol.py ambiguity already resolved
**Section:** Testing — `test-wiki-protocol.py or test-wiki-server.py (existing/new, #383 + #384)`
**Issue:** `test-wiki-protocol.py` already exists; the "(existing/new)" hedge is unnecessary noise.
**Fix:** Drop the "or test-wiki-server.py (existing/new)" qualifier and write "test-wiki-protocol.py (existing, extend for #383 + #384)" to match reality.

## Verdict

GAPS_FOUND
One GAP: `test-junction.py` does not exist; "existing, extend" must be corrected to "new, create".