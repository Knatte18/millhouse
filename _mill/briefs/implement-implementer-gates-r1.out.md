Both cards are committed (2 of 2) and pushed, and the batch verify command passed (`test-implementer-common.py` and `test-verify-run.py`, rc=0). No tracked files are left dirty.

Card 6 (`feat(verify): run implementer verify gates through _verify_run`):
- `_run_verify_gate` and `_run_verify_gates` now run through `_verify_run.run_verify` and take `timeout_s`, `status_path`, `label` and `runs`.
- A timeout returns a stuck/verify dict with `timed_out: True` and is never retried.
- `_truncate_verify_output` is extracted from `_run_verify_gate`.
- `test-implementer-common.py` installs a default `run_verify` fake in `main()` and fails the run on any unexpected verify command. Existing cases were moved onto local `run_verify` patches with their assertions kept. New cases 6a to 6h cover the timeout, retry and module-wide labels, `runs` collection, the output-path suffix and truncation.

Card 7 (`feat(verify): emit verify_runs and route timeouts in finalize`):
- `verify_timeout_s` and `verify_label` are threaded through `finalize_from_output` and `_forward_output`.
- `_forward_output` now wraps `_forward_output_body` and attaches `verify_runs` to each status envelope. It adds nothing when no verify ran.
- Timed-out gates skip `_reclassify_verify_failure` at all four sites, so they stay stuck/verify.
- A dirty `_mill/status.md` is ignored by `_in_scope_dirty_stuck`, the porcelain checks and `_is_formatter_drift_only`.
- New cases 88a to 88e, 89, 90 and 91 cover these.

Changed files:
- C:\Code\millhouse\wts\verify-runner-instrumentation\plugins\mill\scripts\_implementer_common.py
- C:\Code\millhouse\wts\verify-runner-instrumentation\plugins\mill\unit_tests\test-implementer-common.py

{"status":"success","commit_sha":"52c834bd13a70bc9aef222ff995f944f1630b499","session_id":"38265f2d-e006-438c-be40-c56fe2de5733","cards_done":[6,7]}
