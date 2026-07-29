All 3 cards in batch `unit-tests-plan` are committed and verified.

**Summary of work:**
- Card 16 (`_review_plan.py::prepare()` holistic `reviewer_override` unit tests) — 5 new checks added to `plugins/mill/unit_tests/test-review-plan-flow.py` (tests 31a–31e): override resolves over config, unknown name raises `ReviewError`, cluster override raises `ReviewError`, override skips the large-prompt auto-switch, and override is a no-op outside holistic scope.
- Card 17 (`_review_plan.py::run()` holistic `reviewer_override` unit tests) — 4 new checks added to the same file (tests 32a–32d): `holistic_only=True` dispatches the named override (test_stub and Gemini providers), unknown name raises `ReviewError`, and `effort` is forwarded to the test_stub provider branch when the large-prompt auto-switch is skipped.
- Card 18 (`reviewer_self_id` round-trip tests) — 2 new checks added to `plugins/mill/unit_tests/test-review-common.py`: `apply_actual_model_override` leaves `reviewer_self_id:` untouched when rewriting `reviewer_model:`, and `write_review_file` preserves a `reviewer_self_id:` line verbatim on disk.

**Notable implementation decision:** the brief's literal instruction to seed the registry via `_test_registry.write_to(wiki_root, ...)` for Cards 16/17 does not actually make a named `reviewer_override` resolvable in this repo, because `_reviewers.load()` only falls back to the legacy wiki `agents.yaml` when both the plugin template and `.millhouse/agents.local.yaml` are empty — and the real plugin template (`plugins/mill/templates/mill-agents.yaml`) is non-empty in this source tree. This exact gap is already documented and solved by the already-committed sibling batch (`unit-tests-discussion`) via a `_write_local_overlay(mill_dir, **entries)` helper writing to `.millhouse/agents.local.yaml`. I added the same helper to `test-review-plan-flow.py` and used it for all registry entries that the new `reviewer_override` tests need to actually resolve, so the new assertions exercise real behavior rather than a fixture that would leave the override name unresolvable.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-review-dispatch-attribution-gaps/plugins/mill/unit_tests/test-review-plan-flow.py`
- `/home/knatte/Code/millhouse/wts/mill-review-dispatch-attribution-gaps/plugins/mill/unit_tests/test-review-common.py`

Card-count self-check: range start `8f1dcf0998646fc084001e4ffb5a29c3f281d99b` (batch-start commit). `git log 8f1dcf09..HEAD --oneline` shows 2 commits (`31acc277` covering Cards 16+17 combined, `81ad1bc8` covering Card 18) against 3 declared cards — matches expectation since Cards 16/17 touch the same file and were combined per the allowed convention. All 3 cards (16, 17, 18) are genuinely complete; this is an honest "3 of 3 cards done."

Verify command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-common.py`) passes.

{"status":"success","commit_sha":"81ad1bc8","session_id":"b76365fc-b64b-4296-a8c3-f64420d2b89c","cards_done":[16,17,18]}
