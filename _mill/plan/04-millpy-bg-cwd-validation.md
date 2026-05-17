# Batch: millpy-bg-cwd-validation

```yaml
task: 60 (A) — Branch/slug/claim fixes
batch: millpy-bg-cwd-validation
number: 4
cards: 2
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Add cwd validation to `millpy-bg.py`'s launcher (D7) — when the launcher is invoked from a worktree whose current branch does not resolve to a known task slug (e.g. the operator launched a review from the main worktree's terminal), the launcher must reject before spawning the worker. Uses the lenient `slug_from_branch` from batch 1 — this is the only inter-batch dependency in the plan. Tests cover the rejection paths in a new unit-test module.

External interface: the launcher's exit-code-1 plus stderr message becomes the contract that batch 5's SKILL preludes refer to.

## Cards

### Card 8: `millpy-bg.py` launcher validates cwd via `slug_from_branch` (D7)

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-bg.py`, modify `_launcher_main` (lines 94-151) to validate cwd between the `git_root` resolution (line 125) and the `scratch_dir` creation (line 127). Insert a `try` block that lazily imports `_paths`, `_config`, `_marker` and calls `_paths.resolve_wiki_path(Path(git_root))`, then `_config.load_config(wiki_path, Path(git_root))`, then `_marker.slug_from_branch(Path(git_root), wiki_path, cfg)`. The expected structure follows the discussion's "millpy-bg.py launcher validation post-D7 sketch":

  - `except _marker.MarkerError as exc`: run `_subprocess_util.run(["git", "-C", git_root, "branch", "--show-current"])`, derive `branch = result.stdout.strip() or "<detached>"`, print to stderr `f"mill-bg: cwd appears to be a non-task worktree (branch={branch!r}, error: {exc}). Switch to the task-worktree terminal before launching reviews."`, return 1.
  - `except (ValueError, SystemExit) as exc`: print to stderr `f"mill-bg: cannot validate cwd ({exc}). Verify cwd is a task worktree and config is loadable."`, return 1.

  Place the imports inside `_launcher_main` (NOT at module top) — the worker fast-path at lines 27-85 of the file must remain stdlib-only, as documented in the existing comment at lines 26-27. The `from pathlib import Path` already imported at line 91 covers the `Path(git_root)` use. Add `import _subprocess_util` (already imported at line 89 in the launcher branch) reference for the `git branch --show-current` call inside the `except MarkerError` block. Do not import `_paths`, `_config`, or `_marker` at module top — keep them inside the new `try` block.

  ASCII-only stderr message strings. The `f"{branch!r}"` rendering produces single-quoted Python repr (e.g. `'main'`), which is ASCII-safe. Do NOT call `_status.append_phase` or any wiki-mutating helper from the launcher — validation is read-only.
- **Commit:** `fix(bg): validate cwd before spawning worker (#312)`

### Card 9: New `test-bg-launcher.py` covers cwd-rejection paths (D9 part for D7)

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `_mill/discussion.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-bg-launcher.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-bg-launcher.py`. Module structure follows the same convention as other test files: `from __future__ import annotations`, imports at top, `if __name__ == "__main__": sys.exit(main())` at bottom. The module's `main()` runs each test function in turn, prints `PASS: <name>` on success, raises `AssertionError` on failure.

  Tests to include:
  1. `test_launcher_rejects_non_task_worktree()` — use `tempfile.TemporaryDirectory()` and existing helpers from `_test_helpers` (or replicate the minimal git-init pattern from `test-marker.py`) to build a fake git worktree on branch `main` with no matching slug in Home.md. Run `millpy-bg`'s `_launcher_main(["--slug", "test", "--", "/bin/true"])` (or via `subprocess.run([sys.executable, "millpy-bg.py", "--slug", "test", "--", "/bin/true"], cwd=fake_worktree)`). Assert exit code 1 and stderr contains the substring `cwd appears to be a non-task worktree`.
  2. `test_launcher_rejects_invalid_cwd_with_clean_error()` — fixture is a path that has no sibling wiki / no resolvable wiki (so `resolve_wiki_path` raises `ValueError`). Run the same launcher invocation and assert exit code 1 and stderr contains the substring `cannot validate cwd`.
  3. `test_launcher_accepts_valid_task_worktree()` — fixture: branch matches a known slug in Home.md (use `_make_task_worktree` from `_test_helpers`). Run the launcher with `--slug test -- /bin/true` (or `cmd /c rem` on Windows; use `sys.executable -c ""` for cross-platform). Assert exit code 0 AND the worker spawn completes — i.e., `pid=` and `log=` are printed on stdout. The test must NOT depend on `/bin/true` existing; pick a portable no-op (`sys.executable -c "pass"`).

  The first two tests cover the rejection path; the third asserts the validation does not regress the happy path. Subprocess invocation is preferable to in-process call where the worker spawns a real detached process — using subprocess.run with capture_output and a short timeout (e.g., 30s) keeps the test deterministic. Use `_test_helpers._make_task_worktree(...)` for fixture setup where possible; review its signature in `_test_helpers.py` before authoring.

  Register all three tests in `main()` at the bottom of the file. ASCII-only assertion messages.
- **Commit:** `test(bg): cover launcher cwd-validation paths`

## Batch Tests

`python plugins/mill/unit_tests/run-all.py` picks up the new `test-bg-launcher.py` automatically (the runner globs `test-*.py` under `unit_tests/`). The tests must work on Windows (this is a Windows-primary plugin) — Card 9's "/bin/true" anti-pattern is explicitly avoided. Use `sys.executable -c "pass"` for the no-op subprocess.
