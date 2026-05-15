# Discussion: 52 (A) — Fix unit_tests/run-all destroying wiki during batch verify

```yaml
task: 52 (A) — Fix unit_tests/run-all destroying wiki during batch verify
slug: run-all-wiki-wipe-fix
status: discussing
parent: main
```

## Problem

During a mill-go batch-verify step, `unit_tests/run-all.py` is invoked from inside a task worktree (e.g. `c:/Code/millhouse/wts/some-slug/`). Task worktrees contain NTFS junction `.wiki` → real wiki clone. On Windows, `shutil.rmtree` follows NTFS junctions because `entry.is_dir()` is `True` and `entry.is_symlink()` is `False` for junctions — it does not stop at the junction boundary. A test's `tempfile.TemporaryDirectory.__exit__` cleanup fired against a temp dir that contained (or was inside) the task worktree, followed the `.wiki` junction, and wiped the entire real wiki (`C:/Code/millhouse/wiki/`), deleting `Home.md`, `config.yaml`, and `.git/`.

Two root causes combine: (1) `run-all.py` does not set `cwd` for subprocess test invocations, so each test process inherits the task worktree's cwd where `.wiki` is present; (2) several test files use `tempfile.TemporaryDirectory` in tests that create real NTFS junctions, relying on the stdlib cleanup which calls bare `shutil.rmtree` — not the junction-aware `safe_rmtree` helper added in commit 27cb7e9.

## Scope

**In:**
- `plugins/mill/unit_tests/run-all.py` — add `cwd=HERE` to subprocess call so test processes start from the `unit_tests/` directory (no `.wiki` junction present there)
- `plugins/mill/unit_tests/_test_helpers.py` — add `safe_temp_dir()` context manager that creates a temp dir via `mkdtemp()` and cleans up via `safe_rmtree(ignore_errors=True)` instead of bare `shutil.rmtree`
- `plugins/mill/unit_tests/test-setup-hub-links.py` — replace all `tempfile.TemporaryDirectory` usages with `safe_temp_dir()` (every test in this file calls `create_hub_links` which unconditionally creates `.wiki` and `.portals` NTFS junctions)
- `plugins/mill/unit_tests/test-spawn-core.py` — replace `TemporaryDirectory` with `safe_temp_dir()` in the 2 tests that create real junctions: `test_recreate_active_junction_creates_link` and `test_recreate_active_junction_idempotent`

**Out:**
- Integration tests (`plugins/mill/integration_tests/`) — they use `.scratch/` for fixtures and do not run from task worktrees; the junction risk does not apply there
- `test-no-direct-rmtree.py` — no new linter rule banning `TemporaryDirectory` globally; `safe_temp_dir()` is the correct fix for specific tests, not a blanket prohibition
- `test-millpy-spawn.py` — already fixed in commit 27cb7e9 (3 tests converted to `safe_rmtree` directly)
- Production scripts — `_safe_rmtree.py` and `_worktree.py` were already fixed in commit 27cb7e9
- Any other test files that use `TemporaryDirectory` without creating junctions — not at risk; no change

## Decisions

### safe-temp-dir-location

- **Decision:** Add `safe_temp_dir()` to `_test_helpers.py` (not a new file).
- **Rationale:** `_test_helpers.py` is already the shared fixture module for all unit tests; it already adds `plugins/mill/scripts` to `sys.path` at import, so `_safe_rmtree` is available without additional path manipulation. Callers already import from `_test_helpers`.
- **Rejected:** New `_test_fixtures.py` file — unnecessary new file; no test currently has a separate fixture file.

### safe-temp-dir-yield-type

- **Decision:** `safe_temp_dir()` yields `Path`, not `str`.
- **Rationale:** All test files use `Path` throughout; `_make_task_worktree` also returns `Path`. Yielding `str` would require every caller to wrap in `Path()`, producing more noise than the current `Path(tmp)` pattern.
- **Rejected:** Yield `str` — callers would still wrap in `Path`, so no net simplification.

### safe-temp-dir-implementation

