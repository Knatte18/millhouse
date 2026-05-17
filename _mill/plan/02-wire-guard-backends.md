# Batch: wire-guard-backends

```yaml
task: '63 (A) — Reviewer tool-sandbox: git snapshot guard + fix --allowedTools'
batch: wire-guard-backends
number: 2
cards: 3
verify: python plugins/mill/unit_tests/test-review-plan-flow.py && python plugins/mill/unit_tests/test-review-code-flow.py && python plugins/mill/unit_tests/test-review-discussion-flow.py
depends-on: [1]
```

## Batch Scope

Wire each of the three review-backend `run()` functions to enter `worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]])` around the existing body. The guard catches any HEAD or working-tree change introduced by a reviewer LLM call. The reviews_dir entry in `expected_paths` lets `write_review_file`'s legitimate untracked output pass through. Existing per-backend control flow (parallel `ThreadPoolExecutor` fan-out, holistic call, NEED_CONTEXT resume retries, error-tail handling) is preserved unchanged.

Depends on batch 1's `worktree_snapshot_guard` and `ReviewerOverstepError`. The existing flow tests (`test-review-plan-flow.py`, `test-review-code-flow.py`, `test-review-discussion-flow.py`) run the backends end-to-end via `_reviewer_test_stub`, which never mutates git — they must remain green with the guard wired in.

External interface: no public-API change. `run()` continues to return `ReviewResult` or raise `ReviewError`; `ReviewerOverstepError` propagates as a `ReviewError` to the API-layer catch sites in `millpy-review-*.py`.

## Cards

### Card 3: Wrap _review_plan.run() body in worktree_snapshot_guard

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. In `_review_plan.py`, add `worktree_snapshot_guard` to the existing import block from `_review_common`:

     ```python
     from _review_common import (
         # ... existing imports ...
         worktree_snapshot_guard,
     )
     ```

     Preserve alphabetical ordering within the import tuple if present; otherwise append.

  2. Locate the existing `def run(cfg, slug, mill_dir, wiki_root, project_root, *, max_rounds=None, holistic_only=False, no_holistic=False) -> ReviewResult:` function. Currently the body starts with the `if holistic_only and no_holistic:` precondition check (line 284). The validation check must remain BEFORE the guard (a precondition failure should not consume a snapshot). Everything from `# 1. Paths and round` (line 287) through the closing `return ReviewResult(...)` (line 622-628) is the body to wrap.

  3. Wrap that body in `with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):`. Indent the wrapped body one level. The final `return ReviewResult(...)` lives inside the with-block.

  4. Do not add any `try/except ReviewerOverstepError` — let it propagate as a `ReviewError` to the API-layer catch in `millpy-review-plan.py`. Existing `except ReviewError` sites continue to work because of the subclass relationship.

  5. ASCII rule: no new `print()` strings are added in this card. The guard helper raises with an already-ASCII message.

- **Commit:** `feat(_review_plan): wrap run() in worktree_snapshot_guard`

### Card 4: Wrap _review_code.run() body in worktree_snapshot_guard

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. In `_review_code.py`, add `worktree_snapshot_guard` to the existing import block from `_review_common`.

  2. Locate `def run(cfg, slug, mill_dir, wiki_root, project_root, *, max_rounds=None, batch_name=None, extra_files=None) -> ReviewResult:`. The entire body — from `# 1. Paths + round counter` to the final `return ReviewResult(...)` — is wrapped in `with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):`. The wrapped block covers the NEED_CONTEXT resume retry path on both happy and error branches.

  3. The early-exit `except LLMError` branch (around line 318) that returns a `ReviewResult` with `verdict: ERROR` is inside the guard block — preserved as-is. The guard checks state on with-block exit regardless of which return path is taken, so the LLMError early-return is still snapshot-validated.

  4. Same propagation rule as card 3: do not catch `ReviewerOverstepError` locally.

- **Commit:** `feat(_review_code): wrap run() in worktree_snapshot_guard`

### Card 5: Wrap _review_discussion.run() body in worktree_snapshot_guard

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. In `_review_discussion.py`, add `worktree_snapshot_guard` to the existing import block from `_review_common`.

  2. Locate `def run(cfg, slug, mill_dir, project_root, wiki_root, *, max_rounds=None) -> ReviewResult:`. Note the parameter order here differs from `_review_plan`/`_review_code` — `project_root` is the 4th positional, `wiki_root` is the 5th. Pass the correct one to the guard (`project_root`).

  3. Wrap the entire body — from `# 1. Resolve paths` to the final `return ReviewResult(...)` — in `with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):`.

  4. The existing `try: raw, session_id = _reviewer_single.run(spec, prompt_text)` / `except LLMError as exc: raise ReviewError(f"All sub-reviews failed: {exc}") from exc` block is inside the guard — when `LLMError` is caught and re-raised as `ReviewError`, propagation past the guard's `__exit__` will still cause the guard to re-raise the original exception (the `except Exception: raise` branch in the helper). On normal return, the guard then performs the after-snapshot check. Both behaviours are correct.

- **Commit:** `feat(_review_discussion): wrap run() in worktree_snapshot_guard`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-review-plan-flow.py && python plugins/mill/unit_tests/test-review-code-flow.py && python plugins/mill/unit_tests/test-review-discussion-flow.py`

The three flow tests run each backend end-to-end against `_reviewer_test_stub`, which never mutates git. Adding the guard must not change any test outcome — same PASS lines as before this batch. Any new FAIL means either an import error, a parameter mismatch (especially the `_review_discussion.run` positional-arg ordering), or a stub fixture that accidentally writes outside `_mill/reviews/`. None of those should occur if the wrap is purely additive.

No new unit test is needed in this batch — the guard helper itself is covered by `test-review-guard.py` (batch 1). The flow tests verify the wiring does not regress existing behaviour.
