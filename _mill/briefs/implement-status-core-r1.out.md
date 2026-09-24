All 4 of 4 cards are committed. The batch verify command passes (`test-status.py`, `test-parent-branch.py`, `test-cleanup.py`).

Card 3's commit went in with one `test-status.py` assertion failing, because I hardcoded the quoting of `parent_thread: mh:orch`. Card 4's commit fixes it and includes that `test-status.py` change.

{"status":"success","commit_sha":"acd458a1f7d170752acb7df8d2c22f135cda0736","session_id":"707992d5-dc4e-4b1b-a81d-b9a701eaa22d","cards_done":[1,2,3,4]}
