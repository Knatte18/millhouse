Both cards of batch `02-worktree-removal-longpaths` (2 of 2) were committed this turn:

- Card 3: `plugins/mill/scripts/_worktree.py` — added `-c core.longpaths=true` to `remove_safe`'s `git worktree remove` and `git worktree prune` argv, mirroring `_verify_baseline.py:106`'s creation-side placement. Commit `1c063521`.
- Card 4: `plugins/mill/unit_tests/test-worktree.py` — added a new test case (patches `_subprocess_util.run` to capture argv from both calls made by `remove_safe`, and `kill_stale_holders` as a no-op) asserting the `-c`/`core.longpaths=true` pair sits between `-C <cwd>` and `worktree` for both the remove and prune invocations. Commit `cd14dcc5`.

Verify: `PYTHONPATH= "$MILL_PYTHON" plugins/mill/unit_tests/test-worktree.py` (the command listed in `_mill/plan/00-overview.md`'s Batch Index for batch 2 -- the batch file's own frontmatter literally says `verify: null`, but its `## Batch Tests` section explicitly describes this exact test run, so I treated the frontmatter `null` as plan drift and ran the real test rather than skipping verification of new test coverage). All existing and new assertions passed; working tree is clean (`git status --porcelain --untracked-files=no` empty) after both commits were pushed.

{"status":"success","commit_sha":"cd14dcc5b06903bb9ea34c9740c66c8778ef93b3","session_id":"8492e35d-644c-4618-b014-a639fd86f40e","cards_done":[3,4]}
