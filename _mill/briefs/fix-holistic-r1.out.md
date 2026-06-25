Applied the single NIT finding from the holistic code review.

Finding Fixed: `_delete_remote_branch` in cleanup checks one error pattern; abandon checks two
- Location: plugins/mill/scripts/millpy-cleanup.py lines 414-423
- Fix: Added `or "unable to delete" in stderr_lower` to the tolerant condition to match millpy-abandon.py and the documented Shared Decision for remote-branch delete tolerance
- Commit: 21883df4

Verification: all four batch verify commands passed.

{"status":"success","commit_sha":"21883df4","session_id":"760f67f2-1e5a-4e3f-836e-b5b0a71b85c7"}
