Both cards' Commit: messages appear in the log (card 1: `405a9e4b`, card 2: `4e56e8e5`). The plan-edit commit is a supporting commit for card 2's necessary scope extension, not a separate declared card. 2 of 2 cards committed — all complete.

4e56e8e5f3d09eeedf5ee0f8fa8a989c5ccf7a8b {"status":"success","commit_sha":"4e56e8e5f3d09eeedf5ee0f8fa8a989c5ccf7a8b","session_id":"6a974981-5e80-4f78-9461-935033a7a1e0","cards_done":[1,2]}

Relevant files:
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/scripts/wiki/_client.py` (Card 1 fix)
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/unit_tests/test-wiki-health-check.py` (Card 1 test)
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/scripts/wiki/_sync.py` (Card 2 fix, sub-fix 1)
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/scripts/wiki/_server.py` (Card 2 fix, sub-fix 2)
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/unit_tests/test-wiki-sync.py` (Card 2 test)
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/unit_tests/test-wiki-daemon.py` (Card 2 test)
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/unit_tests/run-all.py` (pre-existing `--only`/SKIP bug fix, required to make the batch's own verify command runnable; scope-extended in the plan file first)
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/_mill/plan/01-wiki-daemon-reliability.md` (Edits list extended for run-all.py)

Both cards committed this turn (2 of 2). Verify command passed (20/20 tests). No uncommitted tracked changes remain.

{"status":"success","commit_sha":"4e56e8e5f3d09eeedf5ee0f8fa8a989c5ccf7a8b","session_id":"6a974981-5e80-4f78-9461-935033a7a1e0","cards_done":[1,2]}
