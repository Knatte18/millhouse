All 3 of 3 cards committed and matched to the batch's declared `Commit:` messages. All cards complete: 3 of 3 cards committed.

{"status":"success","commit_sha":"9a64082567949c1bf75218f7b6ba63d986d34651","session_id":"429c8e3f-a4b1-4447-9a91-07211eb8a58d","cards_done":[1,2,3]}

Summary of work done:
- `/home/knatte/Code/millhouse/wts/claude-plugin-root-env-setup/plugins/mill/scripts/_config.py` — added `resolve_plugin_root_from_syspath(sys_path)` helper that scans `sys.path` for the PYTHONPATH-inserted `scripts` entry and returns its parent, plus added it to `__all__`.
- `/home/knatte/Code/millhouse/wts/claude-plugin-root-env-setup/plugins/mill/unit_tests/test-config.py` — added five unit tests covering basic scan, no-match `SystemExit`, non-index-1 entry, trailing-slash normalization, and first-match-wins; registered them in the `tests` list and the module docstring `Covers:` section.
- `/home/knatte/Code/millhouse/wts/claude-plugin-root-env-setup/plugins/mill/skills/mill-setup/SKILL.md` — Phase 4.8 write snippet and Phase 8 verify snippet both switched to call `_config.resolve_plugin_root_from_syspath(sys.path)` instead of reading `os.environ['CLAUDE_PLUGIN_ROOT']` directly, dropping the manual `sys.path.insert` line.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py` passed all 60 tests. Pre-existing ruff lint issues in both touched files (import ordering, `__all__` sort, nested `with`) predate this batch's changes (confirmed via `git show HEAD:...`) and were left untouched, per "never edit files outside this batch's declared scope."

{"status":"success","commit_sha":"9a64082567949c1bf75218f7b6ba63d986d34651","session_id":"429c8e3f-a4b1-4447-9a91-07211eb8a58d","cards_done":[1,2,3]}
