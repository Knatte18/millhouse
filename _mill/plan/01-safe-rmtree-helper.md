# Batch: safe-rmtree-helper

```yaml
task: (A) -- Central safe-rmtree helper + ban direct rmtree
batch: safe-rmtree-helper
number: 1
cards: 2
verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-safe-rmtree.py" && PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Ship the `_safe_rmtree` helper module plus its unit test, exposing
`safe_rmtree(path, *, allowed_root, ignore_errors=False)`. This batch
delivers only the API and its standalone test coverage. The
external interface that batch 2 consumes is exactly this function
plus the `_safe_rmtree.safe_rmtree` import path. Batch-local
decisions are all captured under `## Shared Decisions` in
`00-overview.md`; there are no batch-local divergences.

## Cards

### Card 1: Create `_safe_rmtree.py`

- **Context:**
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `_mill/discussion.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Deletes:** none
- **Requirements:**
  - Define module-level public function `safe_rmtree(path: Path, *, allowed_root: Path, ignore_errors: bool = False) -> None`. Order of operations inside the function: (1) resolve `path` and `allowed_root` via `Path(...).resolve()`; (2) refuse if `path` is or has-as-ancestor any blacklisted root (see below); (3) refuse if `path` is not equal-to or descendant-of `allowed_root`; (4) silent no-op return if `not resolved_path.exists() and not resolved_path.is_symlink()` (the symlink-check handles broken junctions); (5) refuse if `resolved_path` itself is a junction (`_is_reparse_point` true) or a symlink (`Path.is_symlink()` true); (6) walk-and-strip junctions/symlinks via `_walk_strip_reparse_points(resolved_path)`; (7) call `shutil.rmtree(str(resolved_path), ignore_errors=ignore_errors)`.
  - Refusal channel: every refusal path raises `SystemExit("[safe-rmtree] <one-line reason>: <path>")`. Reasons by case: "refuses to delete shared-state path" (blacklist match); "path outside allowed_root" (containment); "path is itself a junction -- use _junction.remove instead" (path-is-junction); "path is itself a symlink -- use _junction.remove instead" (path-is-symlink).
  - Blacklist construction: define a module-private function `_blacklist_for(allowed_root: Path) -> list[Path]` that calls `_paths.resolve_container_path(allowed_root)` inside `try: ... except (Exception, SystemExit):`, returning `[]` on failure. On success, the function returns `[container, container / "wiki", container / "portals", container / "wts" / container.name]` (each `.resolve()`-d). The "main repo worktree" path is derived as `container / "wts" / container.name` per CLAUDE.md `## Project shape` (main worktree directory name equals container name).
  - Blacklist comparison: `resolved_path == entry or entry in resolved_path.parents` for each entry. This catches both "delete the wiki" and "delete a parent of the wiki".
  - Reparse-point detection: define module-private `_is_reparse_point(p: Path) -> bool` that returns `False` on POSIX (`os.name != "nt"`). On Windows, return `os.path.isjunction(str(p))` when `hasattr(os.path, "isjunction")` else fall back to `bool(os.lstat(str(p)).st_file_attributes & 0x400)` wrapped in `try: ... except (OSError, AttributeError): return False`. Pattern mirrors `_junction.remove`'s logic at `plugins/mill/scripts/_junction.py:170-178`.
  - Walk-and-strip: define module-private `_walk_strip_reparse_points(root: Path) -> None` that uses `os.scandir(str(root))` (NOT `os.scandir(..., follow_symlinks=False)` -- that parameter does not exist on `scandir`). For each `DirEntry`: if `entry.is_symlink()` OR `_is_reparse_point(Path(entry.path))`, call `_junction.remove(Path(entry.path))` and continue (do not recurse). Else, if `entry.is_dir(follow_symlinks=False)`, recurse into it. The function returns `None` and does not delete real directories or files -- only strips junctions/symlinks. Wrap the iteration in a `try: ... finally: scandir.close()` block (or use `with os.scandir(...) as it:` form) so file handles are released on Windows before `shutil.rmtree` runs.
  - Imports at module top: `from __future__ import annotations`; `import os`; `import shutil`; `import sys`; `from pathlib import Path`; `import _junction`; `import _paths`. No `if __name__ == "__main__":` block.
  - Module docstring: 8-15 lines explaining purpose, public API, the wiki-wipe incident this guards against, and the relationship to `_junction.strip_all_in_worktree` (config-driven CRUD, complementary).
  - Function docstring on `safe_rmtree`: documents `path`, `allowed_root`, `ignore_errors` arguments; lists every refusal case with the matching `SystemExit` message; documents the strip-then-rmtree sequence; states POSIX vs Windows differences (`_is_reparse_point` is a no-op on POSIX; `entry.is_symlink()` runs cross-platform).
  - Logging: at function entry, `print(f"[safe-rmtree] starting: path={path} allowed_root={allowed_root}", file=sys.stderr)`. After successful rmtree, `print(f"[safe-rmtree] removed: {resolved_path}", file=sys.stderr)`. ASCII-only.
