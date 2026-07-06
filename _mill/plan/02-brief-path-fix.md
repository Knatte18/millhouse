# Batch: brief-path-fix

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
batch: brief-path-fix
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-code-flow.py
depends-on: []
```

## Batch Scope

Fixes #601 and #607: `millpy-review-plan.py` and `millpy-review-code.py` both write their review brief under `git_root`'s `_mill/briefs/` instead of the nested project's own `_mill/briefs/`, leaving orphaned directories in nested-layout repos. This is a straight regression (introduced by commit `e5e26571`) with an already-correct pattern to copy from `millpy-review-discussion.py`. Independent of every other batch in this plan — no shared code or DAG dependency.

## Cards

### Card 6: Fix millpy-review-plan.py brief_path

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")` to `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")`, where `project_root = _paths.resolve_hub_path()` (already computed earlier in the script). Delete the stale comment above it ("Write the brief under the task worktree (git_root), not the hub root, so the implementer's brief path is relative to the task branch checkout.") since it describes the bug, not the intent.
- **Commit:** `fix(review-plan): resolve brief_path under hub root, not git_root (#601)`

### Card 7: Fix millpy-review-code.py brief_path

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Identical fix to Card 6, applied to `millpy-review-code.py`'s copy-pasted `briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")` line and its identical stale comment.
- **Commit:** `fix(review-code): resolve brief_path under hub root, not git_root (#607)`

### Card 8: Add nested-layout case to test-review-plan-flow.py

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a nested-layout fixture case (hub_root nested one level under git_root) asserting the prepare-stage `brief_path` in the returned JSON envelope resolves under the nested `project_root`'s `_mill/briefs/`, not under `git_root`'s. Existing flat-layout assertions must remain unchanged.
- **Commit:** `test(review-plan-flow): cover nested-layout brief_path resolution (#601)`

### Card 9: Add nested-layout case to test-review-code-flow.py

- **Context:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a nested-layout fixture case symmetric to Card 8, for `millpy-review-code.py`'s prepare-stage `brief_path`.
- **Commit:** `test(review-code-flow): cover nested-layout brief_path resolution (#607)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-code-flow.py` runs both affected test files, covering existing flat-layout coverage plus the two new nested-layout cases.