- **Decision:** Implement `safe_temp_dir()` using `tempfile.mkdtemp()` for creation and `safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)` for cleanup.
- **Rationale:** `TemporaryDirectory.__exit__` calls bare `shutil.rmtree` — the exact dangerous code path this task fixes. Using `mkdtemp()` with explicit cleanup via `safe_rmtree` avoids that path entirely and gives explicit control over deletion order (strip junctions first, then rmtree). `ignore_errors=True` ensures cleanup failures do not mask test results.
- **Rejected:** Wrapping `TemporaryDirectory` and overriding its cleanup — over-engineered; `mkdtemp()` is simpler.

### test-spawn-core-scope

- **Decision:** Replace `TemporaryDirectory` with `safe_temp_dir()` only in the 2 junction-creating tests in `test-spawn-core.py`.
- **Rationale:** Only `test_recreate_active_junction_creates_link` and `test_recreate_active_junction_idempotent` call `recreate_active_junction` which creates a real `.active` NTFS junction inside the temp dir. The other 10 tests in the file do not create junctions; `TemporaryDirectory` is safe for them.
- **Rejected:** Replace all 12 — would change safe tests unnecessarily; principle of minimal change.

### run-all-cwd

- **Decision:** Add `cwd=HERE` to `subprocess.run` in `run-all.py` where `HERE = Path(__file__).resolve().parent` (the `unit_tests/` directory).
- **Rationale:** The `unit_tests/` directory has no NTFS junctions (no `.wiki`, no `.active`). Test files use `HUB = Path(__file__).resolve().parent.parent.parent.parent` to find the repo root — this is `__file__`-relative, not cwd-relative, so changing cwd does not break their path logic. This is the simplest possible fence against test processes inadvertently touching junctions in the parent worktree.
- **Rejected:** Also setting `PYTHONPATH` to `HERE` — unnecessary; `PYTHONPATH` is already propagated via `child_env`; each test file adds its own `sys.path` entries.

### no-direct-rmtree-linter-unchanged

- **Decision:** Do not extend `test-no-direct-rmtree.py` to ban `tempfile.TemporaryDirectory` in junction-creating test files.
- **Rationale:** `TemporaryDirectory` is legitimate in many test contexts (tests that don't create junctions). A blanket ban would be overly restrictive and hard to maintain. The structural fix — `safe_temp_dir()` in the specific tests that need it — is cleaner and more targeted.
- **Rejected:** Linter rule pairing `_junction` import with required `safe_temp_dir` — too fragile; imports and usage are not always co-located.

## Technical context

### Key files

- `plugins/mill/unit_tests/run-all.py:33` — `subprocess.run` call missing `cwd=HERE`; add it
- `plugins/mill/unit_tests/_test_helpers.py` — add `safe_temp_dir()` after existing helpers; needs `import contextlib, tempfile` added to imports
- `plugins/mill/unit_tests/test-setup-hub-links.py` — 12 `TemporaryDirectory` usages (all tests); callers do `with tempfile.TemporaryDirectory() as tmp:` then `container = Path(tmp) / "container"` — becomes `with safe_temp_dir() as tmp:` then `container = tmp / "container"` (since `safe_temp_dir` yields `Path`)
- `plugins/mill/unit_tests/test-spawn-core.py:495` — `test_recreate_active_junction_creates_link`; `test_recreate_active_junction_idempotent` at line 515; both use `with tempfile.TemporaryDirectory() as tmp:` followed by `container_path = Path(tmp) / "container"` — becomes `with safe_temp_dir() as tmp:` + `container_path = tmp / "container"`

### How `create_hub_links` creates junctions

`create_hub_links` in `test-setup-hub-links.py` creates `.wiki` and `.portals` NTFS junctions inside the test's temp dir container via `_junction.create`. These junctions point to sibling directories inside the same temp tree (not outside it). However, `TemporaryDirectory.__exit__` calls `shutil.rmtree` which on Windows follows junctions as directories — even intra-temp junctions can cause recursive re-entry into already-partially-deleted trees, and if the test cwd is a task worktree (due to run-all.py's missing `cwd=`), the junction target could resolve to the real wiki.

### Why `_blacklist_for` does not protect task worktrees

`_safe_rmtree._blacklist_for(allowed_root)` protects: container root, `container/wiki`, `container/portals`, `container/wts/<main-repo-name>`. Task worktrees (e.g. `container/wts/some-task/`) are NOT on the blacklist by design — they are legitimately deleted during cleanup. The protection here comes from `allowed_root` containment: if the temp dir is within `unit_tests/` (no junctions), `safe_rmtree` won't follow anything outside.

