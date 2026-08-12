# Batch: code-metadata

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "code-metadata"
number: 5
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py
depends-on: [2, 3]
```

## Batch Scope

Threads `duration_s`/`tool_calls`/`cost_usd` through the code review backend, following batch 4's
shape. Unlike the discussion backend, `_review_code.run` has a `NEED_CONTEXT` resume-retry that makes
a second reviewer call in the same round, so this batch is where the "sum across every call in a
round" Shared Decision first bites: two `LLMError` branches and two `ReviewError` branches, each with
different sources for the metrics.

## Cards

### Card 20: `finalize()` accepts and persists the three metrics

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add keyword-only `duration_s`, `tool_calls`, `cost_usd` (all `None`-defaulted) to `finalize`,
  documented in its Args section alongside `actual_model`, forwarded to the `finalize_scope` call,
  and added to the success-path `reviews[...]` entry from the returned `review_entry`.
  In `finalize`'s `except ReviewError` branch, call `apply_cost_metadata` (imported from
  `_review_common`) on `raw_text` before `write_review_file`, and add the three keys to that
  branch's synthetic `ERROR` entry.
  The `_splice_rename_nit_findings` call and the per-batch rename-NIT behaviour are untouched, and
  the splice must stay ahead of the `apply_cost_metadata` call in the ERROR branch's text flow so the
  written raw text still contains whatever the splice produced.
- **Commit:** `feat(review): thread cost metadata through code finalize`

### Card 21: `run()` sums metrics across the NEED_CONTEXT retry

- **Context:**
  - `plugins/mill/scripts/_llm_common.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Import `sum_optional` from `_review_common` (added there in batch 3) and use it for all three
  metrics — do not define a local copy; `_review_plan.py` uses the same helper from the same place.
  In `run`, initialise `duration_s`, `tool_calls`, `cost_usd` from the first call's `res`. On the
  `NEED_CONTEXT` path, after `retry_res = _reviewer_single.run(..., resume=True, ...)`, fold the
  retry's three values into the running totals with `sum_optional` before proceeding to
  `parse_verdict`. Pass the running totals to the final `finalize` call.
  The four error branches source their metrics as follows, and each gets all three keys:
  - initial `except LLMError`: `duration_s = getattr(exc, "duration_s", None)`, others `None` — the
    first call never returned.
  - initial `except ReviewError` (parse failure after a successful first call): the first call's
    already-known values from `res`, and `apply_cost_metadata` applied to `raw` before the existing
    `write_review_file` call.
  - retry `except LLMError`: the first call's values summed with `getattr(exc, "duration_s", None)`
    via `sum_optional`, since the round genuinely cost both attempts.
  - retry `except ReviewError`: the running totals (first call plus retry), with
    `apply_cost_metadata` applied to `raw` before its `write_review_file` call.
  The `rounds == 0` short-circuit entry gets the three keys set to `None`.
- **Commit:** `feat(review): sum reviewer call cost across code review retries`

### Card 22: flow-test coverage for summation and both ERROR branch kinds

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add cases.
  (1) Happy path: assert `reviews[0]` carries the three keys and the written file's yaml header has
  a `duration_s:` line.
  (2) Summation: drive the `NEED_CONTEXT` retry path with a `_reviewer_single.run` double returning
  two `ReviewerCallResult`s with distinct `duration_s`/`tool_calls`/`cost_usd`, and assert the final
  entry carries the sums, not the last call's values.
  (3) `None`-absorbing: same two-call path where the second result's `tool_calls`/`cost_usd` are
  `None`, asserting the first call's values survive rather than being zeroed or dropped.
  (4) Call-failure ERROR: `LLMError` with a `duration_s` on the initial call -> that value in the
  entry, `file` still `None`.
  (5) Retry call-failure ERROR: a successful first call plus an `LLMError` on the retry -> the
  entry's `duration_s` is the sum of both.
  (6) Parse-failure ERROR: text `parse_verdict` rejects -> the entry carries the call's metrics AND
  the raw file written by that branch has `duration_s:` injected into its header.
- **Commit:** `test(review): cover code review cost summation and ERROR-path metadata`

## Batch Tests

`verify:` runs `test-review-code-flow.py`, which owns `_review_code`'s coverage including both
`NEED_CONTEXT` branches and both ERROR shapes, and is the only test file this batch edits.
