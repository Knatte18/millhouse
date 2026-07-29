# Batch: is-inplace-topology-fix

```yaml
task: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout
batch: is-inplace-topology-fix
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-inplace.py test-paths.py test-review-common.py test-cleanup.py
depends-on: []
```

## Batch Scope

This batch delivers issue #735's fix: `_inplace.is_inplace` stops asking "does a directory exist at the canonical `<wts>/<slug>/` path" and instead asks "is `git_root` the main worktree", per the `is-inplace-topology-check` Shared Decision. The external interface (`is_inplace(slug, git_root, cfg) -> bool`) is unchanged — every caller keeps working transparently, only the detection result changes for the misdetected case. The batch also migrates every test fixture whose mocking currently targets the old `_inplace.resolve_worktrees_dir` mechanism to the new `_inplace.resolve_main_worktree_root` mechanism, and adds a `test-cleanup.py` case for the previously-unreachable `_resolve_inplace_mode` `"worktree"` fallback. No batch-local decisions beyond the two Shared Decisions in the overview.

## Cards

### Card 1: Rewrite `_inplace.is_inplace` to a git-topology check

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_inplace.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Replace the module-level `from _paths import resolve_worktrees_dir` import with `from _paths import resolve_main_worktree_root`.
  - Replace `is_inplace`'s body with: resolve `main_root = resolve_main_worktree_root(git_root)`, then return `git_root.samefile(main_root)`, falling back to `git_root.resolve() == main_root.resolve()` on `OSError` — the same fallback pattern `_paths.resolve_git_root` already uses (`_paths.py:145-150`) when comparing worktree paths.
  - `slug` and `cfg` remain unused parameters in the signature (API compatibility with all three call sites and the structural signature test).
  - Update `is_inplace`'s docstring: replace the "Detection criterion: no directory exists at `<worktrees-dir>/<slug>/`" line with a description of the git-topology comparison, and add a note that `slug`/`cfg` are retained for signature compatibility only and no longer participate in the check.
  - Update the module docstring's opening paragraph (currently: "no child worktree directory exists under `<container>/worktrees/<slug>/`") to describe the topology-based mechanism instead of path existence, and drop the stale `<container>/worktrees/<slug>/` example path (the actual default resolved by `_paths.resolve_worktrees_dir` is `<container>/wts/<slug>/`).
  - Update the module docstring's "Public API" summary line for `is_inplace` to match the new detection criterion.
  - `prompt_stale_worktree` is unaffected — do not touch it.
- **Commit:** `fix(inplace): replace path-existence check with git-topology comparison`

### Card 2: Migrate `test-inplace.py` fixtures to the topology mechanism

- **Context:**
  - `plugins/mill/scripts/_inplace.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-inplace.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Rename `_test_is_inplace_true_when_no_worktree_dir` (lines 21-34) to `_test_is_inplace_true_when_topology_matches`; replace its `patch("_inplace.resolve_worktrees_dir", return_value=tmp / "worktrees")` with `patch("_inplace.resolve_main_worktree_root", return_value=git_root)`; keep the `result is True` assertion.
  - Delete `_test_is_inplace_false_when_worktree_dir_exists_default` (lines 37-52) and `_test_is_inplace_false_when_worktree_dir_exists_override` (lines 55-73) — the "default vs. override `worktrees_dir`" distinction has no analog once `is_inplace` no longer calls `resolve_worktrees_dir`.
  - Add a new test `_test_is_inplace_false_when_topology_differs_735_regression` in their place: patch `_inplace.resolve_main_worktree_root` with `return_value=<a tmp path distinct from git_root>` (simulating a real separate worktree parked at a non-canonical location) and create no directory at the canonical `<wts>/<slug>/` path; assert `is_inplace` returns `False`. Add a one-line comment noting the old path-existence implementation would have wrongly returned `True` here (issue #735's exact false-positive).
  - Update `main()`'s `tests` list (lines 142-155) to drop the two deleted names and the old `_test_is_inplace_true_when_no_worktree_dir` name, adding `_test_is_inplace_true_when_topology_matches` and `_test_is_inplace_false_when_topology_differs_735_regression` in their place, in the same list position.
  - `_test_is_inplace_importable_and_callable` (structural signature test, asserting `params == ["slug", "git_root", "cfg"]`) and every `prompt_stale_worktree` test stay unchanged.
- **Commit:** `test(inplace): migrate is_inplace fixtures to topology mechanism, add #735 regression coverage`

### Card 3: Migrate `test-paths.py`'s six `_inplace.resolve_worktrees_dir` sites

