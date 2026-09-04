1 of 1 cards committed — all complete.

Summary: Implemented Card 9 of batch 05-baseline-undercount-corroboration-tests, adding three new unit test cases (72f, 72g, 72h) to `plugins/mill/unit_tests/test-implementer-common.py` covering the `start_sha`-checkout corroboration path in `_run_verify_gates`/`_corroborate_batch_failure`: successful corroboration with self-healing baseline persist, failed corroboration that still blocks, and backward-compatible short-circuit when `start_sha` is omitted. All 1 of 1 declared cards committed. Verify command passed (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py`, exit 0, all cases including the 3 new ones PASS). Working tree clean aside from the pre-existing untracked brief file (out of scope).

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-go-windows-baseline-teardown-and-bg-liveness/plugins/mill/unit_tests/test-implementer-common.py`

{"status":"success","commit_sha":"b56cfd12d0960d5ab26ad0c08b4c8b78fa6dceae","session_id":"2b9a9a68-9a1a-4886-8c35-838311477272","cards_done":[9]}
