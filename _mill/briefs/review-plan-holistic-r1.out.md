MILL_REVIEW_BEGIN
# Review: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] Card 5's new test crashes with SystemExit before reaching `is_inplace`
**Location:** Batch 1 (is-inplace-topology-fix) / Card 5
**Issue:** `_resolve_inplace_mode` (`millpy-cleanup.py:423`) unconditionally calls `_paths.resolve_worktrees_dir(cfg, hub_root)` — which internally calls `_paths.resolve_main_worktree_root(hub_root)` — *before* the `worktree_dir.is_dir()` stale-worktree check and before the `_inplace.is_inplace(...)` call at line 434. Card 5's `hub_root` is a bare `tmp_path / "hub"` created via `.mkdir()`, not a real git repo, and the plan patches only `mill_cleanup._inplace.resolve_main_worktree_root` — never `mill_cleanup._paths.resolve_main_worktree_root` (or `_paths.resolve_worktrees_dir`). `_pygit2_util.resolve_common_dir_parent` will raise `GitOpsError` against the non-git directory, which `_paths.resolve_main_worktree_root` converts to `SystemExit` (`_paths.py:246-248`). `test-cleanup.py`'s `main()` only catches `AssertionError` (line 1790), so this `SystemExit` propagates uncaught, aborting the whole script before any later-registered tests run. This affects both Case A and Case B (the crash happens before the mode branch is reached).
**Fix:** Add `patch("mill_cleanup._paths.resolve_main_worktree_root", return_value=hub_root)` (mirroring the existing sibling test's pattern at `test-cleanup.py:705`) to both Case A and Case B's `with` blocks, alongside the `_inplace.resolve_main_worktree_root` patch.

### [BLOCKING] Card 7's "Repro" step cannot reproduce #736 — wrong git command ordering
**Location:** Batch 2 (step5-checkout-guard) / Card 7
**Issue:** After `git merge --squash task/guard-test` on `main`, `_mill/status.md` is staged in the index as a new file (main never had `_mill/` in its history). Card 7's "Repro" step immediately runs a bare `git checkout -- "_mill"` with no preceding `reset` — but `git checkout -- <pathspec>` restores from the *index*, and the path IS present there (staged by the squash), so this call succeeds (`returncode == 0`), not `!= 0` as the plan asserts. The real #736 failure only occurs *after* `git reset -q HEAD -- <pathspec>` un-stages the path (matching HEAD's absence) — exactly the order Step 5 itself uses (line 177 reset, then line 178 checkout), and exactly the order the *existing* `#648` repro sub-step follows (lines 721-728: `reset` then `checkout`, both `check=False`). Card 7's repro omits the reset, so the assertion `returncode != 0` will fail, raising `AssertionError` and failing the whole integration-test run before the "Fix" section is ever reached.
**Fix:** Run `git -C <repo> reset -q HEAD -- "_mill"` (check=False, unguarded) immediately before the bare unguarded `checkout -- "_mill"` repro call, matching the real Step 5 ordering and the existing `#648` repro's two-command structure.

## Verdict

REQUEST_CHANGES
Two BLOCKING test-authoring bugs (Card 5 SystemExit crash, Card 7 repro-order logic error) would break both batches' `verify:` commands as written.
MILL_REVIEW_END
