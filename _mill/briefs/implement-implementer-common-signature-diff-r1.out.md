All 7 cards (7-13) declared in this batch are committed: 4 commits cover the 7 cards (c94573bf: cards 7+8+9; aad069f4: card 10; 5e03633c: card 11; 111e6e1b: cards 12+13). Verify command passed (`run-all.py --only test-implementer-common.py`, all cases including new 71a/71b/72a-e green). Working tree is clean.

Summary of files touched:
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_implementer_common.py` — added `_extract_failure_signatures`, `_normalize_failure_signature`, `signatures` field on `_run_verify_gate`'s non-zero-exit stuck dict, subset-diff waiver logic in `_run_verify_gates`, and `batch_verify_baseline` threaded through `finalize_from_output`/`_forward_output` and all four internal `_run_verify_gates` call sites.
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-implementer-common.py` — added cases 71a/71b (extraction/normalization) and 72a-e (subset-diff matrix).

All 7 of 7 cards committed — full completion, not partial.

{"status":"success","commit_sha":"111e6e1b220c678e4fbedd6774741113170e8b02","session_id":"f030abb2-03f8-4dc2-95f3-7209305d8bd5","cards_done":[7,8,9,10,11,12,13]}
