# Review: 8 (A) — Disable per-batch reviews (config-driven) — 01-python-backend

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-python-backend
date: 2026-05-06
```

## Findings

### [NIT] Test numbering creates reader confusion
**Step:** Card 2 — unit tests
**Issue:** New tests are named "test6a"/"test6b" but appended after test 19. The existing "Test 6" is the NEED_CONTEXT per-batch test; 6a/6b at the end of `main()` breaks sequential readability with no comment explaining the naming.
**Fix:** Number them 20 and 21, or add an inline comment explaining why they're grouped as 6a/6b (e.g. "logically extends the holistic-only family").

### [NIT] Docstring skip condition is redundant
**Step:** Card 1 — docstring update
**Issue:** The updated step 4 text says "holistic_only, or batch reviewer is null" — but "batch reviewer is null" is always mediated by setting `holistic_only = True` in the guard; it is never an independent skip path.
**Fix:** "`(skipped if batch_files is empty or holistic_only — including when batch is null)`" more accurately describes the single code path.

## Verdict

APPROVE — logic is correct, back-compat holds, test coverage is complete.