# Batch: toctou-guard-hardening

```yaml
task: "millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows"
batch: "toctou-guard-hardening"
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-safe-rmtree.py test-junction.py
depends-on: []
```

## Batch Scope

This batch is the whole task: it hardens the two shared recursive `os.scandir`
walks that feed `_worktree.remove_safe` — `_safe_rmtree._walk_strip_reparse_points`
and `_junction.strip_all_in_worktree`'s inner `_walk` — against a
`FileNotFoundError` raised when a file or directory vanishes between being
listed by a parent `os.scandir()` call and being processed (the TOCTOU race
behind GitHub issue #738's `[WinError 3]` failure during
`_verify_baseline.compute_baseline`'s teardown). It is one batch because the
two source-file edits are small, mechanically identical in shape, and the two
test files that cover them import directly from those two modules — splitting
across batches would force an artificial dependency edge for no isolation
benefit. There are no batch-local decisions beyond `## Shared Decisions` in
the overview; the guard-catch-class and logging-format decisions there are
authoritative for both edited files in this batch.

## Cards

### Card 1: Guard `_safe_rmtree._walk_strip_reparse_points` against vanished entries

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_walk_strip_reparse_points` (currently lines 61-69),
  wrap the existing `with os.scandir(str(root)) as it: for entry in it: ...`
  body in an outer `try/except FileNotFoundError:` around the whole
  `with os.scandir(str(root)) as it:` block. On catch, print
  `f"[safe-rmtree] skip vanished entry: {root}"` to `sys.stderr` (module
  already imports `sys`) and return — this is the guard that protects
  `safe_rmtree`'s own direct, unwrapped call `_walk_strip_reparse_points(original)`
  (line 151), which has no enclosing `try/except` anywhere else in the call
  chain. Separately, inside the `for entry in it:` loop, wrap each entry's
  full per-iteration body — the `entry.is_symlink()` check, the
  `_is_reparse_point(ep)` check, the `_junction.remove(ep)` call, the
  `entry.is_dir(follow_symlinks=False)` check, and the recursive
  `_walk_strip_reparse_points(ep)` call — in its own `try/except
  FileNotFoundError: continue`. On catch inside this inner per-entry guard,
  print `f"[safe-rmtree] skip vanished entry: {ep}"` to `sys.stderr` before
  continuing. Do not change `_onexc_chmod_retry`, `_is_reparse_point`,
  `_blacklist_for`, or `safe_rmtree`'s own body — only
  `_walk_strip_reparse_points`'s internals change. Do not catch any
  exception class other than `FileNotFoundError`, and do not add a
  `sys.platform` check — the guard applies unconditionally on both
  Windows and POSIX per the overview's Shared Decisions.
- **Commit:** `fix(safe-rmtree): skip vanished entries in _walk_strip_reparse_points instead of raising`

### Card 2: Guard `_junction.strip_all_in_worktree`'s `_walk` against vanished entries

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_junction.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `strip_all_in_worktree`'s inner `_walk` closure
  (currently lines 314-336), add a **separate** `except FileNotFoundError:`
  clause alongside (not merged into) the existing
  `except PermissionError:` around `entries = list(os.scandir(str(dir_path)))`
  (line 317-318). The existing `PermissionError` branch's message and
  return-early behaviour are unchanged. The new `FileNotFoundError` branch
  prints `f"[junction] WARNING: vanished entry scanning {dir_path}; skipping"`
  to `sys.stderr` (module already imports `sys`) and returns early — its
  wording must be distinct from the `PermissionError` branch's "permission
  denied" text, since reusing that text would misreport a vanished-path race
  as a permission failure. Separately, wrap the `for entry in entries:` loop
  body — the `entry.is_symlink()` check, the `_is_junction_or_symlink(ep)`
  check, the `remove(ep)` call, and the `entry.is_dir()` check plus the
  recursive `_walk(ep)` call it guards — in a `try/except
  FileNotFoundError: continue` per entry. On catch inside this inner
  per-entry guard, print `f"[junction] WARNING: vanished entry scanning
  {ep}; skipping"` to `sys.stderr` before continuing. `removed.append(ep)`
  must stay inside the per-entry try (an entry whose `remove(ep)` call
  raises `FileNotFoundError` must not be appended to `removed`, since it was
  never actually removed by this call — it was already gone). Do not change
  `create`, `remove`, `points_to`, or `_is_junction_or_symlink` — only
  `strip_all_in_worktree`'s inner `_walk` changes. Do not catch any
  exception class other than `FileNotFoundError` in the new clauses, and do
  not add a `sys.platform` check.
- **Commit:** `fix(junction): skip vanished entries in strip_all_in_worktree's walk instead of raising`

### Card 3: Add vanished-entry regression coverage to `test-safe-rmtree.py`

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-safe-rmtree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add three new cases to `main()` in
  `test-safe-rmtree.py`, following the file's existing pattern (a
  `tempfile.TemporaryDirectory()` fixture block per case, `assert` calls,
  and a `print("PASS: ...")` on success) and its existing
  `unittest.mock.patch` convention (already imported at the top of the
  file via `from unittest.mock import MagicMock, patch`):
  1. **Vanished file entry mid-walk:** build a small fixture tree with at
     least two sibling files, patch `_safe_rmtree.os.scandir` (or mock a
     `DirEntry`-shaped stand-in returned from it) so that one entry's
     `is_symlink()` call raises `FileNotFoundError`, call `safe_rmtree` on
     the tree's parent directory, and assert it completes without raising
     and the surviving sibling is still processed.
  2. **Vanished subdirectory entry mid-walk:** build a fixture tree with a
     nested subdirectory, mock the recursive `os.scandir` call for that
     subdirectory to raise `FileNotFoundError`, call `safe_rmtree`, and
     assert it completes without raising and sibling entries of the
     vanished subdirectory are still processed.
  3. **Top-level `safe_rmtree` entry-point window:** mock `os.scandir` to
     raise `FileNotFoundError` on the very first (outermost) call made by
     `_walk_strip_reparse_points` — i.e. the call `safe_rmtree` itself
     makes directly at its step 7 (`_walk_strip_reparse_points(original)`).
     Call `safe_rmtree` (not `_walk_strip_reparse_points` directly) so the
     assertion exercises the window between `safe_rmtree`'s step-6
     `exists()` check and the walk's own `os.scandir` open. Assert
     `safe_rmtree` completes without raising.
  `_safe_rmtree._walk_strip_reparse_points` calls `os.scandir` via the
  context-manager protocol (`with os.scandir(str(root)) as it:`) — any mock
  standing in for it needs `__enter__`/`__exit__` (or use
  `unittest.mock.MagicMock` configured as a context manager, or patch at a
  level that doesn't require reimplementing the protocol, e.g. patching the
  `DirEntry`-shaped objects' methods rather than `os.scandir` itself where
  that is simpler). Do not modify or remove any existing case in this file
  — the existing 11 cases (blacklist/containment refusals, junction/symlink
  strip-before-rmtree, missing-path no-op, `ignore_errors` semantics,
  non-container `allowed_root` handling) must still pass unchanged.
