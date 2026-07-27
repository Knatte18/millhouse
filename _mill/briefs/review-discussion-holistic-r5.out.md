MILL_REVIEW_BEGIN
# Review: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: /home/knatte/Code/millhouse/wts/mill-vscode-spawn-session-leak/_mill/discussion.md
date: 2026-07-27
```

## Findings

### [GAP] Scope/In test-coverage bullet vs Testing's exemplar scope
**Section:** Scope > In (final bullet) vs. Testing
**Issue:** Scope/In requires assertions "at each of the four sites," but Testing (narrowed in round 4) covers only 3 exemplars and explicitly leaves `millpy-terminal.py:118` (Windows branch) unit-test-uncovered; round 4's narrowing reached Technical Context but not this bullet.
**Fix:** Reword the Scope/In bullet to match Testing's 3-exemplar scope, the same reconciliation round 4 already applied to Technical Context.

### [NOTE] Terminal.py mock-site audit mischaracterizes line 76
**Section:** Technical context (test-millpy-terminal.py breakdown)
**Issue:** The "5 capture only `cwd`" group includes the line-76 `mock_subprocess_run` helper, which actually stores `{"argv": argv, "cwd": cwd}` — both fields — unlike the other 4 sites (122/201/245/297), which store only the bare `cwd` value.
**Fix:** Reword the grouping (e.g. "5 sites don't capture full `kwargs`") or split line 76 out as its own sub-case.

## Verdict

GAPS_FOUND
Scope/In's test-coverage bullet still claims all four sites; Testing narrows real coverage to three exemplars.
MILL_REVIEW_END
