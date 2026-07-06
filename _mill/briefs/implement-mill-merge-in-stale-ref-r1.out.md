```json
{"status":"success","commit_sha":"5fb274e6241ae97147c88f8d2db232b1a2cae062","session_id":"803801f1-235e-4559-9035-ca2ee52a251f"}
```

Both cards of batch `01-mill-merge-in-stale-ref` are implemented, committed, and pushed:

- `C:\Code\millhouse\wts\mill-script-fixes\plugins\mill\skills\mill-merge-in\SKILL.md` — Card 1: Step 1's no-op check now fetches `origin` and resolves `MERGE_REF` from `refs/remotes/origin/<parent-branch>` (falling back to the local `<parent-branch>` when that ref is missing or the local branch is ahead) before diffing `HEAD..MERGE_REF`; Step 3 re-derives the identical `MERGE_REF` before merging; the "No-op guarantee" section now documents the fetch as the one exception to "touches no task state". Commit `52c549c0`.
- `C:\Code\millhouse\wts\mill-script-fixes\plugins\mill\integration_tests\test-merge.py` — Card 2: `_setup_trio` now creates a real bare `hub-origin.git` remote for the hub and pushes `main` to it; the no-op-check assertion replicates the SKILL.md `MERGE_REF` resolution via `_run` calls and asserts it resolves to `"origin/main"`, proving the fetch-succeeds branch is exercised. Commit `5fb274e6`.

`verify:` (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py`) passes end-to-end, including the new `PASS: mill-merge-in no-op check empty (MERGE_REF='origin/main', ...)` assertion. Pre-existing `F541` ruff findings in `test-merge.py` (lines ~337-339, ~375-377, `_setup_nested_hub_scenario`) were confirmed present on `main` via `git show main:...` and left untouched as out-of-scope. `git status --porcelain --untracked-files=no` is clean; the only untracked file is the brief itself (`_mill/briefs/implement-mill-merge-in-stale-ref-r1.md`), outside this batch's declared scope.
