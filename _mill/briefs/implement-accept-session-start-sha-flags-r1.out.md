Excellent! All cards in the batch have been implemented successfully:

1. **Card 1** (test): Added `test_15_stage_finalize_accepts_session_and_start_sha_flags` to verify that:
   - The implement CLI parses `--stage finalize` with `--session-id` and `--start-sha` without argparse exiting
   - The finalize branch passes `status.md` values to `finalize_from_output`, not the CLI args

2. **Card 2** (fix): Added `--start-sha` and `--session-id` arguments to argparse in `millpy-implement.py`, following the pattern in `millpy-fix.py`, with clear comments explaining they are accepted for CLI-shape parity but ignored (status.md is the authoritative source)

The verify command passed all 36 tests successfully. The changes are minimal and focused, addressing exactly the issue: `millpy-implement.py` now accepts the `--session-id` and `--start-sha` flags that mill-go's agent-mode dispatch threads into the finalize call, preventing the `error: unrecognized arguments` exit code.

{"status":"success","commit_sha":"9e34689d6c2d7f9e4e0cc0ab6f924fca3af4a84d","session_id":"cc802323-bcf3-4516-92d7-c3553a3650b5"}
