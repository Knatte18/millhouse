{"status":"success","commit_sha":"d70778a2a4eecc32fb750aa696e489bb7be92bac","session_id":"971cadd3-eeee-4fbf-befa-84f67e3f2f72"}

All 5 of 5 cards in batch `03-prompt-surfaces.md` were committed successfully, and `verify:` passed (test-agents-defs.py + test-review-templates.py, both PASS).

Summary of work:

- Card 14: `plugins/mill/agents/mill-reviewer.md` -- granted `Write` in frontmatter tools, updated `description:`, reworded the blanket write-prohibition body line, updated the tool inventory / `MUST NOT use:` line, and replaced the sole-output sentence with the briefs-scoped `Write` guardrail (report file named by description only, no `<OUTPUT_FILE>` token). Commit `4ef17ecf`.
- Card 15: deleted the shared 4-line tool-prohibition header from all five templates (`review-discussion.md`, `review-code-batch.md`, `review-code-holistic.md`, `review-plan-batch.md`, `review-plan-holistic.md`), keeping only the REPORT-not-fix sentence and the `MILL_REVIEW_BEGIN`/`MILL_REVIEW_END` output-format section untouched. Commit `1f5c5437`.
- Card 16: `plugins/mill/templates/review-discussion.md` -- removed the false "You are in tool-use mode" clause from the source-grounding paragraph, left the other four templates' different (`## Files included`/`NEED_CONTEXT`) paragraphs untouched. Commit `f60d2a53`.
- Card 17: `plugins/mill/unit_tests/test-agents-defs.py` -- re-pinned `test_reviewer_agent_definition`'s exact-set assertion to `{Read, Grep, Glob, Write}` with `{Edit, Bash, NotebookEdit}` as the forbidden set; updated docstrings. Commit `1735f4cf`.
- Card 18: created `plugins/mill/unit_tests/test-review-templates.py` -- asserts all five templates render via `_review_common.render_prompt` with their exact backend token sets, the deleted prose stays deleted, the kept prose (MILL_REVIEW markers + REPORT instruction) stays kept, and no `<OUTPUT_FILE>` token appears anywhere. Commit `18069a4e`.
- Formatter drift (blank-line-after-docstring in both touched/created test files) committed separately as `chore(format): commit formatter drift`, commit `d70778a2`.

Final verify run: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agents-defs.py test-review-templates.py` -> PASS (all 6 test functions green).

{"status":"success","commit_sha":"d70778a2a4eecc32fb750aa696e489bb7be92bac","session_id":"971cadd3-eeee-4fbf-befa-84f67e3f2f72"}
