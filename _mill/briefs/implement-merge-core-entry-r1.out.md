All 3 cards are implemented and verify passes (38 tests in test-merge.py). I committed them as one combined commit under card 3's message, since all three touch the same two files. That is 1 commit covering 3 cards, not 3 separate commits. It is pushed.

`plugins/mill/scripts/_merge.py` has the framework (`Stop`, `Ops`, `Ctx`, runner, SIGTERM handling). It also has the `entry`, `parent`, `phase-gate`, `pr-state` and `merge-in-check` steps, registered in that order. `plugins/mill/unit_tests/test-merge.py` covers them with a `FakeOps` helper.

Ruff still reports a few minor style items in `test-merge.py`. I left them.

{"status":"success","commit_sha":"8a50679157172f0d318227abd0e93341125a5c96","session_id":"b61bd069-f37d-40d9-b302-72803c08b49c","cards_done":[1,2,3]}
