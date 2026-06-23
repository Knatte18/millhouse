MILL_REVIEW_BEGIN
# Review: Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-23
```

## Findings

### [BLOCKING] Dirty-tree gate crashes test-millpy-implement.py regression suite
**Location:** Batch 2, Card 8 (threading) + Card 6 (dirty-tree gate)
**Issue:** Card 8 resolves `parent_branch` from the fixture's `parent: main` row (non-None) and `task_dir=status_path.parent` (non-None), so on every self-reported-success path `_in_scope_dirty_stuck` calls `_cleanliness.compute_terminal_dirt` -> `_pygit2_util.status_porcelain(project_root)`. In `test-millpy-implement.py` the fixture is NOT a real git repo and `compute_terminal_dirt` / `_pygit2_util` / `_parent_branch.resolve` are not mocked, so `status_porcelain` raises `GitOpsError`. Card 6 places this call in the self-reported-success branch OUTSIDE the `except Exception` wrapper, so it propagates and breaks `test_1_initial_dispatch_success`, `test_14_stage_finalize`, etc. — failing batch 2's own `verify:`.
**Fix:** Either wrap the new gate calls in the self-reported branch in `try/except Exception` (no-op on failure), or have Card 8 add a `compute_terminal_dirt`/`_parent_branch.resolve` mock to the test setUp.

### [NIT] Card 11 misstates merge.model as haiku
**Location:** Batch 3, Card 11
**Issue:** Card says "leave `merge.model: haiku` untouched", but `merge.model` is already `sonnethigh`.
**Fix:** Drop the `merge.model: haiku` reference; the only change is `roles.implementer.model`.

### [NIT] Card 4 attributes the status read to run() not prepare()
**Location:** Batch 1, Card 4
**Issue:** Card states `_review_code.run reads status_path`; the read actually lives in `_review_code.prepare` (lines 234-248), which `run` invokes.
**Fix:** Reword to reference `prepare` (called by `run`); no logic change.

## Verdict

REQUEST_CHANGES
Dirty-tree gate will crash batch 2's existing regression tests on the non-git fixture.
MILL_REVIEW_END
