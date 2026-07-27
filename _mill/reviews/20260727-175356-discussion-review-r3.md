MILL_REVIEW_BEGIN
# Review: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-27
```

## Findings

### [GAP] vscode.py mock-kwargs audit deferred vs. terminal.py's
**Section:** Technical context (test files bullet)
**Issue:** Terminal.py's 8 `subprocess.run` mocks are audited exactly (lines 76/122/201/245/297 need a signature change, lines 159/339/386 don't); the parallel vscode.py note punts ("needs auditing per-site... before deciding") even though source shows all 18 vscode.py mock sites (lines 74,120,158,200,246,298,342,389,424,522,569,615,662,720,772,812,863,903) discard kwargs entirely — unlike terminal.py, there is no partial split, 100% need updating.
**Fix:** State plainly that every vscode.py mock site needs the signature change, matching the precision already given for terminal.py, so a plan writer doesn't assume a terminal.py-like partial split.

### [NOTE] CLAUDE_CODE_ENTRYPOINT's marker-vs-config status unconfirmed
**Section:** Decisions > scrub-scope
**Issue:** The allowlist keeps `CLAUDE_CODE_ENTRYPOINT` on the strength of the source issue's own hedge ("likely CLAUDE_CODE_ENTRYPOINT"); round 2 proved same-prefix vars (`CLAUDE_CODE_USE_BEDROCK`/`VERTEX`) can be persistent config rather than session markers, but that same scrutiny was never reapplied to confirm ENTRYPOINT itself is session-scoped rather than a stable setting.
**Fix:** Add a line confirming (or citing evidence) that `CLAUDE_CODE_ENTRYPOINT` is set per-invocation, not user-configured, before treating the allowlist as final.

## Verdict

GAPS_FOUND
One GAP: incomplete/deferred test-mock audit for vscode.py where terminal.py's is exact.
MILL_REVIEW_END
