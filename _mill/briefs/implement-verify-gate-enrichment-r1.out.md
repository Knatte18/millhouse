All work is complete for this batch. Both cards (11 and 12) are committed, pushed, and verify passes.

Summary: 2 of 2 cards committed successfully.

- Card 11: `plugins/mill/scripts/_implementer_common.py` — enriched `_run_verify_gate`'s truncated `reason` with an omitted-content marker plus up to 20 extracted failure-summary lines (Go subtest/package, pytest, run-all.py per-test/summary) recovered from the omitted portion, updated docstring. Commit `82bf80c1`.
- Card 12: `plugins/mill/unit_tests/test-implementer-common.py` — added 5 new scenario blocks (Test D-H) covering the short-output regression guard, earlier-FAIL-line recovery with tail, no-match byte-count-only marker, 20-line cap enforcement, and run-all.py-specific line recovery. Commit `3f1a9524`.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py` passes (all tests green, including the 5 new Test D-H scenarios). Working tree is clean of tracked in-scope changes.

3f1a952437eba05727daa5ae821df2552de70f0c
{"status":"success","commit_sha":"3f1a952437eba05727daa5ae821df2552de70f0c","session_id":"74a83c48-081c-45b9-baa9-f0f0067ee123","cards_done":[11,12]}
