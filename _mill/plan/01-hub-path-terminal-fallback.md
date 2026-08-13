# Batch: hub-path-terminal-fallback

```yaml
task: 'mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies'
batch: hub-path-terminal-fallback
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-paths.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #833: `_paths.resolve_hub_path()`'s terminal fallback returns the wrong worktree when a task worktree's own `.millhouse/config.local.yaml` is missing and this repo's own container-form layout (`hub_relative_path: .`) is in play. The main-worktree-stub check only redirects when `hub_relative_path != "."`, so for this repo the walk silently falls through to `return main_root` — the main worktree, not the worktree the caller is actually standing in. The fix is a one-line terminal-fallback change plus a regression test that reproduces the exact scenario via a real linked git worktree (not a single-repo fixture, since `main_root != git_root` only occurs with an actual `git worktree add` checkout — see Card 2).

No external interface change: `resolve_hub_path()`'s signature and every existing call site are untouched. This batch is fully self-contained.

## Cards

### Card 1: `resolve_hub_path` terminal fallback returns `git_root`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `resolve_hub_path()` (`plugins/mill/scripts/_paths.py:169-230`), change the terminal fallback return statement at line 228 from:
  ```
  return main_root
  ```
  to:
  ```
  return git_root
  ```
  `git_root` is the local variable already bound at line 191 (`git_root = resolve_git_root(cwd)`), in scope at line 228. Do not change any other line in the function — the cwd-walk primary strategy (lines 198-214) and the main-worktree-stub fallback (lines 216-226) are unaffected and already handle their documented cases correctly. Update the function's own docstring line `Terminal fallback: ``main_root`` (historic behaviour).` (around line 188) to read `Terminal fallback: ``git_root`` (the worktree actually being resolved from).` so the docstring does not contradict the new behavior.
- **Commit:** `fix(paths): resolve_hub_path terminal fallback returns git_root, not main_root (#833)`

### Card 2: regression test — task worktree with missing config.local.yaml falls back to its own git_root

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new assertion block inside `main()` in `test-paths.py`, placed immediately after the existing "Regression 2: Flat layout, resolve_task_path" block (the file's last existing `resolve_hub_path`-adjacent block, ending around line 379+ — read the current end of `main()` to find the exact insertion point after the last `print("PASS: ...")` line preceding the closing of `main()`'s `try:` block). Follow this file's own real-linked-worktree fixture pattern already used at the "Worktree-form: create a real linked worktree via subprocess" block (`test-paths.py` around line 594-609) — that block is the only place in this file that produces a genuine `main_root != git_root` split (a single-repo fixture without `git worktree add` always has `main_root == git_root`, which cannot reproduce #833's terminal-fallback divergence).

  Build the fixture:
  1. `tmp_path = Path(tmp)`, `wts_dir = tmp_path / "wts"`, `wts_dir.mkdir()`.
  2. `main_root = wts_dir / "millhouse"`, `main_root.mkdir()`, `subprocess.run(["git", "init", "--quiet", str(main_root)], check=True)`.
  3. Write `main_root / ".millhouse" / "config.local.yaml"` with content `hub_relative_path: .` (mkdir parents first) — this reproduces this repo's own container-form layout, where the main-worktree-stub's `hub_subpath != "."` gate never redirects.
  4. `linked_worktree = wts_dir / "feat"`; create it via `subprocess.run(["git", "-C", str(main_root), "worktree", "add", str(linked_worktree)], capture_output=True)` — the same subprocess call already used at the existing "Worktree-form" block.
  5. Do NOT create any `.millhouse/` directory anywhere inside `linked_worktree` — this reproduces the exact #833 scenario (a task worktree whose own local config is missing).
  6. `got = _paths.resolve_hub_path(linked_worktree)`.
  7. `assert got == linked_worktree, f"task worktree with missing config.local.yaml: expected own git_root {linked_worktree}, got {got}"` — before the Card 1 fix this would have asserted `== main_root` and failed against the pre-fix `return main_root` line.
  8. `print("PASS: resolve_hub_path task worktree missing config.local.yaml -> falls back to own git_root, not main_root (#833)")`.
- **Commit:** `test(paths): regression for resolve_hub_path terminal fallback via real linked worktree (#833)`

## Batch Tests

`verify:` runs `test-paths.py` directly (single file, no `--only` needed). Card 2's new assertion block is the only new coverage; Card 1's fix is a one-line return-value change with no other observable surface, so no additional test file is touched.