- **Commit:** `feat(safe-rmtree): add _safe_rmtree.py with blacklist + walk-and-strip`

### Card 2: Create `test-safe-rmtree.py`

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-worktree.py`
  - `plugins/mill/unit_tests/run-all.py`
  - `_mill/discussion.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-safe-rmtree.py`
- **Deletes:** none
- **Requirements:**
  - File structure follows `test-worktree.py`'s pattern: module docstring, `from __future__ import annotations`, imports, helper functions, `def main() -> int:` runner with `tempfile.TemporaryDirectory()` blocks and `assert` + `print("PASS: ...")` per scenario. Test discovery via `plugins/mill/unit_tests/run-all.py` requires the `test-` prefix and a non-zero exit on any failure -- mirror `test-worktree.py:31` (`def main() -> int:`) and its `if __name__ == "__main__": sys.exit(main())` at file bottom.
  - `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))` with `HUB = Path(__file__).resolve().parent.parent.parent.parent` (same idiom as `test-worktree.py:10-11`).
  - Import shape: `from _safe_rmtree import safe_rmtree`. Also `import _safe_rmtree` for monkeypatch access in scenarios that need to override `_paths.resolve_container_path` or stub `shutil.rmtree`.
  - Build a fake container layout per scenario via `tempfile.TemporaryDirectory()`:
    ```
    <tmp>/container/wiki/decoy.txt
    <tmp>/container/portals/decoy.txt
    <tmp>/container/wts/container/.keep
    <tmp>/container/wts/<slug>/.keep
    ```
    `container` here is the directory named the same as its parent (matches CLAUDE.md `## Project shape` -- the main repo directory name equals the container name).
  - Scenarios (each its own `with tempfile.TemporaryDirectory() as tmp:` block; each ends with a `print("PASS: <scenario>")` line):
    - `refuses on path == container root`: build the fake layout above, attempt `safe_rmtree(container, allowed_root=container)`, assert `SystemExit` is raised. Monkeypatch `_paths.resolve_container_path` to return `container` so the blacklist resolves predictably.
    - `refuses on path == container/wiki`: same monkeypatch; target `container / "wiki"`, assert `SystemExit`.
    - `refuses on path == container/portals`: same; target `container / "portals"`, assert `SystemExit`.
    - `refuses on path == container/wts/container`: same; target the main-repo worktree path, assert `SystemExit`.
    - `refuses on path ancestor of blacklist`: target `<tmp>` (which contains `container` and therefore the wiki); `allowed_root=<tmp>`; assert `SystemExit`. Verifies the `parents`-ancestor check.
    - `refuses on path outside allowed_root`: `allowed_root=<tmp>/a`, `path=<tmp>/b` (both pre-created); assert `SystemExit` with message containing "path outside allowed_root".
    - `refuses when path is itself a symlink` (POSIX-only, gate on `os.name != "nt"`): create `<tmp>/target/` and `<tmp>/link -> <tmp>/target/` via `os.symlink`; `allowed_root=<tmp>`; assert `SystemExit` with message containing "path is itself a symlink".
    - `refuses when path is itself a junction` (Windows-only, gate on `os.name == "nt"`): create real target via `_junction.create`; `safe_rmtree(junction, allowed_root=junction.parent)`; assert `SystemExit` with message containing "path is itself a junction".
    - `strips junction inside tree before rmtree` (Windows-only): build `<tmp>/scratch/sub/`, `<tmp>/shared_target/data.txt` (with content "DO NOT DELETE"); create junction `<tmp>/scratch/sub/aliased -> <tmp>/shared_target/` via `_junction.create`; `safe_rmtree(<tmp>/scratch, allowed_root=<tmp>/scratch)`; after the call, assert `<tmp>/scratch` is gone AND `<tmp>/shared_target/data.txt` still exists with the same content. This is the regression guard for the wiki-wipe incident.
    - `strips symlink inside tree before rmtree` (POSIX-only): build `<tmp>/scratch/sub/`, `<tmp>/shared_target/data.txt`; `os.symlink(<tmp>/shared_target, <tmp>/scratch/sub/aliased)`; `safe_rmtree(<tmp>/scratch, allowed_root=<tmp>/scratch)`; assert `<tmp>/scratch` is gone AND `<tmp>/shared_target/data.txt` still exists.
    - `strips multiple junctions at different depths` (Windows-only): create three junctions at depth 0, 1, 2 inside scratch; after `safe_rmtree`, assert all three targets are intact.
    - `missing path is no-op`: `safe_rmtree(<tmp>/does-not-exist, allowed_root=<tmp>)`; assert no exception raised; assert returns `None`. Also assert no exception when `ignore_errors=False`.
    - `ignore_errors=True swallows OSError from rmtree`: monkeypatch `_safe_rmtree.shutil.rmtree` to raise `OSError("simulated")`. `safe_rmtree(<tmp>/scratch, allowed_root=<tmp>/scratch, ignore_errors=True)`; assert no exception raised. With `ignore_errors=False` (default), assert `OSError` IS raised.
    - `ignore_errors passes through to shutil.rmtree`: monkeypatch `_safe_rmtree.shutil.rmtree` with a `MagicMock`. Call `safe_rmtree(<tmp>/scratch, allowed_root=<tmp>/scratch, ignore_errors=True)`. Assert the mock was called exactly once with `ignore_errors=True`. Repeat with `ignore_errors=False`; assert mock called with `ignore_errors=False`.
    - `non-container allowed_root does not crash`: `allowed_root = Path(tempfile.mkdtemp())` (outside any millhouse layout). `_paths.resolve_container_path` will raise `SystemExit` from `resolve_main_worktree_root`. Assert `safe_rmtree(allowed_root, allowed_root=allowed_root)` succeeds (the directory gets removed) -- verifies the `except (Exception, SystemExit):` guard works. Clean up the tempdir explicitly afterwards if it still exists.
  - At the end of `main()`, return 0; on any `AssertionError` in a scenario, let it propagate so the subprocess returns non-zero.
  - Module docstring: 4-8 lines describing the unit covered.
  - ASCII-only in `print()` strings.
- **Commit:** `test(safe-rmtree): cover refusal cases + junction/symlink strip + ignore_errors`

## Batch Tests

The batch `verify` runs `test-safe-rmtree.py` directly (fast feedback on the new helper) and then `run-all.py` (full suite, guarding against regressions in other tests). Both must pass before the batch is considered done. `test-safe-rmtree.py` is the only new test; it covers every Decision in the discussion (Refusal blacklist, Reparse-point detection, Path-is-junction handling, Missing-path handling, ignore_errors semantics, Platform behaviour, Container resolution).
