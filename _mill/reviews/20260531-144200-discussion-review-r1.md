# Review: replace-claude-p-with-psmux

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-31
```

## Findings

### [NOTE] `rows` bump absent from Scope In
**Section:** Technical context
**Issue:** "bump to 100 for safety" is stated in Technical Context but not listed in Scope In and has no Decision entry — a plan writer could omit it.
**Fix:** Add `rows=100` bump to the Scope In bullet for `millpy-claude-sub.py`, or add a brief Decision entry.

### [NOTE] Reuse idle check (line 200) not named in idle-detection-rewrite
**Section:** Decision: idle-detection-rewrite / Testing
**Issue:** `_wait_for_idle_prompt` at line 200 (reuse path, before submission) is a third call site; the decision names only boot wait and response wait. The `test-claude-sub.py` test list doesn't include a case for this check switching from `❯` to `for shortcuts`.
**Fix:** Add the reuse-path idle check to the decision's change description and add a matching test case.

### [NOTE] Phase 1 timeout behaviour unspecified
**Section:** Decision: idle-detection-rewrite
**Issue:** If Phase 1 (wait up to 10s for `esc to interrupt`) times out, the expected behaviour — fail immediately vs. fall through to Phase 2 — is not stated.
**Fix:** State explicitly (e.g., "Phase 1 timeout → raise RuntimeError immediately, do not enter Phase 2").

## Verdict

APPROVE
Discussion is complete and well-grounded; three minor NOTEs, no blocking gaps.