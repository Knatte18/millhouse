Clean. Both cards committed and pushed, verify passes.

{"status":"success","commit_sha":"57361832","session_id":"7c4d8b57-512d-4fee-94e5-ebbb341241b3"}

Summary of work done:

- `plugins/mill/scripts/wiki/_client.py` — Card 1: split `_dispatch()`'s retry-loop exception handling so `ConnectionRefusedError` (when `attempt < 3`) re-invokes `_ensure_daemon(wiki_path)` and updates `req[FIELD_TOKEN]` before the backoff sleep, so a mid-session daemon death is respawned instead of retried against the dead socket. `WikiStartupError` from a failed respawn propagates uncaught. `TimeoutError`/`ConnectionResetError` handling is unchanged (separate `except` clause, same sleep-and-retry, no respawn). Commit `7322cd0b`.
- `plugins/mill/unit_tests/test-wiki-client-retry.py` — Card 2: added `WikiStartupError` to the `wiki` import, and three new cases covering (a) respawn-then-succeed via `_ensure_daemon` side_effect list, (b) no extra `_ensure_daemon` call for `TimeoutError`, (c) `WikiStartupError` from a failed respawn propagating immediately with zero sleep calls. Commit `57361832`.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-client-retry.py` passes all 11 tests (8 pre-existing + 3 new). Ruff lint clean on both changed files. Working tree is clean; both commits pushed to `hanf/mill-infra-and-tooling-fixes`.

{"status":"success","commit_sha":"57361832","session_id":"7c4d8b57-512d-4fee-94e5-ebbb341241b3"}