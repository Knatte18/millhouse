Both cards (Card 12 and Card 13) committed — 2 of 2 cards complete. Both `Commit:` messages from the batch file match the log exactly.

{"status":"success","commit_sha":"f3f22f32191fa440d6437c77299e4440d027d37f","session_id":"eeec3588-0eb8-4c12-9f3a-06ddba77207c","cards_done":[12,13]}

Summary: 2 of 2 cards committed for batch `bg-heartbeat-diagnosability`.

- `plugins/mill/scripts/millpy-bg.py` — Card 12: added a heartbeat thread inside `_worker_main`'s worker fast-path (`_HEARTBEAT_INTERVAL_S = 30`), writing `[mill-bg] HEARTBEAT <ts>` lines through the already-open log handle every 30s while the inner subprocess runs; stopped/joined immediately after `subprocess.run()` returns, still inside the `with` block. Commit `6d3ee1cb`.
- `plugins/mill/unit_tests/test-millpy-bg.py` — Card 13: added tests (q) heartbeat presence before EXIT sentinel, (r) exactly two opens of `log_path` (proving the heartbeat never opens a second handle), (s) no exception escapes the heartbeat thread via a `threading.excepthook` guard. Commit `f3f22f32`.

`verify:` (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-bg.py`) passes all 19 test cases including the three new ones. Working tree is clean.

Note: `uvx ruff check` on both edited files reports pre-existing `BLE001`/`I001`/`PLW1510`/`SIM117` findings that are already present on `main` (confirmed via `git show main:plugins/mill/scripts/millpy-bg.py | ruff check -`) and reflect this file's established best-effort-diagnostic exception-catching style, which the plan's Requirements explicitly specify verbatim for the new heartbeat code. These are out of this batch's scope and were left unchanged rather than diverging from the approved plan text.

{"status":"success","commit_sha":"f3f22f32191fa440d6437c77299e4440d027d37f","session_id":"eeec3588-0eb8-4c12-9f3a-06ddba77207c","cards_done":[12,13]}
