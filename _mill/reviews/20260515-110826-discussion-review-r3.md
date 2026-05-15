# Review: Wrap claude -p via psmux to use subscription instead of API credits

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: C:\Code\millhouse\wts\claude-p-wrapper\_mill\discussion.md
date: 2026-05-15
```

## Findings

### [NOTE] Poll-loop termination condition ambiguous
**Section:** `### Dual marker protocol` decision
**Issue:** "Idle-prompt-empty AND end-marker-on-own-line is the dual idle signal" reads as requiring both conditions; fixture 3 (`with-status.txt`) shows extraction succeeds before the idle prompt returns (a status line trails the end marker), so the idle-prompt check is not load-bearing — but the plan writer may implement both unnecessarily.
**Fix:** Clarify the poll loop rule: attempt `extract_response` on every capture; stop on success; interpret `MarkerNotFoundError` as continue-polling; idle-prompt check is optional belt-and-suspenders, not a gate.

## Verdict

APPROVE
All decisions are made, scope is tight, testing is fully enumerated, feasibility claims are source-verified.