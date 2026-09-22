Both cards of batch inlined-style-blocks (2 of 2) are committed, honestly verified against the git log range da6b2038..HEAD:

- Card 9 (commit 6dac60ce): inserted the byte-identical `## Writing style` block after `<TOOL_RULE>` in all five reviewer prompt templates (plugins/mill/templates/review-code-batch.md, review-code-holistic.md, review-discussion.md, review-plan-batch.md, review-plan-holistic.md).
- Card 10 (commit 72d06139): inserted the same block after the `## Tools` section in the three skill-less agent briefs (plugins/mill/templates/fixer-holistic-brief.md, merge-in-conflict-brief.md, merge-in-verify-brief.md).

All eight copies verified byte-identical via diff, and `grep -c "Apply a per-sentence cut test"` returns exactly 1 in each of the eight files. No `<UPPERCASE>` token was introduced. Batch verify command (`test-review-templates.py`) passed all 9 tests. `git status --porcelain --untracked-files=no` is clean (no tracked modifications outstanding).

Both commits pushed to hanf/prose-skill-gaps.

{"status":"success","commit_sha":"72d0613984d991765098cfad09d80be1ab86df38","session_id":"0d10d827-ffba-49e2-8219-9b6c41148aa3","cards_done":[9,10]}
