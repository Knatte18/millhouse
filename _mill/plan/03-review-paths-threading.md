# Batch: review-paths-threading

```yaml
task: "Sub-project repo (hub_relative_path) support"
batch: "review-paths-threading"
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-cli.py
depends-on: [2]
```

## Batch Scope

This batch threads `git_root` through `_review_code.run()` and `_review_plan.run()` so the new `resolve_ref_paths` and `resolve_existing_paths` fallback (added in batch 1) actually fires at runtime. The work touches `_review_code.py`, `_review_plan.py`, `millpy-review-code.py`, and `millpy-review-plan.py`. `millpy-review-code.py` and `millpy-review-plan.py` are also edited in batch 2 (different lines — `load_config` call vs `_review_*.run` call) — the depends-on:[2] edge serialises the work so the implementer applies batch 2's changes first and batch 3 layers on top without overlapping edits at the same source location.

`millpy-review-discussion.py` does not call either function — it is not edited in this batch.

Verified callsites (3 `resolve_ref_paths`, 6 `resolve_existing_paths`) match the tables in discussion.md `### resolve_ref_paths and resolve_existing_paths signature change`. The implementer must re-grep at implementation time and halt if the count drifts (per the source-of-truth verification rule in discussion.md).

Batch-local decisions:
- Each `*.run()` function gains a `git_root: Path` positional or keyword arg. Per the existing signatures' style (keyword-rich, mostly kw-only after `*`), thread it as a keyword arg named `git_root`. Place it in the same kwargs block as `project_root`.
- The main entry in `millpy-review-code.py` already calls `_paths.resolve_git_root()` (line 73 area); reuse the existing local variable. If not present, add `git_root = _paths.resolve_git_root()` next to the existing `project_root = Path.cwd()`. Same in `millpy-review-plan.py`.

## Cards

### Card 9: thread `git_root` through `_review_code.run` and `millpy-review-code.py`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Re-grep `resolve_ref_paths` and `resolve_existing_paths` in `_review_code.py` and assert 1 + 2 callsites respectively (line 254 for `resolve_ref_paths`; lines 274 and 374 for `resolve_existing_paths`). If counts differ, halt and surface the discrepancy. In `_review_code.run()`'s signature, add a new keyword arg `git_root: Path` (no default — required, since every existing caller in this codebase has a git_root to pass). Update all three callsites inside `run()` to pass `git_root=git_root`. In `plugins/mill/scripts/millpy-review-code.py`'s `main()`, ensure `git_root = _paths.resolve_git_root()` is computed (it likely already is — read lines 73-105 to confirm). Pass `git_root=git_root` to the `_review_code.run(...)` invocation at line 105. After the edit, re-grep `_review_code.py` and assert every `resolve_ref_paths(` and `resolve_existing_paths(` call inside `run()` includes a `git_root=` kwarg.
- **Commit:** `feat(_review_code): thread git_root through run() into resolve_ref/existing_paths`

### Card 10: thread `git_root` through `_review_plan.run` and `millpy-review-plan.py`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Re-grep `resolve_ref_paths` and `resolve_existing_paths` in `_review_plan.py` and assert 2 + 4 callsites respectively (lines 134 and 470 for `resolve_ref_paths`; lines 140, 205, 476, 544 for `resolve_existing_paths`). If counts differ, halt and surface the discrepancy. In `_review_plan.run()`'s signature, add a new keyword arg `git_root: Path` (no default). Update all six callsites inside the module (whether `run()` calls them directly or via inner helper functions) to pass `git_root=git_root`. Where a helper function inside `_review_plan.py` consumes a callsite, add the `git_root` kwarg to the helper's signature too — do not introduce module-level state. In `plugins/mill/scripts/millpy-review-plan.py`'s `main()`, ensure `git_root = _paths.resolve_git_root()` is computed and pass `git_root=git_root` to the `_review_plan.run(...)` invocation. Match the threading shape used in card 9 for symmetry. After the edit, re-grep `_review_plan.py` and assert every `resolve_ref_paths(` and `resolve_existing_paths(` call includes `git_root=`.
- **Commit:** `feat(_review_plan): thread git_root through run() into resolve_ref/existing_paths`

## Batch Tests

The batch's `verify:` runs the full unit-test suite. The existing `test-review-common.py` tests now cover the `git_root` fallback's hit / miss / no-kwarg / wiki-prefix / creates_union semantics. No new tests are added in this batch — threading is mechanical, and the runtime behaviour is exercised by batch 5's integration test. Coverage:
- `test-review-common.py` — kwarg fallback semantics (added in batch 1).
- Existing `test-review-code.py`, `test-review-plan.py`, `test-review-discussion.py` — must continue to pass after the signature change. If `_review_code.run()` or `_review_plan.run()` is called from a test without a `git_root` kwarg, the test must be updated to pass a sensible value (typically the test's own scratch dir).
