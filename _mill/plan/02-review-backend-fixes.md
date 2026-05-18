# Batch: review-backend-fixes

```yaml
task: '64 (A) -- Small infra fixes batch 9'
batch: review-backend-fixes
number: 2
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Four review-backend bug fixes, all independent of each other but grouped because they
share the same context: `_review_common.py` and the three review-runner modules. Card 5
adds `--- END FILE: ---` / `--- END DIFF: ---` close delimiters to `bulk_files()` and
`bulk_files_with_diff()`, eliminating the cross-file attribution ambiguity that causes
phantom BLOCKING findings in multi-file reviews. Cards 6, 7, and 8 each add a `rounds=0`
early-return path to `_review_code.py`, `_review_discussion.py`, and `_review_plan.py`
respectively, replacing the misleading `ReviewError("Round 1 exceeds max 0")` with a
clean APPROVE stub that matches the documented skip semantics.

No test files are modified in this batch; the new test coverage lives in batch 3
(which depends on this batch).

## Cards

### Card 5: Add END FILE / END DIFF close delimiters to `bulk_files` and `bulk_files_with_diff`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `bulk_files()` (around line 739): change:
  ```python
  parts.append(f"--- FILE: {p} ---\n{contents}")
  ```
  to:
  ```python
  parts.append(f"--- FILE: {p} ---\n{contents}\n--- END FILE: {p} ---")
  ```

  In `bulk_files_with_diff()` (around line 778-791), there are four `parts.append(...)` branches:
  - The two FILE fallback branches (diff failed, returncode != 0; and diff is full-file fallback) — each currently ends with `\n{file_content}`. Change each to end with `\n{file_content}\n--- END FILE: {p} ---`.
  - The DIFF branch (around line 788): change:
    ```python
    parts.append(f"--- DIFF: {p} (from {start_sha[:8]}) ---\n{diff_text}")
    ```
    to:
    ```python
    parts.append(f"--- DIFF: {p} (from {start_sha[:8]}) ---\n{diff_text}\n--- END DIFF: {p} ---")
    ```
  - The full-file branch (diff disabled or no start_sha, around line 791): change to end with `\n{file_content}\n--- END FILE: {p} ---`.

  Verify: every branch of both functions now appends a close delimiter matching the opener's type (FILE vs. DIFF) and path.
- **Commit:** `fix(review-common): add END FILE/END DIFF close delimiters to bulk_files`

### Card 6: Return APPROVE stub when `rounds=0` in `_review_code.py`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In the `run()` function, after `effective_max` is set (lines 197-200) and before the existing `if round_n > effective_max: raise ReviewError(...)` check (line 201), insert:
  ```python
  if effective_max == 0:
      print(
          f"[_review_code] rounds=0 -- review disabled, returning APPROVE",
          file=sys.stderr,
      )
      return ReviewResult(
          type="code",
          round=0,
          verdict="APPROVE",
          blocking_count=0,
          reviews=[{"scope": scope_label, "verdict": "APPROVE", "file": None, "skipped": True}],
      )
  ```
  `scope_label` is already defined at line 195 (`scope_label = batch_name or "holistic"`).
  `ReviewResult` is already imported at the top of the file.
- **Commit:** `fix(review-code): return APPROVE stub when rounds=0 instead of raising`

### Card 7: Return APPROVE stub when `rounds=0` in `_review_discussion.py`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In the `run()` function, after `max_rounds` is set (line 63) and before the existing `if round_n > max_rounds: raise ReviewError(...)` check (line 64), insert:
  ```python
  if max_rounds == 0:
      print(
          f"[_review_discussion] rounds=0 -- review disabled, returning APPROVE",
          file=sys.stderr,
      )
      return ReviewResult(
          type="discussion",
          round=0,
          verdict="APPROVE",
          blocking_count=0,
          reviews=[{"scope": "holistic", "verdict": "APPROVE", "file": None, "skipped": True}],
      )
  ```
  `ReviewResult` is already imported at the top of the file.
- **Commit:** `fix(review-discussion): return APPROVE stub when rounds=0 instead of raising`

### Card 8: Return APPROVE stub when `rounds=0` in `_review_plan.py` (kwarg path)

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  `_review_plan.py` already skips the batch and holistic paths when `cfg rounds == 0`
  (lines 326 and 333: `if reviewer_name is None or cfg[...]["rounds"] == 0: spec = None`).
  That existing logic handles the config-based skip. What is NOT handled is the `max_rounds`
  kwarg-override path: when `max_rounds=0` is passed to `run()` while config rounds > 0,
  `batch_max_rounds` and `holistic_max_rounds` are both set to 0, but the spec is non-null,
  so the review blocks are entered — and `if round_n > 0: raise ReviewError("Round 1 exceeds max 0")` fires.

  Fix: add a guard immediately before each `if round_n > <max_rounds>: raise ReviewError(...)` check:

  **Per-batch path** (within the batch review block, after `batch_max_rounds` is computed,
  before the `if round_n > batch_max_rounds` check at line ~127):
  ```python
  if batch_max_rounds == 0:
      print("[_review_plan] batch rounds=0 -- review disabled, returning APPROVE stub", file=sys.stderr)
      return ReviewResult(
          type="plan", round=0, verdict="APPROVE", blocking_count=0,
          reviews=[{"scope": batch_path.stem, "verdict": "APPROVE", "file": None, "skipped": True}],
      )
  ```

  **Holistic path** (within the holistic review block, after `holistic_max_rounds` is
  computed, before the `if round_n > holistic_max_rounds` check at line ~440):
  ```python
  if holistic_max_rounds == 0:
      print("[_review_plan] holistic rounds=0 -- review disabled, returning APPROVE stub", file=sys.stderr)
      return ReviewResult(
          type="plan", round=0, verdict="APPROVE", blocking_count=0,
          reviews=[{"scope": "holistic", "verdict": "APPROVE", "file": None, "skipped": True}],
      )
  ```

  Note: both guards return a partial `ReviewResult` from within the plan's aggregation
  loop. The implementer must confirm that returning early from within the batch or holistic
  sub-section produces a well-formed outer ReviewResult (i.e., the outer aggregation still
  assembles correctly). If the structure requires returning from the outer `run()`, adjust
  accordingly — the requirement is that `ReviewError` is NOT raised when `max_rounds=0`.

  `ReviewResult` is already imported at the top of the file.
- **Commit:** `fix(review-plan): return APPROVE stub when rounds=0 kwarg instead of raising`

## Batch Tests

No test files are modified in this batch. The verify command runs the full suite to
detect regressions: `python plugins/mill/unit_tests/run-all.py`. The new tests
that cover these changes live in batch 3, which depends on this batch.
