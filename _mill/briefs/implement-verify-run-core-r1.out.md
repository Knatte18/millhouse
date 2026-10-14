All 4 of 4 cards are committed, and the batch verify passed (6 test files).

Deviations from the plan:
- In the timeout test I used `timeout_s=3` instead of `timeout_s=1`. The child needs time to start its grandchild and write its pid file, and 1 second was too tight to be reliable.
- In `run_verify`, the START marker and the heartbeat thread begin before `Popen` rather than after. That way a launch failure still leaves a START line before its END line.

Leftover: `test-merge-in-subagent.py` still imports `_implementer_common` at line 18, which nothing else in the file uses now that the `_posix_shell_run_args` cases moved out. I left it, since the line carries a `# noqa`.

{"status":"success","commit_sha":"56c1e5cded5214eb19d06d237e37c640a8456511","session_id":"980f6c84-186d-4626-89bb-1b805ffca1ae","cards_done":[1,2,3,4]}
