# Review: 18 — par-E — Migrate Python invocation to `uv run`

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md (migrate-to-uv)
date: 2026-04-30
```

## Findings

### [GAP] `_llm_claude.py` has `shutil.which("claude")` — excluded from scope
**Section:** Technical Context / PATH truncation; Constraints
**Issue:** The claim "These are the only two scripts with external program lookups via `shutil.which`" is factually wrong. `_llm_claude.py:46` also calls `shutil.which("claude")` and is subject to the same WindowsApps PATH truncation. The Constraints section ("changes limited to `millpy-vscode.py` and `millpy-terminal.py`") would prevent the implementation agent from fixing it after they verify — leaving a known bug open in the review subsystem, which is the hot path for `mill-go`.
**Fix:** Either add `_llm_claude.py` to the PATH-fix scope (with the same `["cmd", "/c", "claude"]` pattern, or `shell=True`), or explicitly state why it is not subject to the same failure and does not need fixing.

### [GAP] `_shortcuts.py` change contradicts the Constraints section
**Section:** Scope (In) vs. Constraints
**Issue:** Scope declares `_shortcuts.py` as in scope for Python changes (template path update from `.py` to `.ps1`; deletion of old wrappers). The Constraints section says "All other scripts: no changes" with only `millpy-vscode.py` and `millpy-terminal.py` explicitly excepted. A plan writer cannot reconcile these without guessing intent.
**Fix:** Add `_shortcuts.py` as a third permitted exception in the Constraints section, or narrow the phrasing to "All other `millpy-*.py` user-callable scripts: no changes."

## Verdict

GAPS_FOUND  
Two internal contradictions; resolve before plan writing proceeds.