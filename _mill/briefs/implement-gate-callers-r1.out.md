Batch gate-callers is complete: 2 of 2 cards committed. The batch `verify:` command passed (72 tests in test-done-gate, 48 across the other three files).

- Card 8 (committed): `millpy-implement.py` and `millpy-fix.py` resolve the verify timeout once after the second config reload and pass `verify_timeout_s` and `verify_label` to `finalize_from_output` and `_forward_output`.
  - An invalid `pipeline.verify_timeout_minutes` prints the message to stderr and returns 1.
  - The fixer scales the budget by `max(1, len(batch_verifies))` at both sites and labels the run `fix:<scope>`.
  - Tests cover the kwargs, the scaled timeout, and the invalid-config case in both CLI test files.
- Card 9 (committed): `_done_gate.run_preflight` and `run_gate` take an optional `hub_root` and run the gate through `_verify_run.run_verify` with `shell_mode="native"`.
  - A shared private helper, `_run_gate_command`, does the config load and result mapping.
  - Ok and blocked results carry `verify_runs`. Timeouts, launch failures, non-zero exits and invalid timeout config all return `blocked`.
  - The dotnet shutdown call is unchanged.
  - `test-done-gate.py` was rewritten to patch `_verify_run.run_verify` and `_config.load_config`. All 11 original cases are kept, adapted to the new seam, and 6 cases were added.

`uvx ruff check` reports many findings on the touched files. I did not fix them.

Files changed:
- C:\Code\millhouse\wts\verify-runner-instrumentation\plugins\mill\scripts\millpy-implement.py
- C:\Code\millhouse\wts\verify-runner-instrumentation\plugins\mill\scripts\millpy-fix.py
- C:\Code\millhouse\wts\verify-runner-instrumentation\plugins\mill\scripts\_done_gate.py
- C:\Code\millhouse\wts\verify-runner-instrumentation\plugins\mill\unit_tests\test-millpy-implement.py
- C:\Code\millhouse\wts\verify-runner-instrumentation\plugins\mill\unit_tests\test-millpy-fix.py
- C:\Code\millhouse\wts\verify-runner-instrumentation\plugins\mill\unit_tests\test-done-gate.py

{"status":"success","commit_sha":"14f3b4dc50d497c2d0288881cc11fd5229c82231","session_id":"986608fd-c44f-4d9b-b9ce-047967db8b3f","cards_done":[8,9]}
