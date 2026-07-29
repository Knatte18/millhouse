MILL_REVIEW_BEGIN
# Review: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

Verified against source: `_inplace.py` (current path-existence body, module-level `from _paths import resolve_worktrees_dir`, stale `<container>/worktrees/<slug>/` docstring example), `_paths.py:228` `resolve_main_worktree_root` (uses `_pygit2_util.resolve_common_dir_parent`), `_paths.py:145-150` samefile/OSError-fallback pattern, `_paths.py:418` lazy `import _inplace` inside `resolve_active_worktree` (confirms no circular-import risk), `_paths.py:433` and `millpy-cleanup.py:434` call sites (line numbers exact), `mill-merge/SKILL.md:21` Entry Step 1 call and lines 155-187 Step 5 restore block including the line-185 false no-op prose, `mill-merge-in/SKILL.md:37` `OLD_CHK_SHA=... || true` precedent. All three `is_inplace` call sites confirmed exhaustively (grep found no fourth). `_resolve_inplace_mode`'s dead-code claim for the `("worktree","")` fallback verified: the caller already confirms `worktree_dir.is_dir()` is False before reaching `is_inplace`, which under the old body is a tautological re-check.

Testing section line references also verified precisely: `test-inplace.py` lines 21-73 (three tests, patching `_inplace.resolve_worktrees_dir`); `test-paths.py` sites at 754/769/827/934/949/978 (827 and 978 confirmed as real-git-repo fixtures via `_test_helpers.init_minimal_git_repo`, others confirmed as bare-mkdir fixtures needing the new patch); `test-review-common.py` sites at ~567-568/614-615 (existing `_paths.resolve_main_worktree_root` patch is for a different resolution-chain code path, correctly distinguished from the new `_inplace.resolve_main_worktree_root` patch needed); `test-cleanup.py` line ~702 stale-worktree reference and lack of any test exercising `is_inplace`'s real body inside `_resolve_inplace_mode` (existing tests all patch `_resolve_inplace_mode` itself). `test-merge.py` lines 593-611 comment confirmed to state the seeded-`status.md` workaround verbatim, substantiating the "no existing coverage of the true no-op case" claim.

No undecided items, no unaddressed failure modes, no scope ambiguity found. Prior-round gaps (caller inventory completeness, `test-cleanup.py` coverage, `test-merge.py` gap confirmation, `resolve_active_worktree`'s incorrect `prompt_stale_worktree` caller claim) are resolved and hold up under fresh re-verification against source in this round.

## Verdict

APPROVE
Discussion is decision-complete, source-verified, and free of unresolved gaps.
MILL_REVIEW_END
