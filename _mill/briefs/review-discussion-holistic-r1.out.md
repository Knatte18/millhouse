MILL_REVIEW_BEGIN
# Review: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-27
```

## Findings

### [GAP] millpy-terminal.py: same leak, absent from Scope
**Section:** Scope (Out) / Problem
**Issue:** `millpy-terminal.py:118` and `:121` launch `claude --name <slug>` via bare `subprocess.run` with no `env=` (same "must keep its console — do NOT route through `_subprocess_util.run`" comment as the targeted picker at `millpy-vscode.py:274`), directly inheriting `CLAUDE_CODE_*` into a fresh top-level session — one hop more direct than the VS Code path this discussion fixes. It is a documented, shortcut-listed (`_shortcuts.py`), unit-tested entry point, but is never mentioned in Scope, unlike `millpy-spawn.py`/`_vscode.py`, which were explicitly investigated and ruled out with cited grep evidence.
**Fix:** Add `millpy-terminal.py`'s two launch sites to Scope/In, or add an explicit Out entry with the same kind of rationale given for `millpy-spawn.py`.

### [GAP] _llm_claude.py STRIP_VARS precedent not addressed
**Section:** Scope (Out) / Decisions > helper-location
**Issue:** `_llm_claude.py:82-90` already filters `os.environ` via a `STRIP_VARS` frozenset ("Git env vars that must NOT be inherited by spawned Claude sessions (see #367)") before three `claude -p` subprocess launches (lines 332, 358, 384) used by the review/implementer pipeline — but the set covers only `GIT_*`, not `CLAUDE_CODE_*`. This is a third live spawn site with the identical defect class, and its existence contradicts the helper-location decision's YAGNI rejection of a shared helper ("`millpy-spawn.py` and `_vscode.py` have no launch site to share the helper with") — `_llm_claude.py` is a real, current consumer of exactly this kind of env-filtering logic.
**Fix:** Scope should state explicitly whether `_llm_claude.py`'s spawned sessions are in/out of this fix (e.g., extend `STRIP_VARS` there too or defer with rationale), and helper-location's rejected-alternatives text should acknowledge this precedent.

## Verdict

GAPS_FOUND
Two live claude/code-spawn sites sharing the identical env-leak defect are unaddressed by Scope.
MILL_REVIEW_END
