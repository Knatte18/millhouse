Batch "dispatch-directive" (02-dispatch-directive.md) complete: 2 of 2 cards committed.

- Card 5: `plugins/mill/unit_tests/test-language-skills-directive.py` — added `` `prose` `` assertions to all seven behaviour tests, plus the once-only count assertion in `test_mixed_languages`, and fixed the module docstring's `Covers:` line and `test_no_recognized_languages`' docstring to name both unconditional skills. Committed as 83b26f83.
- Card 6: `plugins/mill/scripts/_agent_dispatch.py` — seeded `language_skills_directive()`'s skills list with `` `prose` `` ahead of `` `code-quality` ``, fixed the no-recognized-language branch to render every unconditional skill (plural wording) instead of dropping all but the first, and updated the function/module docstrings. Confirmed `implementer-brief.md` and `fixer-batch-brief.md` need no edit since both render `<LANGUAGE_SKILLS>` and already list `Skill` under `## Tools`. Committed as dd5b4fe0.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-language-skills-directive.py` passed (all 9 tests in the file green).

Pre-report self-check: `git status --porcelain --untracked-files=no` is clean, no uncommitted tracked changes.

Ran `uvx ruff check` on the two touched files ad hoc; each reported one pre-existing, unrelated finding outside the lines I edited (an unused `noqa` in the test file's import block, and an unsorted `__all__` in `_agent_dispatch.py`) — left untouched as out of scope for this batch.

{"status":"success","commit_sha":"dd5b4fe0c99d7c3e0083c7007ff6900639a2162e","session_id":"fe5bea13-f8a0-4a3b-b38f-c6ac8b01dcba","cards_done":[5,6]}
