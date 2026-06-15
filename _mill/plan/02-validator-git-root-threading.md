# Batch: validator-git-root-threading

```yaml
task: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling
batch: validator-git-root-threading
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: [1]
```

## Batch Scope

Threads `git_root` through `_plan_validate` so the validator's source-ref checks resolve against `git_root/root` (the corrected behaviour added in batch 1) instead of mis-resolving under a subfolder cwd. Without this, the validator's `_check_non_existent_path` and `_check_batch_oversized` silently drop referenced files in the #471 layout, producing false `non-existent-path` findings and a wrong oversized estimate. External interface the next batch consumes: the new `git_root` keyword parameter on `_plan_validate.run(...)`, which the review CLI (batch 3) passes from its own `git_root`. Depends on batch 1 because the new candidate `git_root/root/raw` in `resolve_existing_paths` must exist for the threaded `git_root` to have any effect.

## Cards

### Card 4: thread git_root into _plan_validate

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a keyword-only `git_root: Path | None = None` parameter to `_plan_validate.run` (`_plan_validate.py:1007`), to `_check_non_existent_path` (`_plan_validate.py:226`), and to `_check_batch_oversized` (the function containing the `resolve_existing_paths` call at `_plan_validate.py:978`). In `run`, pass `git_root=git_root` into both the `_check_non_existent_path(...)` call and the `_check_batch_oversized(...)` call. Inside `_check_non_existent_path`, add `git_root=git_root` to BOTH `resolve_existing_paths([t], project_root, root, wiki_root=wiki_root)` calls (lines ~246 and ~264). Inside `_check_batch_oversized`, add `git_root=git_root` to the `resolve_existing_paths(list(context_tokens), project_root, root, wiki_root=wiki_root)` call (line ~978). Default `git_root=None` preserves current behaviour for any caller that does not pass it (full backward compatibility). Do not change any other check, the error-dict shapes, or the `root` defaulting from the overview.
- **Commit:** `fix(plan-validate): thread git_root into source-ref existence checks`

### Card 5: unit tests for git_root threading

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a case where `project_root` is the `root:` subfolder (i.e. `project_root == git_root / root`) and `git_root` is the repo top, with the referenced card files present at `git_root/root/<path>`. Assert that `run(..., git_root=git_root, root=<root>)` produces NO `non-existent-path` finding for those files and NO spurious `batch-oversized` finding from a zero-byte miscount (the files are found and sized correctly). Add a contrasting assertion that omitting `git_root` (the default `None`) in that same subfolder-cwd layout still mis-resolves (documents why the thread is required) — or, if simpler, assert only the positive case and note the negative in a comment. Use tempfile fixtures following the existing `test-plan-validate.py` style; build a minimal plan dir (`00-overview.md` + one batch file) referencing a real temp file under `git_root/root`.
- **Commit:** `test(plan-validate): cover git_root threading for subfolder-cwd layout`

## Batch Tests

`verify:` runs `test-plan-validate.py` only. Card 5's new case is the regression net proving the validator finds source refs under the #471 layout once `git_root` is threaded. Scope is the single edited validator module; no cross-cutting helper touched, so per-batch scoping is correct.
