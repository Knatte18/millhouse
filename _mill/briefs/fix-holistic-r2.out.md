Applied both NIT findings from the APPROVE'd round-2 holistic review:

NIT 1: test-cleanliness.py ROOD-3 — replaced impossible `??` mock with ` D` (deleted-in-index) status code, a genuinely reachable non-modified status. Commit daf94778.
NIT 2: _cleanliness.py revert_out_of_scope_drift — failed `git checkout` reverts now append the porcelain line to remaining_in_scope_lines so the gate still sees the dirty file. Commit 9a99af6b.

Verification: all three batch verify commands pass.

{"status":"success","commit_sha":"9a99af6bd395ed796e56df03a0d2993bf420d7bb","session_id":"17a82f42-eac3-46a0-b57d-f451e4278acc"}
