All 3 commits match all 3 cards (4, 5, 6) declared in the batch. 3 of 3 cards committed — all complete.

{"status":"success","commit_sha":"b916282149707e5116944899355220ca8d3e20b9","session_id":"a9bbcdbe-3bf5-4955-b9f8-abc5086903e1","cards_done":[4,5,6]}

Summary: 3 of 3 cards committed for batch `status-batch-baseline-field`.

- `plugins/mill/scripts/_status.py`: added `verify_baseline_failures` to `_BATCH_ALLOWED_KEYS` and the serializer's `order` list; widened `set_batch_field`/`set_batch_fields` type hints to include `list[str]`; added a leading `isinstance(value, list)` branch in `_serialise_batches` that writes list values via `yaml.safe_dump(..., default_flow_style=True)` instead of falling through to the raw-`str()` branch.
- `plugins/mill/unit_tests/test-status.py`: added round-trip assertions for `verify_baseline_failures` (non-empty list, sibling-field non-corruption, and empty-list round-trips as `[]` rather than being dropped).

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py` passes (all assertions green). Working tree is clean with no uncommitted tracked changes.

Commits (in order): `4b0b4464`, `a7f0a904`, `b9162821` (HEAD, full SHA `b916282149707e5116944899355220ca8d3e20b9`).

{"status":"success","commit_sha":"b916282149707e5116944899355220ca8d3e20b9","session_id":"a9bbcdbe-3bf5-4955-b9f8-abc5086903e1","cards_done":[4,5,6]}
