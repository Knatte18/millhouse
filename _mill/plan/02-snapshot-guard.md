# Batch: snapshot-guard

```yaml
task: '66 (A) -- Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv'
batch: snapshot-guard
number: 2
cards: 2
verify: python plugins/mill/unit_tests/test-review-common-guard.py
depends-on: []
```

## Batch Scope

Rewrite `worktree_snapshot_guard` in `_review_common.py` so the after-snapshot check always runs, regardless of whether the wrapped block raised (#336). Today the `except Exception: raise` short-circuits the post-snapshot capture, meaning a reviewer that overstepped AND produced unparseable output is reported as the downstream parse error -- the more dangerous `ReviewerOverstepError` never fires. The fix captures any inner exception via `try/except as inner_exc`, runs the after-snapshot unconditionally, then raises `ReviewerOverstepError` (chaining the inner via `__cause__`) if state mutated, otherwise re-raises the inner exception untouched. Add unit tests covering all four cells of the (inner raises Y/N) x (state mutated Y/N) matrix.

External interface: no signature change. `ReviewerOverstepError` and the inner helpers (`_capture_head_sha`, `_capture_porcelain`, `_filter_porcelain`, `_porcelain_diff`) are unchanged.

## Cards

### Card 3: rewrite `worktree_snapshot_guard` body to always run the after-snapshot

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the body of `worktree_snapshot_guard` (currently lines 118-153 of `_review_common.py`) with the structure below. Keep the function signature, the existing `before_sha = _capture_head_sha(project_root)` and `before_porcelain = _capture_porcelain(project_root)` calls, the existing `_filter_porcelain` invocations, and the existing `_porcelain_diff` helper call. Do not modify `_capture_head_sha`, `_capture_porcelain`, `_filter_porcelain`, `_porcelain_diff`, or `ReviewerOverstepError`.

  New body shape (after the two `before_*` capture lines):
  ```python
  inner_exc: Exception | None = None
  try:
      yield
  except Exception as exc:
      inner_exc = exc
  after_sha = _capture_head_sha(project_root)
  after_porcelain = _capture_porcelain(project_root)
  before_filtered = _filter_porcelain(before_porcelain, expected_paths)
  after_filtered = _filter_porcelain(after_porcelain, expected_paths)
  if before_sha != after_sha or set(before_filtered) != set(after_filtered):
      diff = _porcelain_diff(before_filtered, after_filtered)
      raise ReviewerOverstepError(before_sha, after_sha, diff) from inner_exc
  if inner_exc is not None:
      raise inner_exc
  ```

  Update the function's docstring so the "Exceptions raised inside the with-block propagate unchanged" sentence is replaced with two sentences: (1) "If the wrapped block raises AND state was mutated, ``ReviewerOverstepError`` takes priority and chains the inner exception via ``__cause__``; if state was unchanged the inner exception is re-raised unchanged." (2) "If the post-snapshot capture itself raises (e.g. ``_capture_head_sha`` propagating a ``ReviewError`` from a broken git invocation), that error propagates and the inner exception is NOT chained -- the capture failure indicates the snapshot is untrustworthy, so the typed `ReviewerOverstepError` cannot be raised safely. This is an intentional trade-off; the inner exception, if any, is visible in the traceback frames above the capture call."
- **Commit:** `fix(review-common): always run worktree_snapshot_guard after-snapshot, prefer overstep error`

### Card 4: unit test covering the four (inner-raise x state-mutated) cells

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-common-guard.py`
- **Deletes:** none
- **Requirements:** Create a `unittest.TestCase` test file exercising `worktree_snapshot_guard` against a real (temporary) git repo. Use `tempfile.TemporaryDirectory()` plus `subprocess.run(["git", "init", ...])` and a configured user.name/user.email (see `test-bg-launcher.py` or `test-builder-lock.py` for an existing pattern that wires a temp git repo). Create an initial commit so HEAD has a SHA.

  Four test cases, each its own `def test_*` method:
  1. `test_clean_exit_clean_state` -- run `with worktree_snapshot_guard(repo):` with `pass` as the body. Expect: no exception.
  2. `test_clean_exit_state_mutated` -- run with a body that creates a new commit (e.g. `subprocess.run(["git", "commit", "--allow-empty", "-m", "x"])`). Expect: `ReviewerOverstepError` raised; `exc.before_sha != exc.after_sha`.
  3. `test_inner_raises_clean_state` -- run with `raise RuntimeError("inner sentinel")` as the body. Expect: `RuntimeError` propagates unchanged with message `"inner sentinel"`. Use `self.assertRaises(RuntimeError) as ctx` and assert `str(ctx.exception) == "inner sentinel"`.
  4. `test_inner_raises_state_mutated` -- inside the body, first mutate state (e.g. create an empty commit), then raise `RuntimeError("inner sentinel")`. Expect: `ReviewerOverstepError` raised; `exc.__cause__` is the `RuntimeError`; `str(exc.__cause__) == "inner sentinel"`.

  For state-mutation cases, set `expected_paths=None` (the default) so the empty-commit HEAD shift is detected. Use `_review_common.ReviewerOverstepError` from the import.

  Standalone-runnable (`python plugins/mill/unit_tests/test-review-common-guard.py`) and via `run-all.py`.
- **Commit:** `test(review-common): cover guard after-snapshot for all four exception/state cells`

## Batch Tests

`verify:` runs `test-review-common-guard.py`. The four-cell matrix is the complete behaviour spec for the rewritten guard. Cases 1-2 are regression guards (existing behaviour); cases 3-4 cover the new "always runs after-snapshot" semantics. No other test file is affected by this batch.
