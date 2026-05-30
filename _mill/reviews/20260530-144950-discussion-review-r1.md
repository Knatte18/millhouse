# Review: Replace powershell subprocess with winreg in mill-setup

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-30
```

## Findings

### [NOTE] Out-scope describes .ps1 wrappers; code generates .cmd
**Section:** Scope — Out
**Issue:** The discussion says Phase 4.7's `_shortcuts.write_all` step "generate `.ps1` forwarder files", but `_shortcuts.py` currently generates `.cmd` files and deletes legacy `.ps1` wrappers. SKILL.md Phase 4.7's own header ("PS1 shortcut wrappers") and description ("Creates `.millhouse/<script>.ps1` forwarders") are also stale.
**Fix:** Not a blocker — the out-scope rationale ("file generation, not a PowerShell subprocess") is still correct regardless of extension. Pre-existing doc staleness; note it but don't block the plan.

## Verdict

APPROVE
Discussion is complete and self-consistent; all decisions carry rationale and rejected alternatives; testing scenarios are fully specified; no blocking gaps found.