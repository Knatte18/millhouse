All 4 of 4 cards are committed (8, 9, 10, 11). The verify command passed: all 4 unit test files green (test-status.py, test-millpy-implement.py, test-millpy-merge-in-subagent.py, test-millpy-fix.py). The tracked working tree is clean.

- Card 8: removed the module-baseline API and the `verify_baseline_failures` batch key from `_status.py`. The scoped ruff check was clean.
- Card 9: updated `test-status.py` per the brief. It now asserts `set_batch_field` and `set_batch_fields` reject `verify_baseline_failures`, and that a legacy key on disk is read back and dropped on the next batch write. The module-baseline tests and the baseline-row-anchoring block are deleted.
- Card 10: deleted `_verify_baseline.py` and its unit test and the two integration tests (`test-verify-baseline.py`, `test-baseline-waiver.py`) with `git rm`. Only those four files imported the module. No runner listed the test filenames explicitly.
- Card 11: removed `baseline_verify_timeout_minutes` from `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml`. A grep finds no remaining hits.

Mentions of the deleted names remain outside this batch's scope:
- `_implementer_common.py` still has the `module_verify_baseline` kwarg (batch 5 removes it).
- `skills/mill-go-base/SKILL.md` still mentions it (batch 6, docs).
- Comments in `test-cleanup.py`, `test-worktree.py` and `test-done-gate.py` still name the deleted module or its tests.
- `unit_tests/BENCHMARK.md` still lists `test-verify-baseline.py`.

{"status":"success","commit_sha":"089a654f57dc0a3792caddff90569f7685372ef4","session_id":"e4577e31-3687-4140-8727-17131b6baf45","cards_done":[8,9,10,11]}
