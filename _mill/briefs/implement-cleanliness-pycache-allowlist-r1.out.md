Both cards (10 and 11) have matching commits - 2 of 2 cards committed, all complete.

{"status":"success","commit_sha":"3e3bbb270ea4cd5783c44c97e22e656c7ba8c9d0","session_id":"2b274987-f125-4fda-921e-6a9de05cb778","cards_done":[10,11]}

Summary: 2 of 2 cards committed (all complete). Card 10 extended `_cleanliness.py`'s `clean_ephemeral_scope_violations` allowlist for `.pyc` files and `__pycache__` path components (commit `1ba2dad0`), and Card 11 added CESV-11/12/13 regression tests plus a batch-test run confirming all 49 cases pass (commit `3e3bbb27`).

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-go-done-gate-halt-and-cleanliness-recovery/plugins/mill/scripts/_cleanliness.py`
- `/home/knatte/Code/millhouse/wts/mill-go-done-gate-halt-and-cleanliness-recovery/plugins/mill/unit_tests/test-cleanliness.py`

Note: `uvx ruff check` flagged pre-existing lint debt (PIE810 tuple-endswith merge suggestion, import-sort, BLE001 blind-except, SIM117 nested-with) in both files, all present before my edits (confirmed via `git show HEAD~1:...` and `git show HEAD~2:...` comparisons) and consistent with the overview's Shared Decision that `pipeline.done_gate` stays `null` due to 1942 pre-existing repo-wide findings - left untouched, out of scope for this batch.

{"status":"success","commit_sha":"3e3bbb270ea4cd5783c44c97e22e656c7ba8c9d0","session_id":"2b274987-f125-4fda-921e-6a9de05cb778","cards_done":[10,11]}
