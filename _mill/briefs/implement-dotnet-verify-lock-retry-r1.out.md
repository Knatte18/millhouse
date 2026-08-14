Verify passes, working tree clean, both card commits present matching the two `Commit:` messages in the batch file (2 of 2 cards committed). Card-count self-check confirms: 2 of 2 cards committed, matching the batch's declared card count.

{"status":"success","commit_sha":"f12599738e1bf3856a2be9264e30cb7cabdd177a","session_id":"4e041b01-ad5c-4a7d-9353-d5c99d731921","cards_done":[1,2]}

Summary: Both cards in batch `01-dotnet-verify-lock-retry` are complete (2 of 2 cards committed).

- `plugins/mill/scripts/_implementer_common.py` — added `_has_dotnet_lock_race_signature`, updated `_run_verify_gate`'s docstring, and added the retry-once-after-shutdown logic in the failure branch. Commit `bc48e39b`.
- `plugins/mill/unit_tests/test-implementer-common.py` — added Test I1–I4 covering retry-succeeds, retry-still-fails, no-lock-signature (no retry), and non-dotnet command (no retry/shutdown). Commit `f1259973`.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py` passes in full (all tests green, including the new Test I1–I4). Working tree is clean (`git status --porcelain --untracked-files=no` empty). `commit_sha` is the full SHA from `git rev-parse HEAD`.

{"status":"success","commit_sha":"f12599738e1bf3856a2be9264e30cb7cabdd177a","session_id":"4e041b01-ad5c-4a7d-9353-d5c99d731921","cards_done":[1,2]}