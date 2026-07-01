{"status":"success","commit_sha":"38ce7bacdd886e8f170e2e7b455091d2a39631a0","session_id":"213d8d60-7735-4469-8f32-a5f00b6215fa"}

All three cards in batch `parse-batch-refs-leading-token` are implemented, committed, and pushed:

- **Card 4** (`41cdd449`): `plugins/mill/scripts/_review_common.py` — `parse_batch_refs`'s multi-line sub-bullet loop now does `tokens.append(bt[0])` instead of `tokens.extend(bt)`, keeping only the leading backtick-wrapped token per sub-bullet line.
- **Card 5** (`4b88836c`): `plugins/mill/unit_tests/test-review-common.py` — new regression block reproducing the #580 shape, asserting `refs == ["cmd/lyx/main_test.go"]` with phantom tokens dropped. (Also picked up pre-existing ruff-format drift on nearby `Moves:` test literals when the formatter ran.)
- **Card 6** (`38ce7bac`): `plugins/mill/unit_tests/test-plan-validate.py` — new `test_check_reads_not_backtick_path_dirty_multiline_multi_backtick`, registered in the `tests` list, proving Check 6 (`reads-not-backtick-path`) independently flags the same multi-backtick sub-bullet shape at plan-validate time.

Verify command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-plan-validate.py`) passed after each relevant commit and again at the end. Working tree is clean (only the untracked brief file remains, which is expected orchestrator scaffolding outside this batch's scope). Final HEAD: `38ce7bacdd886e8f170e2e7b455091d2a39631a0`.

{"status":"success","commit_sha":"38ce7bacdd886e8f170e2e7b455091d2a39631a0","session_id":"213d8d60-7735-4469-8f32-a5f00b6215fa"}