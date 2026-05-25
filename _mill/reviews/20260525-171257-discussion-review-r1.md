# Review: Green the unit test suite on wiki-v3-adoption so it can merge to main

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-25
```

## Findings

### [GAP] RC2 sample call uses wrong kwarg name
**Section:** `### RC2 -- test-bg-launcher fixture registers slug via wiki.upsert_task`
**Issue:** The Decision shows `wiki.upsert_task(wiki_path, slug=slug, title=title, phase="active")`, but `upsert_task`'s actual signature at `_client.py:41` uses `status`, not `phase`; a planner following the sample literally gets `TypeError: unexpected keyword argument 'phase'`.
**Fix:** Change `phase="active"` to `status="active"` in the Decision text (verified: `status: str | None = None` is the parameter name at `_client.py:49`).

### [GAP] RC1 scope misses tasks.json seeding for test-marker.py happy-path tests
**Section:** `### RC1-test` and `## Technical context` (eight RC1 files)
**Issue:** `test-marker.py`'s happy-path tests (e.g., `test_slug_from_branch_happy_path`) call `slug_from_branch` → `wiki.list_tasks_brief`, which reads TinyDB (`tasks.json`); `_make_task_worktree` only writes `Home.md` and does not seed `tasks.json`; with an empty TinyDB the daemon returns `[]`, `slug_from_branch` raises `MarkerError`, and those tests stay red even after the RC1 log-handler fix.
**Fix:** The plan must also update `_make_task_worktree` (or the relevant fixtures) to call `wiki.upsert_task` to seed the task into `tasks.json`; this is the same mechanism as RC2, but the discussion categorises test-marker.py as RC1-only and does not address the missing seeding step.

### [NOTE] RC3 "both callsites" count is wrong
**Section:** `### RC3 -- migrate test-fold.py rmtree callsites`
**Issue:** The Decision says "Replace both callsites at `test-fold.py:95,97`", but grep finds only one `shutil.rmtree` call in the entire file (line 97); line 95 is a comment, not a callsite.
**Fix:** Change "both callsites" to "the callsite" and remove the `:95` line reference; the planner will see one call and handle it correctly regardless, but the inaccuracy could cause confusion.

## Verdict

GAPS_FOUND
Two concrete errors (wrong kwarg, incomplete RC1 scope) that would leave tests red after the plan executes.