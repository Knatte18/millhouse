# Batch: test-migration

```yaml
task: 52 (A) -- Fix unit_tests/run-all destroying wiki during batch verify
batch: test-migration
number: 2
cards: 2
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

This batch migrates the two test files that use `tempfile.TemporaryDirectory` in tests that create real NTFS junctions. Card 3 migrates all 12 `TemporaryDirectory` usages in `test-setup-hub-links.py` — uniform migration is the safe choice because most tests in this file create NTFS junctions via `create_hub_links` and case-by-case analysis is error-prone. Card 4 migrates the 2 junction-creating tests in `test-spawn-core.py`; the other 10 tests in that file do not create junctions and keep `TemporaryDirectory`. Both cards import `safe_temp_dir` from `_test_helpers` (added in batch 1). After this batch, no test that creates NTFS junctions uses `TemporaryDirectory`'s bare-`shutil.rmtree` cleanup.

## Cards

### Card 3: Migrate `test-setup-hub-links.py` to `safe_temp_dir()`

- **Context:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-setup-hub-links.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `from _test_helpers import safe_temp_dir  # noqa: E402` after the existing `from _setup import create_hub_links  # noqa: E402` import line. (Both are after the `sys.path.insert` call and both need `# noqa: E402`.)
  - Replace all 12 occurrences of `with tempfile.TemporaryDirectory() as tmp:` with `with safe_temp_dir() as tmp:`. These appear on lines 97, 149, 207, 270, 330, 381, 429, 491, 524, 586, 669, 707.
  - In each block that previously did `container = Path(tmp) / "container"`, change to `container = tmp / "container"` — `safe_temp_dir()` yields `Path`, so the `Path(tmp)` wrapper is unnecessary. Any other `Path(tmp)` construction in those blocks must also drop the `Path()` wrapper.
  - Verify there are no other uses of `Path(tmp)` in those blocks by checking every block after replacement.
  - Remove `import tempfile` from the stdlib imports block at the top of the file — after the replacements, `tempfile` is no longer referenced in code (only in the module docstring, which is fine).
  - All test logic and assertions remain unchanged. The only changes are the context manager type and the removal of the `Path(tmp)` wrapper.
- **Commit:** `fix(unit-tests): migrate test-setup-hub-links to safe_temp_dir`

### Card 4: Migrate 2 junction tests in `test-spawn-core.py` to `safe_temp_dir()`

- **Context:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `from _test_helpers import safe_temp_dir  # noqa: E402` to `test-spawn-core.py`. The file already has an `import tempfile` and `from pathlib import Path` at the top; add the new import after the `sys.path.insert` call and the existing `# noqa: E402` import block (same placement pattern as Card 3).
  - In `test_recreate_active_junction_creates_link` (starts at line ~492): replace `with tempfile.TemporaryDirectory() as tmp:` with `with safe_temp_dir() as tmp:` and change `container_path = Path(tmp) / "container"` to `container_path = tmp / "container"`.
  - In `test_recreate_active_junction_idempotent` (starts at line ~513): make the same replacement — `with tempfile.TemporaryDirectory() as tmp:` → `with safe_temp_dir() as tmp:` and `container_path = Path(tmp) / "container"` → `container_path = tmp / "container"`.
  - Keep `import tempfile` in the imports — it is still used by the other 10 test functions that remain on `TemporaryDirectory`.
  - No other changes. The 10 other tests that use `TemporaryDirectory` but do not create junctions are left unchanged.
  - All test logic and assertions remain unchanged.
- **Commit:** `fix(unit-tests): migrate recreate_active_junction tests to safe_temp_dir`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` runs the full unit test suite. After this batch, all tests must pass — including both migrated tests in `test-spawn-core.py` and all 12 tests in `test-setup-hub-links.py`. The cleanup path changed but the test logic did not, so the same assertions hold.
