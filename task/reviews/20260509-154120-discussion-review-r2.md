I have enough to write the review. The key finding is in `_spawn_and_open`'s pre-snapshot call versus the existing test's `side_effect` count.

# Review: 42 (A) — millpy-vscode rework: hybrid spawn/pick + filter active editors

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-09
```

## Findings

### [GAP] Existing "no active worktrees → spawn" test breaks under new design
**Section:** § Technical context — Existing test compatibility
**Issue:** `_spawn_and_open` performs its own `discover_active_worktrees` pre-snapshot call before invoking spawn. The existing test (verified at `test-millpy-vscode.py:329`) supplies `side_effect=[[], [(wt_new, …)]]` — only 2 values for what will now be 3 calls (initial in `main()` + pre-snapshot in `_spawn_and_open` + post-snapshot). The 3rd call raises `StopIteration`. The discussion's "Existing test compatibility" claim that this test "continues to pass" is factually wrong.
**Fix:** Either add a 3rd side_effect value (`[[], [], [(wt_new, …)]]`), or redesign `_spawn_and_open` to accept the already-known active list as the `pre` snapshot so the initial `main()` query doubles as the pre-snapshot (no extra call).

### [NOTE] `.path` vs `[0]` notation inconsistency for pre-snapshot
**Section:** § Decisions — post-spawn-identification (step 1) vs. § Technical context (step 4)
**Issue:** `discover_active_worktrees` returns plain `list[tuple[Path, str, str]]` (verified in `_spawn_core.py:154`). The Decisions section step 1 writes `{entry.path for entry in …}` — `AttributeError` at runtime. Technical Context step 4 correctly uses `e[0]`.
**Fix:** Normalise to index access (`entry[0]`) throughout the discussion.

## Verdict

GAPS_FOUND
One blocking gap: the existing test compatibility claim is wrong and will misdirect the plan.