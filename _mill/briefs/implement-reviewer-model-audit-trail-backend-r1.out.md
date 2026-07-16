All 4 of 4 cards in the batch's `## Cards` are committed, matching their `Commit:` messages exactly:

- Card 12 → `feeab63e` `feat(review-common): add reviewer_model override helper to finalize_scope (#644)`
- Card 13 → `5ffeefc8` `feat(review-code): thread actual_model override into finalize (#644)`
- Card 14 → `d4db7253` `feat(review-plan): thread actual_model override into finalize (#644)`
- Card 15 → `a80876b5` `feat(review-discussion): thread actual_model override into finalize (#644)`

Verify (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py`) passes. Working tree is clean (no uncommitted tracked changes) and everything is pushed to `origin/hanf/mill-go-agent-dispatch-reliability-gaps`.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps/plugins/mill/scripts/_review_common.py` — added `apply_actual_model_override()` and threaded `actual_model` through `finalize_scope()`. Note: I deviated slightly from the literal `\s*` in the brief's regex text and used `[ \t]*` instead, because `\s` also matches `\n` and caused the injection/rewrite logic to bleed across a line boundary when a `reviewer_model:` line was malformed (empty value) — it would swallow the following line (e.g. a closing yaml fence) into the replacement. Verified with manual repro before and after the fix.
- `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps/plugins/mill/unit_tests/test-review-common.py` — added test cases for rewrite, inject-after-fence, malformed-line-not-consumed, identity-when-None, and `finalize_scope(..., actual_model=...)` end-to-end.
- `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps/plugins/mill/scripts/_review_code.py`, `_review_plan.py`, `_review_discussion.py` — added `actual_model: str | None = None` to each `finalize()` and threaded it into the success-path `finalize_scope(...)` call only, per spec.

Pre-existing (not introduced by me, confirmed present on `hanf/linux-port-more`) ruff findings in `_review_plan.py` (f-string without placeholder) and `_review_discussion.py`/`_review_code.py` (unused `parse_blocking_count`/`parse_verdict` imports) were left untouched since they're outside this batch's declared scope.

{"status":"success","commit_sha":"a80876b5","session_id":"5f0bc455-d56b-4950-a607-5f0c3205d5ba"}