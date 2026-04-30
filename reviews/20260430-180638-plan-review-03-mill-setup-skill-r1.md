# Review: 18 — par-E — Migrate Python invocation to `uv run` — 03-mill-setup-skill

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 03-mill-setup-skill
date: 2026-04-30
```

## Findings

### [BLOCKING] `pwsh` vs `powershell` inconsistency in Req 3
**Step:** Card 7, Requirement 3
**Issue:** Req 3 uses `pwsh -Command` (PowerShell 7) but the discussion.md Technical context explicitly says `powershell -Command` (PS5), and the environment is documented as PowerShell 5. `pwsh` is not guaranteed on Windows 11 Enterprise machines; if absent, Phase 4.7 silently fails and PYTHONPATH is never set.
**Fix:** Replace `pwsh -Command` with `powershell -Command` to match the discussion decision and guarantee availability on PS5-only machines.

### [BLOCKING] Bash/PS escaping bug — `$env:USERPROFILE` not escaped
**Step:** Card 7, Requirement 3 (the `pwsh -Command "..."` snippet)
**Issue:** Inside a bash double-quoted string, `$env` is treated as a bash variable (expands to empty). The plan's snippet `\$cache = '$env:USERPROFILE\.claude\...'` results in PowerShell receiving the literal string `:USERPROFILE\.claude\...` (missing the home prefix) — the single-quote PS-literal intent is irrelevant because bash expands `$env` before the string reaches PowerShell.
**Fix:** Escape as `\$env:USERPROFILE` (backslash-dollar so bash passes the literal `$env:USERPROFILE` to PowerShell) and wrap in double-quotes for PS variable expansion: `\$cache = "\$env:USERPROFILE\.claude\plugins\cache\millhouse\mill"`.

### [BLOCKING] Req 6 omits updating existing Phase 8 `.py` wrapper invariant
**Step:** Card 7, Requirement 6
**Issue:** The existing Phase 8 checklist line — "Every script in `_shortcuts.SHORTCUT_SCRIPTS` has a wrapper at `.millhouse/<script>.py`" — remains in the file. Req 6 says to "add a new bullet" for `.ps1`; it does not say to remove or replace the `.py` bullet. An implementer following the plan literally leaves both checks, and the `.py` check fails post-migration since wrappers are now `.ps1`.
**Fix:** Explicitly instruct replacement of the existing `.py` wrapper invariant line (not just addition of a new `.ps1` line).

### [NIT] Redundant `sys.path.insert` in Phase 4.7 snippet after migration
**Step:** Card 7, Requirement 4
**Issue:** The current Phase 4.7 `python -c` block contains `sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')`. Req 4 adds the `PYTHONPATH=...` inline prefix that makes this insert redundant, but the plan doesn't instruct its removal.
**Fix:** Add a note to Req 4 (or Req 2) to remove the `sys.path.insert` line from the Phase 4.7 snippet when applying the PYTHONPATH prefix.

## Verdict

REQUEST_CHANGES — two escaping/portability bugs in the Req 3 PowerShell snippet and a Phase 8 invariant gap.