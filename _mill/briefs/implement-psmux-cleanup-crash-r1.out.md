All 5 of 5 cards from the batch file are committed, matching their `Commit:` messages exactly, and the batch's verify command passes cleanly.

{"status":"success","commit_sha":"b8c52afb","session_id":"57cf5339-180c-47e4-abfd-c3e7c97cfd68"}

Summary of work (5 of 5 cards committed, verify passing):

- `plugins/mill/scripts/_psmux.py` — `list_sessions()` now catches `FileNotFoundError` and returns `[]`, mirroring the existing "no server running" `PsmuxError` degrade path (commit `2cb38564`).
- `plugins/mill/unit_tests/test-psmux-driver.py` — added coverage for the new `FileNotFoundError` handling (commit `185f7fb1`).
- `plugins/mill/scripts/_llm_claude.py` — `cleanup_session()` gains a dispatch-mode gate that resolves git root/config and no-ops (`return None`) when dispatch mode isn't `"psmux"`; any resolution failure (including `SystemExit` from `_paths.resolve_git_root`) falls through to the existing cleanup logic rather than skipping it (commit `915b56df`).
- `plugins/mill/unit_tests/test-llm-claude.py` — wrapped existing K5(i)-(iv) with the psmux dispatch-mode mock pair, hoisted `import _paths` to module level, and added K5(v)/(vi)/(vii) covering agent/subprocess short-circuit and resolution-failure fallthrough (commit `6d81172d`).
- `plugins/mill/skills/mill-go/SKILL.md` — removed the now-redundant trailing `` || true `` from both the per-batch and holistic `cleanup_session` invocation blocks (commit `b8c52afb`).

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-psmux-driver.py test-llm-claude.py` passes: both test files report `PASS` with all sub-assertions green. `git status --porcelain --untracked-files=no` shows no dirty tracked files; the only untracked item is the brief file itself, which is out of scope.

{"status":"success","commit_sha":"b8c52afb","session_id":"57cf5339-180c-47e4-abfd-c3e7c97cfd68"}
