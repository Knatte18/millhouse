# Batch: gate-and-syntax-fixes

```yaml
task: Green the unit test suite on wiki-v3-adoption so it can merge to main
batch: gate-and-syntax-fixes
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Two independent test-only edits: RC3 (migrate `test-fold.py`'s one `shutil.rmtree` callsite to `_safe_rmtree.safe_rmtree`, which unblocks the `test-no-direct-rmtree.py` gate) and RC4 (replace double-bracket V2 Home.md syntax with single-bracket V3 syntax in `test-spawn-core.py`'s two `test_discover_active_worktrees_*` fixtures). Neither card depends on batch 1 or 2 -- batch 3 is a root batch parallel to batch 1, included here so mill-go can run it concurrently with batch 1 if the scheduler chooses.

Batch-local decision: do NOT add `test-fold.py` to `ALLOWED_FILES` in `test-no-direct-rmtree.py`. The discussion's RC3 decision rejected allowlisting and the operator-confirmed gap fixes (r1, r2) preserved that decision.

## Cards

### Card 17: test-fold.py -- migrate shutil.rmtree to _safe_rmtree.safe_rmtree

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
  - `plugins/mill/unit_tests/test-no-direct-rmtree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-fold.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-fold.py`, replace the single `shutil.rmtree(td.name, ignore_errors=True)` callsite (currently at line 97 inside `safe_cleanup`) with `_safe_rmtree.safe_rmtree(Path(td.name), allowed_root=Path(td.name), ignore_errors=True)`. Line 95 is the explanatory comment "Daemon may still hold file locks on Windows; try shutil.rmtree with ignore_errors" -- leave it in place but update its wording if accurate (replace "shutil.rmtree" with "_safe_rmtree.safe_rmtree" so the comment matches the new call). Add `import _safe_rmtree` near the top of the file alongside the existing `_HERE / _SCRIPTS` sys.path setup (the scripts dir is already on sys.path in this file). Remove the now-unused `import shutil` at line 91 if `shutil` is not referenced elsewhere in the file (grep before removing -- the original wrapper imports `shutil` at function-local scope; the line is `import shutil` on line 91). Do NOT add `test-fold.py` to `ALLOWED_FILES` in `test-no-direct-rmtree.py`. After the change, `test-no-direct-rmtree.py` passes (the gate finds no banned-pattern hits outside the allowlist).
- **Commit:** `test(fold): migrate shutil.rmtree to _safe_rmtree.safe_rmtree`

### Card 18: test-spawn-core.py -- single-bracket Home.md syntax

- **Context:**
  - `plugins/mill/scripts/wiki/_parse.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test_discover_active_worktrees_standard_layout` (currently `test-spawn-core.py:894-912`) and `test_discover_active_worktrees_subfolder_install` (currently `test-spawn-core.py:915-933`), change the inlined `home_md` strings from V2 form `[[my-task]] [active]` (double brackets) to V3 form `[my-task] [active]` (single brackets). Specifically: line 900 currently reads `home_md = "# Home\n\n## My Task\n[[my-task]] [active]\n"` -- change `[[my-task]]` to `[my-task]`. Same change at line 921 (`home_md = "# Home\n\n## My Subfolder Task\n[[my-task]] [active]\n"`). No other change in the file. The V3 `wiki._parse.parse_home_md` accepts single brackets `[slug]` for the active-task form and double brackets `[[slug]]` only for the proposal-link form (`[[slug]](proposal-...)`). After the fix, `parse_home_md` returns one task, `discover_active_worktrees` matches it against the porcelain output, and both tests assert `len(results) == 1` correctly.
- **Commit:** `test(spawn-core): use single-bracket Home.md syntax in discover-active-worktrees tests`

## Batch Tests

Verify `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` runs to completion with 77/77 pass after both this batch and batch 2 land. Individually verifiable subsets: after Card 17, `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-no-direct-rmtree.py` passes and `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fold.py` continues to pass (the migration must not regress test-fold's own assertions); after Card 18, `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-spawn-core.py` shows zero fails in the discover-active-worktrees suite (the rest of the file was already green).
