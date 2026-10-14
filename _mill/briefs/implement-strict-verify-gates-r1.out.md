Batch strict-verify-gates: 2 of 2 cards committed and pushed. The verify command passes (test-implementer-common.py, test-done-gate.py, test-millpy-implement.py, test-fix-finalize.py).

Card 12 (`plugins/mill/scripts/_implementer_common.py`):
- `_run_verify_gates` is now strict: it runs the batch gate, then the module-wide gate with the `[module-wide verify] ` reason prefix. There is no waiver and no skip.
- Removed `module_verify_baseline` and `batch_verify_baseline` from `_run_verify_gates`, `finalize_from_output`, `_fixer_logic_ancestor_override` and `_forward_output`, along with every kwarg passed to them.
- Removed `_normalize_failure_signature`, the stuck dict's `signatures` field, and the `effective_returncode` assignments.
- `_extract_failure_signatures` no longer takes `returncode` and no longer synthesizes `NONZERO_EXIT`.
- The post-edit grep for the removed names has zero hits. `uvx ruff check --select F401,F841,F811` on the file passes.

Card 13 (`plugins/mill/unit_tests/test-implementer-common.py`):
- Deleted Cases 59, 61, 62, 71b, 71c and 72, and removed the `_normalize_failure_signature` import. Case 60 is kept with its baseline argument dropped.
- Cases 78-80 have the `batch_verify_baseline` argument removed and their comments reworded; their strict-block assertions are unchanged.
- Added strict-semantics Cases 72a-72e: batch failure skips the module-wide gate, module-wide failure gets the prefix, no module-wide command returns None, the stuck dict has exactly `status`, `stuck_type` and `reason`, and the two removed kwargs raise `TypeError`.
- The only remaining hits for the removed names are the two `TypeError` checks.

Before editing I confirmed that no other script or skill passes the removed kwargs or reads `signatures`.

{"status":"success","commit_sha":"bd606c17fc10a94f0f798aef33dceb1f09fd0a46","session_id":"d3a3c3ed-e894-436a-9308-72d95b562869","cards_done":[12,13]}
