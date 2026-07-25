All 4 cards committed, matching all 4 `Commit:` messages declared in the batch file. Verify passed (29/29 tests, including the 5 new cases). Working tree is clean.

{"status":"success","commit_sha":"680b4632","session_id":"931801b4-5607-4463-8b6f-83d56d448f64","cards_done":[1,2,3,4]}

Summary: 4 of 4 cards committed this turn.

- `plugins/mill/scripts/_daemon.py` (commit 40d8d591): widened `_handle_connection`'s pre-dispatch try to cover the recv loop + decode + `json.loads` under `(OSError, json.JSONDecodeError, UnicodeDecodeError)`, logging `debug` and returning; dispatch-and-beyond logic unchanged.
- `plugins/mill/scripts/wiki/_client.py` (commit 70e8cbc5): added `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` to both `Popen` calls in `_spawn_server`.
- `plugins/mill/scripts/wiki/_server.py` + `plugins/mill/scripts/_daemon.py` (commit 3aa9733b): renamed `WikiServer`'s `DaemonBase` construction from `"wiki"` to `"wiki-server"` and deleted the dead `logging.basicConfig` fallback in `DaemonBase.run()`.
- `plugins/mill/unit_tests/test-wiki-daemon.py` (commit 680b4632): added 5 new cases (recv-loop benign error, benign-type dispatch error, non-benign dispatch error, logger-consolidation identity/name check, `_spawn_server` stdio redirection on both platform branches). Full suite: 29/29 passing.

Ran `ruff check` ad-hoc (not a configured project dependency) on all touched files; all reported findings are pre-existing issues on lines/patterns outside my edits (e.g. blind `except Exception` matching the file's established test-harness convention) — no new findings introduced by this batch's changes. Pushed `680b4632` to `origin/hanf/mill-background-noise-and-stale-config`.
