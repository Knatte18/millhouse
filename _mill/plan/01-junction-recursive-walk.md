# Batch: junction-recursive-walk

```yaml
task: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading
batch: junction-recursive-walk
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-junction.py
depends-on: []
```

## Batch Scope

Fixes `_junction.strip_all_in_worktree` to walk the worktree tree recursively instead of scanning only the root level (one level). In repos where `hub_relative_path` is a subdir (e.g. `src/csharp/NORCE.Models`), mill-spawn creates junctions under that subdir; the root scan returns `[]`, remove_safe fails with WorktreeLockedError, and the live `.wiki` junction survives teardown. The fix replaces the single `os.scandir` with a recursive walk that descends into real directories and stops at junctions/symlinks — stripping every junction found regardless of depth. A regression test case is added to `test-junction.py` to catch future regressions.

## Cards

### Card 1: recursive walk in strip_all_in_worktree

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/scripts/_junction.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Replace the body of `strip_all_in_worktree` (currently at line ~307-317) with a recursive walk. Keep the function signature `(worktree_path: Path, junctions_cfg: dict[str, str]) -> list[Path]` unchanged — `junctions_cfg` is retained unused to avoid touching `_worktree.remove_safe`'s call site this round.

  New implementation logic:
  1. If `worktree_path` does not exist (`not worktree_path.exists()`), return `[]`.
  2. Define an inner helper `_walk(dir_path: Path) -> None` (closure over `removed: list[Path]`):
     - `try: entries = list(os.scandir(str(dir_path)))` / `except PermissionError: print(f"[junction] WARNING: permission denied scanning {dir_path}; junctions inside may survive", file=sys.stderr); return`.
     - For each entry: compute `ep = Path(entry.path)`. If `entry.is_symlink() or _is_junction_or_symlink(ep)`: call `remove(ep)`, append `ep` to `removed`, and do NOT descend. Elif `entry.is_dir()`: call `_walk(ep)` recursively. (Files are skipped.)
  3. Call `_walk(worktree_path)` and return `removed`.

  Update the docstring: remove the stale references to `.millhouse/wiki`, `.others`, `.active` at the root; replace with "Walks the worktree tree recursively, stopping at any junction or symlink (never descending into one). Catches junctions at any depth, including those placed under a hub-relative subdir." Keep the note that `junctions_cfg` is retained for caller compatibility but is no longer read.

  `sys` is already imported in `_junction.py`; `os` is already imported. No new imports needed.
- **Commit:** `fix(_junction): recursive walk in strip_all_in_worktree to find nested junctions (#510)`

### Card 2: nested-junction regression test

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-junction.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add test case `(e) nested-junction case` immediately after the existing `(d) missing-worktree case` (before the `print("", ...)` summary line). Use the same `try/finally` pattern with `_safe_rmtree.safe_rmtree` as cases (a)–(d).

  Setup:
  - Create `tmp_path / "wt"` and `tmp_path / "wt" / "src" / "hub"` (two levels of real subdirs inside the worktree root).
  - Create `tmp_path / "wiki_target"` and `tmp_path / "portals_target"` as target directories.
  - Create junctions `wt/src/hub/.wiki → wiki_target` and `wt/src/hub/.portals → portals_target` using `_junction.create(...)`.

  Call:
  - `stripped = _junction.strip_all_in_worktree(wt, junctions_cfg={})`

  Assertions:
  - Both junction paths are in `stripped`.
  - Neither `wt / "src" / "hub" / ".wiki"` nor `wt / "src" / "hub" / ".portals"` exists after stripping.
  - `wt / "src" / "hub"` (the real parent directory) still exists.
  - `tmp_path / "wiki_target"` and `tmp_path / "portals_target"` still exist (junctions were stripped, targets untouched).
- **Commit:** `test(_junction): nested-junction regression test (#510)`

## Batch Tests

`verify:` runs `test-junction.py` directly. The five test cases in that file (a–e after this batch) exercise: undeclared junction stripping, multiple junctions at root, non-junction directories untouched, missing worktree, and the new nested-junction case. Scoped to `_junction.py` only.
