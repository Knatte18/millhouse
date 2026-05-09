# Review: 42 (A) — millpy-vscode rework: hybrid spawn/pick + filter active editors

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-09
```

## Findings

### [GAP] Post-spawn worktree identification for auto-open unspecified
**Section:** `unified-prompt`, `empty-filter-falls-through-to-spawn`, `§ test-vscode-processes.py`
**Issue:** Three paths (`--new`, Enter-at-prompt, filter-empties) all call `_load_spawn_main()([])` and then are expected to open `code <new launch_path>`. `millpy-spawn.main` returns only an `int`; the mechanism for identifying which newly spawned entry to pass to `code` is never stated. The existing "no active worktrees" test shows the intended pattern (pre/post discover diff, then auto-select-when-single), but auto-select-when-single is being removed in this rework — leaving the post-spawn identification strategy undefined. Additionally, `filter_empties_list_calls_spawn` only asserts spawn is invoked (not that `code` is subsequently called), contradicting the decision's "spawn-and-open" language.
**Fix:** State the post-spawn identification strategy — e.g., "snapshot pre-spawn `active` list; diff with post-spawn `discover_active_worktrees`; auto-open the single new entry." Also align the `filter_empties_list_calls_spawn` test assertion with the decision (add or remove the `code` invocation expectation).

### [GAP] POSIX parser macOS claim inconsistent with filter logic
**Section:** `posix-uses-ps-not-proc`, `§ Probe parser details`
**Issue:** The decision and probe-parser section claim "Linux + macOS portable," and give the example `/Applications/Visual Studio Code.app/Contents/MacOS/Electron --... code` as a covered case. But the described parser keeps only lines "whose first whitespace-separated token's basename starts with `code`." On macOS, the Electron binary path contains spaces; Python `.split()` on that line yields first-token `/Applications/Visual`, whose basename is `Visual` — not `code`. macOS VS Code processes are silently excluded, the probe returns an empty set, and the filter is never applied on macOS.
**Fix:** Either correct the macOS detection (e.g., also accept lines whose basename is `Electron` AND whose cmdline contains the launch path), or explicitly document that macOS silently degrades to no-filter via the existing probe-failure fallback, removing the macOS portability claim.

### [NOTE] `path_match_helper_endsep` test case produces apparent false positive
**Section:** `§ test-vscode-processes.py`, `path-comparison-resolved-substring`
**Issue:** `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo/src") → True`. Check 1 (`(s + os.sep) in cmdline`) gives `"/wts/foo/" in "code /wts/foo/src"` = True. This means a worktree with launch_path `/wts/foo` is treated as "open" when VS Code's cmdline shows it opened at `/wts/foo/src` — a false positive. The intent (validating the path-separator boundary sentinel for trailing-slash cmdlines) is not distinguished from this false-positive scenario.
**Fix:** Add a comment or a companion negative test to clarify the intended semantics: either this is expected (VS Code opened in any subdirectory counts as the worktree being open) or the test is wrong and should assert `False`.

## Verdict

GAPS_FOUND  
Two blocking gaps: post-spawn open identification strategy and macOS POSIX parser claim inconsistency.