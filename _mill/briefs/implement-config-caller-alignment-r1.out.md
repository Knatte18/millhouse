4 of 4 cards committed (Cards 7, 8, 9, 10), matching all 4 declared in the batch file. All complete.

{"status":"success","commit_sha":"d439ddea6eeab62143d0a124bd55f9008bdde32a","session_id":"f2f59972-1002-49be-a733-aadcb5e1322a","cards_done":[7,8,9,10]}

Summary — 4 of 4 cards committed for batch `config-caller-alignment`:

- `plugins/mill/scripts/_config.py` — Card 7: gated stub-misuse warning (fires only when `worktree_root != hub_root` AND stub declares `hub_relative_path` AND carries extra keys)
- `plugins/mill/scripts/_review_common.py` — Card 8: opt-in `git_root` keyword param on `load_config`, decoupled from `mill_dir`'s stale-`review:`-key peek use
- `plugins/mill/scripts/millpy-review-plan.py` — Card 9: one call-site now passes `git_root=git_root`
- `plugins/mill/unit_tests/test-config.py` — Card 10: four new tests covering the gated warning (nested-with-mix warns, flat never warns, git-root-override-only never warns) and the opt-in `git_root` parameter (honored when passed, invisible when omitted)

Batch verify (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py`) passes, all 58 tests green. Working tree clean, all commits pushed.

{"status":"success","commit_sha":"d439ddea6eeab62143d0a124bd55f9008bdde32a","session_id":"f2f59972-1002-49be-a733-aadcb5e1322a","cards_done":[7,8,9,10]}
