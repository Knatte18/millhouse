Both cards (2 of 2) are committed and pushed. The `verify:` command passes.

- Card 9: retargeted the old `mill-merge` step references in mill-merge-in, mill-status, mill-go-base SKILL.md files and CLAUDE.md to the `_merge.py` step functions and the `merge-in` callback.
- Card 10: comment-only edits in `plugins/mill/integration_tests/test-merge.py`.

Mapped sidebar regeneration to `_merge.step_wiki_done` and lock release to `_merge.run_merge`. Left a couple of "Step 5" mentions in the integration test's comments.

{"status":"success","commit_sha":"eb31b27877243b1057608dcaddca80fa6950c16c","session_id":"e984682e-2fd1-4a28-9422-7efb84492440","cards_done":[9,10]}
