Both cards (5 and 6) are committed, matching the batch's 2 declared cards — 2 of 2 cards committed, all complete. Verify passed. Tree is clean.

Summary of changes:
- `plugins/mill/scripts/_parent_branch.py` — `check_liveness` now falls back to `git rev-parse --verify --quiet refs/heads/<branch>` when the origin `ls-remote` check fails, fixing #879 (live local-only parent branches no longer misclassified as dead).
- `plugins/mill/unit_tests/test-parent-branch.py` — added `check_liveness` coverage for remote-alive, local-only-alive, and both-dead cases, mocking `_subprocess_util.run` per the `test-pr-state.py` pattern.

{"status":"success","commit_sha":"d67cc1f4277a7acc3d08b4da393b426c60af4178","session_id":"dff120c8-cf0a-4bfe-b3a8-8d293c38cec5","cards_done":[5,6]}
