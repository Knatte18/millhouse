MILL_REVIEW_BEGIN
# Review: Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-23
```

## Findings

### [BLOCKING] Completeness gate crashes existing success tests on int parse
**Location:** Batch 2, Card 6 (`_batch_completeness_stuck`)
**Issue:** `test-millpy-implement.py` (in BOTH batch-1 and batch-2 `verify:`) mocks `_subprocess_util.run` to return `stdout="abc1234\n"` for every git call; `test_1`/`test_2` reach `_forward_output`'s self-reported-success branch with `card_count` threaded by Card 8, so the new gate runs `git rev-list --count` and `int("abc1234")` raises `ValueError` — the call is placed outside any try/except (step 3), crashing finalize.
**Fix:** In `_batch_completeness_stuck`, return `None` when the rev-list returncode is non-zero OR the count is non-numeric (guard the `int()` parse), and treat `card_count <= 0` as a no-op; alternatively Card 10/8 must update the mock to return a numeric stdout for `rev-list --count`.

### [BLOCKING] card_count=0 from heading-less batch files mis-feeds the gate
**Location:** Batch 2, Card 8 (`card_count` resolution) + Card 6
**Issue:** Card 8 computes `card_count` by counting `### Card N:` headings; a batch file with zero such headings (e.g. the test fixture `01-test-batch.md`, or a future docs-only batch) yields `card_count=0`, which Card 6 still treats as a live integer and runs the rev-list parse against — compounding the crash above and giving a meaningless `0 < 0` comparison.
**Fix:** Card 6's helper must early-return `None` when `card_count` is falsy/`<= 0`; state this explicitly in the Requirements.

### [NIT] Card 4 rationale misstates `_review_code` failure mode
**Location:** Batch 1, Card 4
**Issue:** The card claims it prevents "a raw `ValueError` surfacing from `_review_code` internals," but `_review_code.run` reads `status_path` only for per-batch scope and already wraps it in `try/except Exception` (lines 233-248); holistic reviews never read status.md, so the new unconditional `require_status_path` guard adds a NEW hard-fail (exit 1) for holistic reviews when status.md is absent, and is exercised by no test in either batch's `verify:`.
**Fix:** Either gate the guard on `args.batch is not None`, or correct the rationale and accept the stricter contract deliberately; note that no batch `verify:` covers `millpy-review-code.py`.

### [NIT] Test cards under-specify run-all discovery for main()-style file
**Location:** Batch 2, Card 10 (and Cards 5, 12)
**Issue:** `test-implementer-common.py` has no per-test functions — it runs inline cases inside `main()`; "follow the file's run-all.py discovery convention" is ambiguous since discovery is file-level, and a new test function not wired into `main()` would silently never run.
**Fix:** Card 10 should say "add new cases inside the existing `main()` body and increment the case numbering"; Cards 5/12 should say "append the new function to the file's `tests = [...]` runner list."

## Verdict

REQUEST_CHANGES
Completeness gate crashes existing success tests; guard the count parse and zero card_count.
MILL_REVIEW_END