- **Context:**
  - `plugins/mill/scripts/_inplace.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Re-grep `_inplace.resolve_worktrees_dir` in this file before editing — line numbers below are as of this writing and may have drifted.
  - In the `resolve_active_worktree` M2 in-place test (~lines 748-761) and M2+sub in-place test (~lines 763-776): replace `patch("_inplace.resolve_worktrees_dir", return_value=tmp_path / "wts-none")` (~lines 754, 769) with `patch("_inplace.resolve_main_worktree_root", return_value=git_root)`.
  - In the `resolve_active_worktree` `skip_slug_validation=True` in-place test (~lines 816-838) and the `resolve_active_hub` `skip_slug_validation=True` in-place test (~lines 973-989): both build a real git repo via `_test_helpers.init_minimal_git_repo` with no separate worktree, so the topology check resolves correctly with no mock needed — drop the `patch("_inplace.resolve_worktrees_dir", return_value=tmp_path / "wts-none")` (~lines 827, 978) entirely rather than replacing it.
  - In the `resolve_active_hub` M2 in-place test (~lines 928-941) and M2+sub in-place test (~lines 943-956): replace `patch("_inplace.resolve_worktrees_dir", return_value=tmp_path / "wts-none")` (~lines 934, 949) with `patch("_inplace.resolve_main_worktree_root", return_value=git_root)`.
  - Every replaced patch uses `return_value=git_root` (the fixture's own `git_root` variable already in scope at that point) to simulate in-place mode, matching the fixture's existing expected outcome (`got == git_root`) at each of these four sites.
- **Commit:** `test(paths): migrate resolve_active_worktree/resolve_active_hub in-place fixtures to topology mechanism`

### Card 4: Migrate `test-review-common.py`'s two `_inplace.resolve_worktrees_dir` sites

- **Context:**
  - `plugins/mill/scripts/_inplace.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In the `resolve_path` M2 in-place test (~lines 559-576) and M2+sub in-place test (~lines 606-623): add `patch("_inplace.resolve_main_worktree_root", return_value=git_root)` to the `with (...)` block alongside the existing `patch("_paths.resolve_main_worktree_root", return_value=git_root)` (~lines 567, 614), and remove the now-obsolete `patch("_inplace.resolve_worktrees_dir", return_value=worktrees_dir)` (~lines 568, 615) from both blocks.
  - Re-grep before editing — line numbers may have drifted.
- **Commit:** `test(review-common): add _inplace.resolve_main_worktree_root patch to resolve_path in-place fixtures`

### Card 5: Add `test-cleanup.py` coverage for `_resolve_inplace_mode`'s topology outcomes

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_inplace.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a new top-level test function `test_resolve_inplace_mode_topology_outcomes()` directly after `test_is_live_phase()` (currently ends at line 183, before `def main() -> int:` at line 185), following the same style as `test_scan_orphan_portals`/`test_is_live_phase` (plain assertions + `print("PASS ...")`, no pytest fixtures).
  - The function calls `_resolve_inplace_mode` (module-level alias `_resolve_inplace_mode = mod._resolve_inplace_mode`, already bound at test-cleanup.py:25) directly — not through `apply_plan` — patching only `mill_cleanup._inplace.resolve_main_worktree_root` (never `mill_cleanup._resolve_inplace_mode` itself, unlike every other test in this file).
  - Build a `SlugRecord(slug="my-task", worktree_path=hub_root, branch="impl/my-task", home_marker="active")` (same constructor shape as the existing call at test-cleanup.py:670-675) with `hub_root` a bare `tmp_path / "hub"` directory created via `.mkdir()` — do not create a directory at `<worktrees_dir>/my-task`, so the stale-worktree-edge branch (`worktree_dir.is_dir()` at `millpy-cleanup.py:426`) is never triggered.
  - Patch `mill_cleanup._marker.slug_from_branch` with `return_value="my-task"` (matching `record.slug`, so the early-return guard at `millpy-cleanup.py:414-415` is not triggered) and `mill_cleanup._subprocess_util.run` with a fake matching the `_fake_run2` pattern (test-cleanup.py:679-688) that returns `stdout="impl/my-task\n"`, `returncode=0` for the `branch --show-current` call.
  - Case A (in-place): additionally patch `mill_cleanup._inplace.resolve_main_worktree_root` with `return_value=hub_root`; call `_resolve_inplace_mode(record, hub_root, wiki_path, cfg={})`; assert the result equals `("inplace", "impl/my-task")`.
  - Case B (worktree): additionally patch `mill_cleanup._inplace.resolve_main_worktree_root` with `return_value=<a tmp path distinct from hub_root>`; call `_resolve_inplace_mode(record, hub_root, wiki_path, cfg={})` again; assert the result equals `("worktree", "")`. Add a one-line comment noting this exercises `millpy-cleanup.py:437`'s fallback, which was unreachable before this task's topology rewrite (the old `is_inplace` recomputed the same path-existence check the caller had already confirmed `False`, so it always returned `True` at this call site).
  - `wiki_path` can be any `tmp_path / "wiki"` `Path` — it is only forwarded to `_marker.slug_from_branch`, which is patched.
  - Register the call by adding `test_resolve_inplace_mode_topology_outcomes()` immediately after the existing `test_scan_orphan_portals()` / `test_is_live_phase()` calls inside `main()`'s try block (currently at lines 1425-1426).
- **Commit:** `test(cleanup): add _resolve_inplace_mode coverage for both post-fix topology outcomes`

## Batch Tests

`verify:` runs `run-all.py --only test-inplace.py test-paths.py test-review-common.py test-cleanup.py` — the four files this batch edits. Each file is a self-contained script invoked as a subprocess by `run-all.py`; `test-inplace.py` and `test-paths.py`/`test-review-common.py`/`test-cleanup.py` all follow the existing `main() -> int` + `if __name__ == "__main__": sys.exit(main())` convention already present in each file (Card 5 adds one new top-level test function to `test-cleanup.py`'s existing pattern, matching `test_scan_orphan_portals`/`test_is_live_phase`). No other test files import `_inplace` or `_resolve_inplace_mode`, so this scope is exhaustive for the batch's edits — confirmed via `grep -rl "_inplace" plugins/mill/unit_tests/` returning exactly these four files.
