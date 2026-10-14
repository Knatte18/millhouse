# Batch: cleanliness-status-exclusion

```yaml
task: Instrument and bound the verify runner
batch: cleanliness-status-exclusion
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py
depends-on: []
```

## Batch Scope

Makes `_cleanliness.py`'s dirty-tree helpers ignore `_mill/status.md`, so an uncommitted `## Verify log` row never blocks mill-go's step-2b gate, the Handoff terminal-dirt gate, or the finalize no-JSON inference path.
Independent of batch 1: no runner code is needed, only the path exclusion.
Batch 3 imports `_cleanliness.is_status_md_path` for the matching exclusions in `_implementer_common.py`.

## Cards

### Card 5: Exclude status.md from cleanliness dirt gates

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add public `is_status_md_path(path: str) -> bool` to `_cleanliness.py`: true when a repo-root- or hub-relative path is `_mill/status.md` at any depth, i.e. `("/" + path).endswith("/_mill/status.md")` -- the same any-depth idea as the briefs check `"/_mill/briefs/" in "/" + path` (signature inlined, no file read needed).
  Docstring: status.md is orchestrator-owned; verify runs append `## Verify log` rows to it between orchestrator status commits, so its dirt is never implementer work.
  Apply it:
  - `compute_new_dirt`: drop porcelain lines whose path (`line[3:]`) satisfies `is_status_md_path` from both the snapshot set and the live set before the set difference.
  - `compute_terminal_dirt`: drop such lines from `lines` before `_filter_to_task_scope`.
  - `revert_out_of_scope_drift`: skip such lines entirely (never reverted, never added to `remaining_in_scope_lines`), checked on the git-root-relative path before rebasing.
  Update each function's docstring with one sentence naming the exclusion.
  Tests in `test-cleanliness.py`, using the file's existing real-git tempdir fixtures: `is_status_md_path` true for the inputs "_mill/status.md" and "sub/hub/_mill/status.md", false for "_mill/status.md.bak", "x_mill/status.md" and "_mill/plan/00-overview.md";
  a dirty fixture status.md alone yields `[]` from `compute_new_dirt`, `[]` from `compute_terminal_dirt`, and `([], [])` from `revert_out_of_scope_drift`;
  a dirty fixture status.md next to a dirty in-scope source file still reports the source file from each of the three functions.
- **Commit:** `fix(cleanliness): ignore status.md dirt in batch and terminal gates`

## Batch Tests

`verify:` runs `test-cleanliness.py`, which passes on this branch's base and covers every function this card edits.
