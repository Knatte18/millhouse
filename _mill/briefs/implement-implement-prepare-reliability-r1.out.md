All 3 of 3 cards committed (Card 1 as its own commit `4afb4f55`; Cards 2 and 3 combined into `22be968d` since they touch the same file, per the brief's combined-commit allowance, named using Card 3's commit message). Batch verify (`test-agent-dispatch.py`, `test-millpy-implement.py`) passes with 59 tests OK. No uncommitted tracked changes remain.

{"status":"success","commit_sha":"22be968d","session_id":"b551b4e6-fdb1-43c3-8fcc-d770f42faa89"}

Summary of work:
- `plugins/mill/scripts/_agent_dispatch.py` — Card 1: `resolve_dispatch_mode`'s fallback default changed from `"subprocess"` to `"agent"` (matches shipped `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml`), docstring updated.
- `plugins/mill/unit_tests/test-agent-dispatch.py` — Card 1: renamed/updated the test that pinned the old wrong default.
- `plugins/mill/scripts/millpy-implement.py` — Card 2: added a three-way branch (resume-after-incomplete / prepare-reuse / fresh-mint) in `main()`'s prepare-and-full block so a re-dispatched `--stage prepare` against an already-`running` batch reuses `session_id`/`start_sha` instead of re-minting state; `emit_prepare(...)` call now passes `start_sha=start_sha`. Card 3: a failed `git push` in the fresh-mint branch is now non-fatal (stderr warning, falls through to envelope emission); the `git commit` step above it is unchanged and still fatal.
- `plugins/mill/unit_tests/test-millpy-implement.py` — Card 3: added `test_prepare_stage_envelope_includes_start_sha_matching_head`, `test_prepare_stage_reuses_session_on_rerun_of_running_batch`, `test_prepare_stage_push_failure_nonfatal_but_commit_failure_still_fatal`.

{"status":"success","commit_sha":"22be968d","session_id":"b551b4e6-fdb1-43c3-8fcc-d770f42faa89"}