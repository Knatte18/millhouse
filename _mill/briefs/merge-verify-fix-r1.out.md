Verify passes and the fix is committed.

Summary of root cause and fix:

- `plugins/mill/scripts/millpy-review-plan.py` (finalize stage, around line 250) unconditionally reads `review_entry["findings"]` from the dict returned by `_review_plan.finalize()`. That key is a real, always-present part of `_review_plan.finalize()`'s contract (`plugins/mill/scripts/_review_plan.py:647`).
- `plugins/mill/unit_tests/test-review-finalize.py` had three mocked `_review_plan.finalize` return-value dicts (for `test_review_plan_finalize_round_required`, `test_review_plan_finalize_receives_raw_text_byte_identical`, and `test_review_plan_finalize_no_prepare`) that were missing the `"findings"` key — stale relative to the merge that added gap classification. Exercising the real `millpy-review-plan.py` code against these mocks raised `KeyError: 'findings'`, and because `_review_common` is fully mocked in these tests, the `except ReviewError` clause caught a `MagicMock` instead of a real exception class, producing `TypeError: catching classes that do not inherit from BaseException is not allowed` — which is exactly the two verify failures ("review-plan finalize did not succeed via auto-discovery" and "test 3b").
- Fix: added `"findings": []` to the three mocked return-value dicts in `plugins/mill/unit_tests/test-review-finalize.py` so they match the real `_review_plan.finalize()` contract. No production code or test assertions were weakened.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-class-taxonomy.py test-review-common.py test-review-finalize.py` now reports `PASS -- all 3 unit tests`.

{"status":"success","commit_sha":"98c979aeaa418616eb8d9a9fa61dca1caa79268a"}
