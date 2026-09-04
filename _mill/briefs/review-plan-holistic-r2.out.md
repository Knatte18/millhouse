MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] New tests never registered in test-plan-validate.py's `main()` list
**Location:** batch `symbol-reference-check`, cards 2 and 3.
**Issue:** `test-plan-validate.py`'s `main()` (line 6982) drives execution from a hard-coded `tests = [...]` list, not reflection/discovery — verified every one of the ~26 existing `context-completeness` tests is individually listed there. Cards 2 and 3 add ~15 new `test_check_context_completeness_symbol_*` functions but neither card's Requirements mentions appending them to that list, nor does the overview's "new tests follow the file's existing end-to-end convention" Shared Decision (which only covers the test-body pattern).
**Effect:** unregistered `def test_...` functions are silently never invoked by `python .../test-plan-validate.py` — the batch's own `verify:` — so the batch could report green while the new symbol-branch behavior has zero actual regression coverage. This also falsifies the batch's own "Batch Tests" claim that this one file's suite "exercises" cards 1–3's work.
**Fix:** add an explicit Requirements step to cards 2 and 3 instructing the implementer to append each new test function to `main()`'s `tests` list (with placement/comment matching the file's existing per-check grouping convention, e.g. lines 7041–7069).

### [NIT:consistency] Test file's top-of-file "Check coverage" docstring not updated
**Location:** batch `symbol-reference-check`, card 2 (or 3).
**Issue:** `test-plan-validate.py`'s module docstring (lines 9–29) summarizes `context-completeness` as "references a resolvable file-path-shaped token" — card 1 updates the equivalent summary in `_plan_validate.py`'s own module docstring (line 47) to mention symbol-shaped tokens, but no card updates this test file's parallel summary line.
**Fix:** add a one-line Requirements note to extend the test file's "Check coverage" docstring entry alongside the new tests.

## Verdict

REQUEST_CHANGES
New symbol-branch tests are never wired into the test runner's hard-coded dispatch list.
MILL_REVIEW_END
