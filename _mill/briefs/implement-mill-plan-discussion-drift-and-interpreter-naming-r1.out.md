3 of 3 cards committed, matching all three `Commit:` messages declared in the batch file. Verify passed cleanly. Working tree is clean.

{"status":"success","commit_sha":"1e8ec476b085d9c4ad97f958f0f001ea561cf867","session_id":"a0a155d7-8342-4948-8c28-d9d1e44864f9","cards_done":[1,2,3]}

Summary: Implemented all 3 cards of batch 01-mill-plan-discussion-drift-and-interpreter-naming in `/home/knatte/Code/millhouse/wts/mill-plan-entry-gate-and-misc-bugs/plugins/mill/skills/mill-plan/SKILL.md`:

- Card 1 (commit `531073d7`): Added the "Interpreter-naming note" paragraph naming `$MILL_PYTHON` explicitly for Phase: Plan's narrative Python calls (fixes #939).
- Card 2 (commit `b805007d`): Added `discussion_sha` capture at the top of Phase: Plan, a `discussion_sha:` frontmatter-persistence paragraph, and a pre-commit drift check that halts/blocks on a mismatch before committing the plan.
- Card 3 (commit `1e8ec476`): Added the reusable "Discussion drift guard" definition in Phase: Plan Review and threaded a guard-invocation instruction into all 6 LLM-dispatch sites (step 2 Agent-mode and subprocess branches, step 1.5 Agent-mode and subprocess re-invocations, step 3.5 Agent-mode and subprocess retries) — fixes #938.

All 3 commits are present in `git log 71d98b88..HEAD --oneline` matching the batch's declared `Commit:` messages exactly. `verify:` (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skill-helper-drift.py test-guards.py`) passed with 2/2 tests green. Working tree is clean (no uncommitted tracked changes). 3 of 3 cards fully complete.
