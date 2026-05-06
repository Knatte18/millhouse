# Batch: python-backend

```yaml
task: "8 (A) — Disable per-batch reviews (config-driven)"
batch: python-backend
cards: 2
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

This batch adds the null-batch guard to `_review_plan.run()` so that `review.plan.batch: null` in config triggers holistic-only review instead of crashing. It also adds two unit tests covering the new code path. No CLI or integration-test changes — the guard is entirely in the backend `run()` function.

## Cards

### Card 1: null-batch guard in _review_plan.run()

- **Reads:**
  - `plugins/mill/scripts/_review_plan.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  In `_review_plan.run()`, within the "# 3. Load reviewers" block (currently at line 313), replace the existing two lines:

  ```python
  batch_reviewer_name = cfg["review"]["plan"]["batch"]
  batch_reviewer = load_reviewer(batch_reviewer_name)
  ```

  with:

  ```python
  batch_reviewer_name = cfg["review"]["plan"]["batch"]
  if batch_reviewer_name is None:
      if cfg["review"]["plan"].get("holistic") is None:
          raise ReviewError(
              "review.plan.batch is null and review.plan.holistic is also null"
              " — at least one must be set"
          )
      holistic_only = True

  if not holistic_only:
      batch_reviewer = load_reviewer(batch_reviewer_name)
  else:
      batch_reviewer = None
  ```

  The docstring's step summary at line 276 must also be updated from:
  `4. Parallel per-batch reviews (skipped if batch_files is empty or holistic_only).`
  to:
  `4. Parallel per-batch reviews (skipped if batch_files is empty, holistic_only, or batch reviewer is null).`

  Back-compat requirement: existing code that passes a non-null `batch_reviewer_name` must be unaffected — the new branches only activate when `batch_reviewer_name is None`.

- **Commit:** `fix(_review_plan): treat null review.plan.batch as holistic_only`

### Card 2: unit tests for null-batch

- **Reads:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Append two new tests at the end of `main()` in `test-review-plan-flow.py`, following the existing pattern (each wrapped in `with tempfile.TemporaryDirectory() as tmpdir:`).

  **Test 6a — batch=null, holistic fires only:**
  - Build fixture using `_make_plan_fixture` with one batch spec: `[("core", "01-core.md", ["src/a.py"], [])]`.
  - Override `cfg["review"]["plan"]["batch"] = None` (keep `"holistic": "test_stub"`).
  - Seed 1 APPROVE response with `stub.seed([(APPROVE_TEXT, "sid-null-1")])`.
  - Call `plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)`.
  - Assert: `r.verdict == "APPROVE"`.
  - Assert: `len(r.reviews) == 1`.
  - Assert: `r.reviews[0]["scope"] == "holistic"` (no per-batch entry).
  - Assert: `"plan-review-r1"` is in the review filename (holistic pattern, no batch stem).
  - Print `"PASS test6a: batch=null — holistic fires, per-batch skipped"`.

  **Test 6b — batch=null, holistic=null raises ReviewError:**
  - Build fixture using `_make_plan_fixture` with one batch spec same as above.
  - Override both: `cfg["review"]["plan"]["batch"] = None` and `cfg["review"]["plan"]["holistic"] = None`.
  - Call `plan_run(...)` inside a `try` block expecting `ReviewError`.
  - Assert the exception message contains `"at least one must be set"`.
  - Print `"PASS test6b: batch=null + holistic=null raises ReviewError"`.
  - If no exception: `errors += 1; print("FAIL test6b: expected ReviewError")`.

  Maintain the existing error-counting pattern (`errors += 1` in `except AssertionError` and `except Exception` blocks).

- **Commit:** `test(_review_plan): null-batch guard — holistic-only and ReviewError cases`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` runs the full unit test suite. Both new test cases (test6a, test6b) print `PASS` on success. Any assertion failure increments `errors` and prints `FAIL`, causing `run-all.py` to exit non-zero.
