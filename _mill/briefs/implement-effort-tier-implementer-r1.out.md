3 of 3 cards committed, matching the batch file's `## Cards` `Commit:` messages exactly (Card 4, Card 5, Card 6). Verify command passed. No uncommitted tracked changes remain.

{"status":"success","commit_sha":"8e6aff8e","session_id":"feee4e28-d9f7-4485-9af7-c157739fbabd"}

## Summary

All 3 of 3 cards in batch `02-effort-tier-implementer` were committed and pushed:

- **Card 4** (`91653389`): `plugins/mill/scripts/_implementer_common.py` — `emit_prepare` gained an `effort: str | None = None` kwarg, added to the envelope as `"effort"` when not None, mirroring `start_sha`'s handling. Added Case 65 to `plugins/mill/unit_tests/test-implementer-common.py`.
- **Card 5** (`eb480ed0`): `plugins/mill/scripts/millpy-implement.py` — threaded the existing `impl_effort` variable into the `--stage prepare` branch's `emit_prepare(...)` call. Added `test_prepare_stage_envelope_includes_effort_from_implementer_spec` to `plugins/mill/unit_tests/test-millpy-implement.py`.
- **Card 6** (`8e6aff8e`): `plugins/mill/scripts/millpy-fix.py` — threaded the existing `fixer_effort` variable into the `--stage prepare` branch's `emit_prepare(...)` call. Added `test_stage_prepare_batch_scope_includes_effort_from_fixer_spec` to `plugins/mill/unit_tests/test-millpy-fix.py`.

Batch verify command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py test-millpy-fix.py`) passed on all three test files. `git status --porcelain --untracked-files=no` is clean (the only untracked file is the brief itself, excluded by `--untracked-files=no`).

Note: `ruff format` on the whole file caused a large unrelated reformatting diff (this repo appears to have pre-existing formatter drift from an older ruff config). I reverted that whole-file reformat and applied only the scoped edits for each card, keeping diffs minimal and on-topic; `ruff check` (lint, no reformat) passed clean on all touched files.

{"status":"success","commit_sha":"8e6aff8e","session_id":"feee4e28-d9f7-4485-9af7-c157739fbabd"}