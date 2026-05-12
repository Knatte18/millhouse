# Review: 53 (A) — Speed up PS1 wrappers by invoking venv Python directly

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-12
```

## Findings

### [GAP] Standalone render() call in test-shortcut-wrapper.py not addressed
**Section:** Testing — test-shortcut-wrapper.py
**Issue:** The testing section says to update `write_all()` call sites but not the standalone `render(TEMPLATE_PATH, {"SCRIPT": "millpy-status"})` at line 23 of the test file; once the template gains a `SCRIPT_PATH` token, `_render.py` raises `KeyError` on that call before any assertion runs.
**Fix:** Add to the testing instructions: update the direct `render()` call at line 23 to also pass `"SCRIPT_PATH"` (e.g., `str(fake_latest_path / "scripts" / "millpy-status.py")`).

### [GAP] Two existing filter tests break after --filter-open change
**Section:** Testing — "Existing picker and --slug tests unaffected"
**Issue:** `filter_excludes_open_worktree` (line 535) and `filter_empties_list_calls_spawn_then_opens` (line 581) both call `main([])` without `--filter-open` and assert that probe-based filtering occurs; with the default-no-probe change neither test can satisfy its assertions.
**Fix:** State explicitly that these two tests must be updated to call `main(["--filter-open"])` alongside their existing probe mocks.

### [GAP] Lazy import removes module attribute relied on by existing mock paths
**Section:** Scope / Technical Context / Testing — test-millpy-vscode.py
**Issue:** Moving `import _vscode_processes` inside `_filter_open_worktrees` makes it a local variable, not a module attribute; `patch("mill_vscode._vscode_processes.find_open_vscode_paths", ...)` is used across at least ten existing tests (lines 87, 212, 258, 310, 532, 579, 623, 670, 780, 819) and all raise `AttributeError` at patch setup time.
**Fix:** Specify how tests should mock after the lazy import — either import `_vscode_processes` at the top of the test file and patch `"_vscode_processes.find_open_vscode_paths"`, or (simpler) keep the module-level import in `millpy-vscode.py` and only gate the *call* to `_filter_open_worktrees` on `--filter-open` (the import cost itself is negligible).

## Verdict

GAPS_FOUND
Three test-plan gaps would produce immediately failing unit tests across both changed test files.