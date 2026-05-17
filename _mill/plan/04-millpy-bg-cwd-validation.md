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
  - `plugins/mill/unit_tests/test-millpy-bg.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-bg.py`, modify `_launcher_main` (lines 94-151) to validate cwd between the `git_root` resolution (line 125) and the `scratch_dir` creation (line 127). Insert a `try` block that lazily imports `_paths`, `_config`, `_marker` and calls `_paths.resolve_wiki_path(Path(git_root))`, then `_config.load_config(Path(git_root), Path(git_root))`, then `_marker.slug_from_branch(Path(git_root), wiki_path, cfg)`. **Argument-order note:** `_config.load_config(repo_root, worktree_root)` takes the hub repo root as its first arg, NOT the wiki path. The discussion's post-D7 sketch incorrectly passed `wiki_path` as the first arg; the plan corrects this to `Path(git_root), Path(git_root)` (matching every other call site of `load_config`, e.g. `millpy-claim.py:175`, `millpy-spawn.py:117`). Passing `wiki_path` as `repo_root` would (a) fail to locate `mill-config.yaml`, (b) internally retry `resolve_wiki_path(wiki_path)` which raises `SystemExit` (silently swallowed), and (c) leave `branch_prefix` unset (empty string), which then weakens D1's slug-fallback to accept the wrong terminal — the opposite of D7's intent.

  - `except _marker.MarkerError as exc`: run `_subprocess_util.run(["git", "-C", git_root, "branch", "--show-current"])`, derive `branch = result.stdout.strip() or "<detached>"`, print to stderr `f"mill-bg: cwd appears to be a non-task worktree (branch={branch!r}, error: {exc}). Switch to the task-worktree terminal before launching reviews."`, return 1.
  - `except (ValueError, SystemExit, OSError) as exc`: print to stderr `f"mill-bg: cannot validate cwd ({exc}). Verify cwd is a task worktree and config is loadable."`, return 1. **OSError inclusion**: after D1, `slug_from_branch` reads `Home.md` BEFORE the prefix check; if `resolve_wiki_path` returns a non-existent path (e.g., wiki clone missing after re-setup, or the launcher is invoked from a stale worktree), `(wiki_path / "Home.md").read_text()` raises `FileNotFoundError`, which is an `OSError` subclass. Without `OSError` in this catch, the launcher would crash with a raw traceback instead of the intended clean diagnostic.

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

  **Critical fixture layout constraint.** The existing `_test_helpers._make_task_worktree(tmp, slug, ...)` creates `tmp/worktree` + `tmp/wiki`. The launcher's `resolve_wiki_path(tmp/worktree)` does NOT find `tmp/wiki` from that layout — `tmp.name != "wts"`, so the resolver falls through to prefix-form and looks at `tmp/worktree.wiki` (which does not exist). Every test in this module MUST use a **container-form** layout: place the worktree at `tmp/wts/<repo-or-slug-name>/` and the wiki at `tmp/wiki/`. Then `resolve_wiki_path(tmp/wts/<name>)` correctly resolves to `tmp/wiki` (because `parent.name == "wts"` -> `parent.parent / "wiki"` = `tmp/wiki`). The test module must either (a) call `_make_task_worktree` and then move/re-init the result into a container-form layout, or (b) introduce a new small helper `_make_container_form_worktree(tmp, slug, title, *, branch_prefix="hanf/", phase="active") -> (worktree_path, wiki_path)` directly inside `test-bg-launcher.py` that mirrors `_make_task_worktree`'s git-init pattern but with the container-form layout. Option (b) keeps the test self-contained; do NOT modify `_test_helpers.py`'s shared helper — other tests that bypass `resolve_wiki_path` would break. The plan permits adding the small helper inline in `test-bg-launcher.py`.

  **Wiki config seeding.** The fixture helper MUST write `tmp/wiki/config.yaml` containing `spawn:\n  branch_prefix: "hanf/"\n` (or whatever the test exercises). Without this, `_config.load_config` produces an empty `branch_prefix`, and the launcher's call to `_marker.slug_from_branch` falls into the legacy bare-`/`-split path (lines 61-66 of `_marker.py`) instead of D1's prefix-aware path. The validation would then succeed for the wrong reason in the accept test — masking any regression in the post-D1 normal path. With `branch_prefix: "hanf/"` seeded, the branch in the accept fixture is `hanf/<slug>` and the validation exercises the production code path.

  Tests to include:
  1. `test_launcher_rejects_non_task_worktree()` — build a container-form fixture (with seeded `wiki/config.yaml` `branch_prefix: "hanf/"`) where the current branch is `main` and Home.md does NOT contain `main` as a slug. `slug_from_branch` raises `MarkerError` and the launcher hits the `except MarkerError` clause. Run via `subprocess.run([sys.executable, str(MILLPY_BG_PATH), "--slug", "test", "--", sys.executable, "-c", "pass"], cwd=worktree_path, capture_output=True, text=True, timeout=30)`. Assert exit code 1 and stderr contains the substring `cwd appears to be a non-task worktree`.
  2. `test_launcher_rejects_invalid_cwd_with_clean_error()` — fixture is a path that has no sibling wiki AND no `wts/` parent (e.g., a freshly initialised git repo directly under `tmp`). `resolve_wiki_path` will resolve to a prefix-form path that does not exist, so the inner `slug_from_branch` raises `FileNotFoundError` (an `OSError` subclass). Run the launcher with the same subprocess pattern, assert exit code 1 and stderr contains the substring `cannot validate cwd`.
  3. `test_launcher_accepts_valid_task_worktree()` — fixture is the container-form layout with seeded `wiki/config.yaml` `branch_prefix: "hanf/"`, the branch is `hanf/<slug>` (e.g. `hanf/test-task`), and Home.md contains `test-task` as a `[active]`-marked slug. This exercises the post-D1 normal prefix-strip path (NOT the bare-`/`-split fallback). Run the launcher with `["--slug", "test", "--", sys.executable, "-c", "pass"]`. Assert exit code 0 AND stdout contains both `pid=` and `log=` markers.

  Each test uses `tempfile.TemporaryDirectory()`, sets up the fixture, runs the subprocess with `capture_output=True, text=True, timeout=30`, and tears down via the context manager. `MILLPY_BG_PATH` is computed once at module top as `Path(__file__).resolve().parent.parent / "scripts" / "millpy-bg.py"`. ASCII-only assertion messages. Use `sys.executable -c "pass"` (portable, no `/bin/true` dependency).

  Register all three tests in `main()` at the bottom of the file.
- **Commit:** `test(bg): cover launcher cwd-validation paths`

## Batch Tests

`python plugins/mill/unit_tests/run-all.py` picks up the new `test-bg-launcher.py` automatically (the runner globs `test-*.py` under `unit_tests/`). The tests must work on Windows (this is a Windows-primary plugin) — Card 9's "/bin/true" anti-pattern is explicitly avoided. Use `sys.executable -c "pass"` for the no-op subprocess.
