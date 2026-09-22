2 of 2 cards committed (card 7 and card 8 — the batch declares 2 cards total).

Card 7: fixed `plugins/mill/skills/handoff/SKILL.md` so its emitted document's first-line directive reads "load `mill:prose`, then `mill:conversation`" instead of naming `mill:conversation` alone. Commit 69775ab1.

Card 8: created `plugins/mill/unit_tests/test-load-directive-convention.py` (new file), a plain-function-plus-`main()` test module following `test-language-skills-directive.py`'s structure. It exposes `check_text(text) -> str | None` implementing the discrimination/co-presence/order rule from the plan, five fixture-driven unit tests covering each scenario the plan specifies, and a tree-walk test over `plugins/*/skills/**/SKILL.md` + `plugins/mill/templates/*.md` (excluding `.claude/skills/` and `plugins/mill/scripts/*.py`). Commit d3d1f297.

Verify command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-load-directive-convention.py`) passed, all 6 sub-tests green.

Pre-report self-check: `git status --porcelain --untracked-files=no` is clean, no uncommitted tracked changes.

status: success
commit_sha: d3d1f297d738d1b5e2e4f219da514c1fc96cf75d
session_id: 1b5ac6ca-7468-4841-ace2-5754ec41b690
cards_done: [7, 8]

{"status":"success","commit_sha":"d3d1f297d738d1b5e2e4f219da514c1fc96cf75d","session_id":"1b5ac6ca-7468-4841-ace2-5754ec41b690","cards_done":[7,8]}