### Junction-safe `safe_rmtree` internals

`safe_rmtree` in `_safe_rmtree.py` calls `_walk_strip_reparse_points(path)` before `shutil.rmtree`. This walks the directory tree and calls `_junction.remove_junction(entry)` (Windows `os.rmdir` on the junction entry) for any entry where `os.lstat` reveals `IO_REPARSE_TAG_MOUNT_POINT`. This removes the junction inode without touching the target, then `shutil.rmtree` proceeds on the pruned tree.

### Commit 27cb7e9 context

That commit added `_safe_rmtree.py` + `test-no-direct-rmtree.py` and fixed 3 tests in `test-millpy-spawn.py`. The remaining unsafe `TemporaryDirectory` usages in `test-setup-hub-links.py` and `test-spawn-core.py` were not addressed in that commit (the `test-no-direct-rmtree.py` linter does not flag `TemporaryDirectory`). This task finishes what commit 27cb7e9 started.

## Constraints

- **No new production code changes.** `_safe_rmtree.py`, `_junction.py`, `_worktree.py`, and all production scripts are already correct. This task touches only test infrastructure.
- **`safe_temp_dir()` must import `_safe_rmtree` lazily or after `sys.path` is set.** `_test_helpers.py` sets `sys.path` at module load (line 17-18); `_safe_rmtree` imports can be top-level in the file after that block.
- **Windows-only junctions.** `_junction.create` is a no-op on POSIX; `safe_temp_dir()` is safe on both platforms since `safe_rmtree` checks for reparse points only on Windows.
- **`allowed_root` for `safe_temp_dir()` must equal the temp dir root itself.** This allows `safe_rmtree` to delete the entire temp dir while its containment check passes.

## Testing

`safe_temp_dir()` is thin composition of `mkdtemp()` + `safe_rmtree` — both already tested. No new test file is needed.

The existing `test-no-direct-rmtree.py` will continue to pass because `safe_temp_dir()` calls `safe_rmtree`, not `shutil.rmtree` directly.

After the changes, running `python plugins/mill/unit_tests/run-all.py` from a task worktree must not delete any files outside `unit_tests/`. Manual verification: run from `c:/Code/millhouse/wts/run-all-wiki-wipe-fix/` and confirm `c:/Code/millhouse/wiki/` is untouched.

The 2 modified tests in `test-spawn-core.py` and all modified tests in `test-setup-hub-links.py` must still pass — the only change is the cleanup path, not the test logic.

## Q&A log

- **Q:** Where should `safe_temp_dir()` live? **A:** [auto-pick] `_test_helpers.py`. **Why:** already the shared fixture module; scripts path already set up; no new file needed.
- **Q:** Should `safe_temp_dir()` yield `Path` or `str`? **A:** [auto-pick] `Path`. **Why:** all test files use `Path` throughout; consistent with `_make_task_worktree` return type.
- **Q:** In `test-spawn-core.py`, replace `TemporaryDirectory` in only the 2 junction-creating tests or all 12? **A:** [auto-pick] Only the 2. **Why:** targeted fix; other 10 tests don't create junctions.
- **Q:** Extend `test-no-direct-rmtree.py` to ban `TemporaryDirectory` in junction-creating files? **A:** [auto-pick] No. **Why:** blanket ban is too blunt; `safe_temp_dir()` is the correct structural fix.
- **Q:** Should `run-all.py`'s `cwd=HERE` also force `PYTHONPATH`? **A:** [auto-pick] No. **Why:** `PYTHONPATH` already propagated via `child_env`; each test file sets `sys.path` via `__file__`-relative logic.
- **Q:** What if cleanup inside `safe_temp_dir()` raises? **A:** [auto-pick] `ignore_errors=True`. **Why:** test cleanup failures must not mask test results.
- **Q:** Use `mkdtemp()` or wrap `TemporaryDirectory` in `safe_temp_dir()`? **A:** [auto-pick] `mkdtemp()`. **Why:** entire point is to avoid `TemporaryDirectory.__exit__`'s bare `shutil.rmtree`.
- **Q:** Migrate all tests in `test-setup-hub-links.py` or only known-failing ones? **A:** [auto-pick] Migrate all. **Why:** `create_hub_links` unconditionally creates NTFS junctions; every test is at risk.
