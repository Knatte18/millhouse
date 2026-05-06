# Review: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8) — 01-implement-cli

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 01-implement-cli
date: 2026-05-05
```

## Findings

### [BLOCKING] git add called without capture_output, text=True, or returncode check
**Step:** Card 3 — Initial dispatch Step 4 and Fix-cycle Step 4 (both paths)
**Issue:** `subprocess.run(["git", "add", "status.md"], cwd=project_root)` has no `capture_output=True`, no `text=True`, and no returncode check. Shared decisions `git-subprocess-style` and `git-error-handling` both require this; a failed `git add` silently proceeds to `git commit`, which then commits nothing and may spuriously succeed.
**Fix:** Apply `capture_output=True, text=True` to the `git add` call and check `result.returncode != 0` → stderr + return 1, same as the commit and push steps.

### [BLOCKING] git commit missing text=True in both paths
**Step:** Card 3 — Initial dispatch Step 4 and Fix-cycle Step 4
**Issue:** `subprocess.run(["git", "commit", ...], cwd=project_root, capture_output=True)` omits `text=True`. Without it `result.stderr` is `bytes`; the error handler `print(result.stderr, file=sys.stderr)` emits `b'...'` noise instead of the actual message, and diverges from the `capture_output=True, text=True` style mandated by shared decision `git-subprocess-style`.
**Fix:** Add `text=True` to both `git commit` calls.

### [NIT] ActiveError from read_slug surfaces as uncaught traceback
**Step:** Card 3 — Common setup Step 4
**Issue:** `slug = _active.read_slug(mill_dir)` raises `ActiveError` on a missing or malformed marker; unlike Step 10 (overview_path missing) and Step 11 (PlanDAGError), no error handling is specified, producing a Python traceback rather than a clean stderr message + exit 1.
**Fix:** Wrap in `try/except _active.ActiveError` (or use `_review_common.find_active_slug`) and return 1 on failure, consistent with the other early-exit steps.

### [NIT] py_compile verify does not check import correctness
**Step:** Batch Tests prose
**Issue:** The prose claims the `py_compile` verify "checks syntax and import correctness"; `py_compile` only validates AST compilation — a missing import (e.g. `import uuid` omitted) passes `py_compile` and only fails at runtime.
**Fix:** Drop "and import correctness" from the prose, or note that import-level failures are caught by batch 02's tests.

## Verdict

REQUEST_CHANGES — two BLOCKINGs on git subprocess style; fix before implementation.