- **Commit:** `test(safe-rmtree): cover vanished-entry TOCTOU race in _walk_strip_reparse_points`

### Card 4: Add vanished-entry regression coverage to `test-junction.py`

- **Context:**
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-junction.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add three new cases to `main()` in `test-junction.py`,
  following the file's existing `try/except Exception` + `ok()`/`fail()`
  helper pattern (each case wrapped in its own `try/finally` with
  `_safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path,
  ignore_errors=True)` teardown, matching cases (a)-(e)). This file
  currently does no mocking (`import unittest.mock` is not present) — add
  `from unittest.mock import patch` for these new cases; that is a
  deliberate, discussed departure from the file's prior real-filesystem-only
  convention, needed because the vanished-entry race cannot be reproduced
  with real filesystem timing.
  1. **Vanished file entry mid-walk:** build a fixture worktree with at
     least two sibling entries under it, patch `_junction.os.scandir` (which
     `strip_all_in_worktree`'s `_walk` calls as a plain iterable —
     `list(os.scandir(str(dir_path)))`, not the context-manager form used in
     `_safe_rmtree.py`) so one entry's `is_symlink()` call raises
     `FileNotFoundError`, call `strip_all_in_worktree(wt, junctions_cfg={})`,
     and assert it returns without raising and the surviving sibling entry
     is still processed.
  2. **Vanished subdirectory entry mid-walk:** build a fixture tree with a
     nested subdirectory, mock the recursive `os.scandir` call for that
     subdirectory to raise `FileNotFoundError`, call
     `strip_all_in_worktree`, and assert it completes without raising and
     sibling entries of the vanished subdirectory are still processed.
  3. **`strip_all_in_worktree` entry-point window:** since `_walk` is a
     closure only reachable through the public `strip_all_in_worktree`
     entry point (unlike `_safe_rmtree._walk_strip_reparse_points`, which
     is directly callable), mock `os.scandir` to raise `FileNotFoundError`
     on the very first top-level call `_walk` makes (i.e. `dir_path ==
     worktree_path`) and call `strip_all_in_worktree` itself (not a
     directly-invoked inner closure, since none is exposed) — assert it
     completes without raising and returns a list (rather than
     propagating the exception).
  Do not modify or remove any of the file's existing 5 cases
  (`strips-undeclared-junction`, `multiple-junctions`,
  `non-junction-untouched`, `missing-worktree`, `nested-junction`) — they
  must still pass unchanged. This file has no
  `PermissionError`/junction-create-remove-`points_to` case of its own
  today and adding one is out of scope for this task.
- **Commit:** `test(junction): cover vanished-entry TOCTOU race in strip_all_in_worktree`

## Batch Tests

`verify:` runs `run-all.py --only test-safe-rmtree.py test-junction.py` —
exactly the two files this batch edits (Cards 3 and 4) and the two files
whose behaviour those tests exercise (Cards 1 and 2). No other test file
imports `_walk_strip_reparse_points` or `strip_all_in_worktree`'s vanished-
entry behaviour directly, so this scope is sufficient; `test-worktree.py`
and other `remove_safe`/`safe_rmtree` callers listed in
`_mill/discussion.md`'s Technical Context are beneficiaries of this fix but
require no changes and are not exercised by new assertions, so they are
left out of the `--only` list per the default per-batch scoping rule.
