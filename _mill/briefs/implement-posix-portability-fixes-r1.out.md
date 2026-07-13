All 5 cards match the batch file's 5 `## Cards` entries: fix(mill-go), test(guards), chore(config), docs(vscode), docs(wiki-push). All 5 of 5 cards committed, verify passes, tree is clean.

{"status":"success","commit_sha":"2c4e3407","session_id":"d8b17f51-36f2-4f04-b927-39b2b999fb09"}

Summary: All 5 of 5 cards in batch `01-posix-portability-fixes` were committed successfully, and the batch `verify:` command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py`) passes with all five checks (including the new Card-2 guard) reporting PASS. Working tree is clean.

Files touched (all absolute paths under `/home/knatte/Code/millhouse/wts/posix-cross-platform-port`):
- `plugins/mill/skills/mill-go/SKILL.md` — Card 1: made all four venv-existence checks POSIX-aware (`.venv/bin/python` OR `.venv/Scripts/python.exe`)
- `plugins/mill/unit_tests/test-guards.py` — Card 2: added `_check_no_windows_only_venv_check()`, wired into `main()`, updated docstring (Four->Five checks)
- `.claude/settings.json` — Card 3: removed dead `MILL_TEST_PYTHON` key, reduced to `{}`
- `plugins/mill/scripts/_vscode.py` — Card 4: reworded stale "pwsh" comments to be OS-neutral
- `plugins/mill/skills/mill-wiki-push/SKILL.md` — Card 5: fixed stale `.ps1` wrapper reference to `.cmd`, documented POSIX direct-invocation

Commits (in order): f89f88f3, 524df1c4, 7b75cb4c, e3167dd5, 2c4e3407 — all pushed to `hanf/posix-cross-platform-port`.

{"status":"success","commit_sha":"2c4e3407","session_id":"d8b17f51-36f2-4f04-b927-39b2b999fb09"}
