MILL_REVIEW_BEGIN
# Review: mill-go-base/mill-merge: documented step behavior diverges from underlying script capability — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-08-21
```

## Findings

### [BLOCKING:design] `test-preflight.py` has no test-invocation entrypoint at all
**Location:** batch 2, cards 6-7. **Issue:** `plugins/mill/unit_tests/test-preflight.py` defines six `test_*` functions but has no `main()`, no `run_all()`, no `if __name__ == "__main__"` block, and no pytest usage — confirmed by reading the full 157-line file. `run-all.py` invokes each `test-*.py` as `python <file>.py` in a subprocess; for this file that subprocess defines functions and exits 0 without ever calling one. **Fix:** card 6 or 7 must add a dispatcher (mirroring `test-marker.py`'s `main()`/`test-pygit2-util.py`'s `run_all()` pattern) that calls every `test_*` function and `sys.exit`s non-zero on failure — otherwise batch 2's `verify:` is a no-op for both the pre-existing tests and card 7's new ones.

### [BLOCKING:design] `importlib.import_module` won't find modules in an arbitrary `scripts_dir`
**Location:** batch 2, cards 6-7. **Issue:** Card 6's `missing_helpers` change calls `importlib.import_module(module_name)`, justified by "`scripts_dir` already being on `sys.path`" — true only for the real `CLAUDE_PLUGIN_ROOT/scripts` path. But `missing_helpers(required, scripts_dir)` takes `scripts_dir` as a plain argument, and card 7's own instructed fixture pattern (mirroring `test_missing_helpers_all_present`) passes a fresh `tempfile.TemporaryDirectory()` that is never added to `sys.path` — see `test-preflight.py` lines 26-66, only the module-level `SCRIPTS_DIR` (line 21) is on `sys.path`. **Fix:** card 6's positive "attr present" test case would raise `ModuleNotFoundError` and get reported as missing, contradicting the expected empty-list assertion; the implementation needs `importlib.util.spec_from_file_location(module_name, scripts_dir / f"{module_name}.py")` (or a temporary `sys.path` insertion) instead of a bare `import_module`.

### [BLOCKING:scope] New tests in batch 1 are written but never invoked
**Location:** batch 1, cards 2 and 5. **Issue:** `test-pygit2-util.py`'s `run_all()` and `test-marker.py`'s `main()` each hard-code an explicit `tests = [...]` list of function objects (no auto-discovery) — see lines 351-370 and 304-324 respectively. Cards 2 and 5 instruct adding new `test_local_branches_at_sha_*` / `test_slug_from_branch_detached_head_no_matching_branch` functions but neither card mentions appending them to that list. **Fix:** add an explicit sub-bullet to cards 2 and 5 requiring the new function names be appended to the respective `tests`/`main()` list, or the new coverage silently never runs even though `verify:` reports success.

### [NIT:consistency] New helper omitted from `_pygit2_util.py`'s `__all__`
**Location:** batch 1, card 1. **Issue:** Every existing public function in `_pygit2_util.py` is listed in the file's explicit `__all__` (lines 333-344); card 1's `local_branches_at_sha` requirement never mentions adding it there, breaking the file's self-declared public-API-export convention (no functional impact since callers use attribute access, not `import *`). **Fix:** add "append `local_branches_at_sha` to `__all__`, alphabetically" to card 1's Requirements.

## Verdict

REQUEST_CHANGES
Batch 2's verify is a no-op (no test entrypoint) and its import approach breaks its own prescribed test fixture; batch 1's new tests are never wired into their file's manual dispatch list.
MILL_REVIEW_END
