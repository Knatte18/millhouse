# Review: 12 (C) — Restructure hub junction layout — 02-spawn-wiki-config

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-spawn-wiki-config
date: 2026-05-06
```

## Findings

### [BLOCKING] `write_wiki_active_task_md` ships with zero test coverage
**Step:** Card 8 (test-spawn-core.py), Requirement 5
**Issue:** The plan explicitly skips adding a unit test for `write_wiki_active_task_md`, citing "requires a real wiki git repo." This is factually incorrect — `_make_wiki` in `test-spawn-core.py` already creates a local bare remote + working clone and is used by `test_claim_in_wiki` and `test_multi_select_groom_then_claim_basic`. The "integration tests in test-millpy-spawn.py" cited as coverage are mock-based and never invoke the real implementation. A new public API function (directory creation + file write + git commit/push) ships with no test coverage at all.
**Fix:** Add `test_write_wiki_active_task_md` to `test-spawn-core.py` using `_make_wiki` and `_make_git_repo` — at minimum assert the directory is created, `task.md` contains expected fields, and a commit lands in the wiki log.

### [NIT] Card 9 stub in `test_smoke_import` is unnecessary
**Step:** Card 9, Requirement 1 — test-millpy-spawn.py
**Issue:** The plan adds `spawn_core_mod.write_wiki_active_task_md = MagicMock()` to `test_smoke_import` to "prevent AttributeError in main()," but `test_smoke_import` does not call `main()` and `_spawn_core` is a plain `types.ModuleType`, not a MagicMock. The call in `main()` is not reached during module load.
**Fix:** Add the stub as a comment explaining it is pre-emptive for a future module-level import, or omit it; the test passes without it.

## Verdict

REQUEST_CHANGES
One blocking gap: `write_wiki_active_task_md` has no unit test despite `_make_wiki` fixture being available.