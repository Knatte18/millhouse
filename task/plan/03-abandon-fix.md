# Batch: abandon-fix

```yaml
task: "35 (A) — Centralize path resolution across all three modes"
batch: abandon-fix
number: 3
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-abandon.py
depends-on: [1]
```

## Batch Scope

Resolve GitHub issue #207: `millpy-abandon.py` reads `wiki_path / "active" / slug / "status.md"` (pre-task-32 layout) and commits the phase-flip to the wiki. Both are wrong post-task-32; status.md lives at `<active_hub>/task/status.md` on the task branch, and the wiki only holds `Home.md`.

Card 5 updates `test-abandon.py` to scaffold task-branch status.md (not wiki status.md) and to assert the commit lands on the task branch. Card 6 changes `millpy-abandon.py` accordingly. The trampoline pattern in the existing tests is preserved — only the mocked `_paths` module gains a `resolve_active_hub` stub, and the mocked `_wiki` module's `write_commit_push` assertion changes to mocks of `_subprocess_util.run` for git ops.

## Cards

### Card 5: update abandon tests for task-branch status.md and commit target

- **Context:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_builder_lock.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-abandon.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Refactor `_make_worktree` (currently at `test-abandon.py:39-51`) to write `status.md` at `<wt>/task/status.md`, not at `<wiki>/active/<slug>/status.md`. Drop the `wiki = tmp / "wiki"` and `status_path = wiki / "active" / slug / "status.md"` lines; replace with `status_path = wt / "task" / "status.md"` and adjust `_make_status_md` callers to write into the worktree's `task/` directory. Return tuple stays `(wt, mill_dir, status_path)`.

  Refactor `_make_trampoline` (currently at `test-abandon.py:54-81`):
  - Drop the `wiki_path` parameter — it is no longer needed.
  - Drop the `wm = types.ModuleType('_wiki')` block and its `write_commit_push` / `wiki_lock` mocks.
  - Add a `_paths` mock with `resolve_active_hub = lambda container, slug, *, cfg, git_root: Path(r'<wt-path>')` (the passed-in `wt` is the active hub when `hub_relative_path == "."`).
  - Add a `_paths` mock for `resolve_container_path = lambda p: Path(r'<container-path>')` and keep `resolve_git_root` / `resolve_wiki_path` from the existing trampoline.
  - Add a mock of `_subprocess_util.run` that records git commands. Stub it to return a successful `_make_run_result(stdout="", returncode=0)` for any `git -C <wt> add task/status.md`, `git commit`, or `git push` invocation. Save the recorded commands to a temp file the test can read back.

  Update each test case (a)-(g) to:
  - Pass the new `_make_trampoline(tmp)` signature (no `wiki_path` arg).
  - Assert the recorded git commands include `git -C <wt> add task/status.md` and `git -C <wt> commit -m "task: abandon <slug>"` and `git -C <wt> push`.
  - Drop assertions that reference wiki paths.
  - Read status via `_status.read_status(wt / "task" / "status.md")` (already done in case (a) — adapt to the new location).

  The trampoline file must continue to exec `millpy-abandon.py` via `importlib.util.spec_from_file_location('mill_abandon', ...)` so the `if __name__ == "__main__":` block does not fire.
- **Commit:** `test(abandon): scaffold task-branch status.md; assert task-branch commits`

### Card 6: switch millpy-abandon.py to resolve_active_hub and task-branch commit

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_builder_lock.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-abandon.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite `millpy-abandon.py`'s status-path resolution and commit logic.

  Replace the import line `import _wiki` (line 21) and remove the `_wiki` reference at lines 94-101. Add `import _subprocess_util` and `import _review_common` (the latter for `load_config`).

  Replace lines 48-55 (Step 3 + Step 4 — resolve paths and load status.md) with:

  ```python
  # Step 3: resolve paths via the centralized helpers (post-task-32: status.md
  # lives at <active_hub>/task/status.md on the task branch, not in the wiki).
  git_root = _paths.resolve_git_root()
  container_path = _paths.resolve_container_path(git_root)
  wiki_path = _paths.resolve_wiki_path(git_root)
  cfg = _review_common.load_config(wiki_path, git_root / ".millhouse")
  active_hub = _paths.resolve_active_hub(
      container_path, slug, cfg=cfg, git_root=git_root,
  )
  active_worktree = _paths.resolve_active_worktree(
      container_path, slug, cfg=cfg, git_root=git_root,
  )

  # Step 4: load status.md and check phase
  status_path = active_hub / "task" / "status.md"
  if not status_path.exists():
      sys.exit(f"Error: status.md not found for slug '{slug}'.")
  ```

  Replace the `with _wiki.wiki_lock(...) ... _wiki.write_commit_push(...)` block at lines 94-101 with task-branch git operations:

  ```python
  _status.append_phase(status_path, "abandoned", timestamp)
  add_result = _subprocess_util.run(
      ["git", "-C", str(active_worktree), "add", "task/status.md"]
  )
  if add_result.returncode != 0:
      sys.exit(f"Error: git add failed: {add_result.stderr.strip()!r}")
  commit_result = _subprocess_util.run(
      ["git", "-C", str(active_worktree), "commit", "-m", f"task: abandon {slug}"]
  )
  if commit_result.returncode != 0:
      sys.exit(f"Error: git commit failed: {commit_result.stderr.strip()!r}")
  push_result = _subprocess_util.run(
      ["git", "-C", str(active_worktree), "push"]
  )
  if push_result.returncode != 0:
      sys.exit(f"Error: git push failed: {push_result.stderr.strip()!r}")
  ```

  Update the module docstring at `millpy-abandon.py:1-6` from "Updates wiki/active/<slug>/status.md, commits, and pushes" to "Updates `<active_hub>/task/status.md` on the task branch, commits, and pushes".

  Drop the `import _wiki` line. Keep `import _builder_lock`, `import _active`, `import _paths`, `import _status`. Add `import _subprocess_util` and `import _review_common`.

  After this card lands, the verify command (`test-abandon.py`) must pass for all seven test cases (a)-(g).
- **Commit:** `fix(abandon): resolve status.md via active_hub; commit to task branch (#207)`

## Batch Tests

The verify command runs `test-abandon.py`. All seven existing test cases (a) happy-path, (b) hub-check, (c) phase=abandoned, (d) phase=done, (e) non-stale lock, (f) stale lock, (g) missing status.md are updated in Card 5 to use the new layout and assertions. Card 6's implementation makes them pass.
