MILL_REVIEW_BEGIN
# Review: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-27
```

## Findings

### [GAP] scrub_env() TDD unit test has no named target file
**Section:** Testing — TDD candidate
**Issue:** The `scrub_env()` pure-function test plan never names a file, and never mentions `plugins/mill/unit_tests/test-subprocess-util.py` — the existing dedicated test file for `_subprocess_util.py` (currently imports `_GRACE_SECONDS, popen_detached, run`) — despite otherwise line-numbered precision for the two other touched test files.
**Fix:** State that the TDD-candidate cases are added to `test-subprocess-util.py` (import `scrub_env` alongside `run`/`popen_detached`), or name an alternate file explicitly.

### [NOTE] STRIP_VARS citation mislabels the psmux call site
**Section:** Scope/Out; Technical context (`_llm_claude.py`)
**Issue:** "three `claude -p` subprocess launches (lines 332, 358, 384)" is imprecise — line 332's argv is `[sys.executable, millpy-claude-sub.py, ...]` (the psmux wrapper), not a direct `claude -p` call; only 358 and 384 build argv via `_build_argv` (which includes `-p`).
**Fix:** Reword to "three STRIP_VARS-filtered spawns (two direct claude -p calls plus one psmux-wrapper call)"; the out-of-scope conclusion itself is unaffected.

## Verdict

GAPS_FOUND
One GAP: the scrub_env() unit test has no assigned file despite an existing dedicated test file.
MILL_REVIEW_END
