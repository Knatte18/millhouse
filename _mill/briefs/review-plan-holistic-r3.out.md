I have verified all the plan's claims against source. Here is my review.

MILL_REVIEW_BEGIN
# Review: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate -- holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-28
```

## Findings

### [BLOCKING] Card 4 test accesses `mod._paths` that doesn't exist
**Location:** Batch 1 / Card 4
**Issue:** `millpy-review-discussion.py` imports `_paths`, `_agent_dispatch`, etc. inside `main()` (indented, lines 61-67); they are not module-level. After `spec.loader.exec_module(mod)`, `mod._paths` is undefined, so `unittest.mock.patch.object(mod._paths, ...)` and `mod._paths.resolve_task_path(...)` raise `AttributeError`, failing batch 1 verify.
**Fix:** Patch the source `_paths` module (or `sys.modules['_paths']`) instead of `mod._paths`, and have the card load roots through that module.

### [BLOCKING] Card 4 test is tautological -- does not guard #553
**Location:** Batch 1 / Card 4
**Issue:** The provided code computes `briefs_dir = mod._paths.resolve_task_path(mod._paths.resolve_hub_path(), "_mill/briefs/")` -- always under `hub_dir` by construction. It never invokes the CLI prepare branch (lines 93-114), so reverting Card 3 (CLI line back to `git_root`) does NOT break the assertion. This contradicts the card's own stated key constraint and leaves #553 unguarded.
**Fix:** Drive `mod.main([...])` with `prepare`/`write_brief`/`resolve_hub_path`/`resolve_git_root` patched, capture the emitted `brief_path` from the JSON envelope, and assert it is under `hub_dir`.

### [NIT] Batch 2 scope mis-states which files Card 7 touches
**Location:** Batch 2 / Batch Scope
**Issue:** Prose says "cards 5 and 7 (both `_implementer_common.py`)", but Card 7 edits `test-implementer-common.py` (Edits), not `_implementer_common.py`.
**Fix:** Correct the scope sentence; Card 7's only edited file is the test file.

## Verdict

REQUEST_CHANGES
Card 4's brief-path test is both broken (AttributeError) and tautological; it cannot guard #553.
MILL_REVIEW_END
