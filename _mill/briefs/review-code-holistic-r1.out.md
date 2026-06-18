MILL_REVIEW_BEGIN
# Review: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-18
```

## Findings

### [BLOCKING] Drift-guard regex matches nothing — test always passes vacuously

**Location:** `plugins/mill/unit_tests/test-skill-helper-drift.py:100`
**Issue:** The pattern `r"_([a-zA-Z_][a-zA-Z0-9_]*)\\.([a-zA-Z_][a-zA-Z0-9_]*)\("` uses `\\.` in a raw string, which the `re` engine sees as the two-character sequence `\` + any-char — it does not match a literal dot. SKILL.md files contain `_paths.resolve_hub_path(` with a real dot, so `re.findall` returns zero matches for every file, `_run_drift_guard` always returns an empty failure list, and the test prints PASS while detecting nothing. Card 1's entire purpose is defeated.
**Fix:** Change to `r"_([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\("` (single `\.`).

### [NIT] Dead `functions` set computed but never used in `_collect_shipped_helpers`

**Location:** `plugins/mill/unit_tests/test-skill-helper-drift.py:73-79`
**Issue:** Lines 73-79 build a `functions` set via `ast.walk` (which includes nested functions), but this set is immediately discarded — `top_level_functions` (lines 82-88) is what gets stored. The double-scan wastes CPU and leaves misleading dead code.
**Fix:** Remove the `functions` set and the `ast.walk` loop entirely; keep only the `top_level_functions` loop over `tree.body`.

### [NIT] `_run_regression_locks` silently escalates on `FileNotFoundError`

**Location:** `plugins/mill/unit_tests/test-skill-helper-drift.py:167-171`
**Issue:** The try/except around `review_plan_path.read_text()` catches only `UnicodeDecodeError`; a missing file raises `FileNotFoundError`, which propagates to `main()`'s bare `except Exception` block and prints a raw traceback instead of a structured FAIL message.
**Fix:** Broaden the except clause to `(UnicodeDecodeError, OSError)` and append a structured failure message; mirror the same fix for the mill-go SKILL path read at line 188.

## Verdict

REQUEST_CHANGES
The drift-guard regex is broken and the test passes vacuously, defeating Card 1's regression coverage entirely.
MILL_REVIEW_END
