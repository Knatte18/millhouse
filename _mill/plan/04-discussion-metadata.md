# Batch: discussion-metadata

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "discussion-metadata"
number: 4
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-discussion-flow.py
depends-on: [2, 3]
```

## Batch Scope

Threads `duration_s`/`tool_calls`/`cost_usd` through the discussion review backend: `finalize()`
forwards them to `finalize_scope()` and surfaces them in its `reviews[...]` entry, and `run()`
sources them from the `ReviewerCallResult` and carries them through both of this backend's
ERROR-producing branches. This is the smallest of the three backend batches — `_review_discussion.run`
has a single reviewer call and no `NEED_CONTEXT` retry path — so it is the reference shape batches 5
and 6 follow.

Batch 7 consumes the interface this batch establishes: `finalize(..., duration_s=, tool_calls=,
cost_usd=)` on each backend, mirroring today's `actual_model` keyword.

## Cards

### Card 17: `finalize()` accepts and persists the three metrics

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add keyword-only `duration_s: float | None = None`, `tool_calls: int | None = None`,
  `cost_usd: float | None = None` to `finalize`, documented in its Args section the same way
  `actual_model` already is (orchestrator-supplied, threaded to `finalize_scope`).
  Pass all three to the `finalize_scope` call, and add the same three keys to the success-path
  `reviews[...]` entry dict, sourced from the returned `review_entry`.
  In the `except ReviewError` branch, call `apply_cost_metadata` on `raw_text` (importing it from
  `_review_common` alongside the existing imports) before the `write_review_file` call, so the raw
  parse-failure file carries the metrics too, and add the three keys to that branch's synthetic
  `ERROR` entry as well. Do not guard the `apply_cost_metadata` call — it is a documented no-op when
  the raw text has no yaml fence.
- **Commit:** `feat(review): thread cost metadata through discussion finalize`

### Card 18: `run()` sources the metrics from the reviewer call

- **Context:**
  - `plugins/mill/scripts/_llm_common.py`
  - `plugins/mill/scripts/_reviewer_single.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `run`, after the `res = _reviewer_single.run(spec, prompt_text)` call added in batch 2, capture
  `res.duration_s`, `res.tool_calls` and `res.cost_usd` into locals and pass them to the `finalize`
  call at the end of the function. `_review_discussion.run` makes exactly one reviewer call and has
  no `NEED_CONTEXT` retry path, so no summation is needed here.
  In the `except LLMError` branch, set the synthetic `ERROR` entry's `duration_s` to
  `getattr(exc, "duration_s", None)` and its `tool_calls`/`cost_usd` to `None` — the call never
  returned, so there is no result object to read them from, and the exception carries only duration.
  The `rounds == 0` short-circuit entry gets the three keys set to `None` (the review never ran).
- **Commit:** `feat(review): report reviewer call cost from discussion run path`

### Card 19: flow-test coverage for both ERROR branches

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add three cases.
  (1) Happy path: drive `run` through `_reviewer_test_stub` and assert the resulting
  `reviews[0]` carries `duration_s` (the stub's `0.0`), `tool_calls` (`None`) and `cost_usd`
  (`None`), and that the written review file's yaml header carries a `duration_s:` line.
  (2) Call-failure ERROR: monkeypatch `_reviewer_single.run` to raise an `LLMError` constructed with
  `duration_s=12.5`, and assert the synthetic `ERROR` entry carries `duration_s == 12.5` with
  `file` still `None`.
  (3) Parse-failure ERROR: have the reviewer return text that `parse_verdict` rejects with a real
  `ReviewerCallResult` carrying a known `duration_s`, and assert both that the `ERROR` entry carries
  that value and that the raw file `write_review_file` wrote has the `duration_s:` line injected
  into its yaml header. Include a variant of (3) whose raw text has no yaml fence at all, asserting
  the file is written unchanged and the run does not raise.
- **Commit:** `test(review): cover discussion cost metadata on success and both ERROR paths`

## Batch Tests

`verify:` runs `test-review-discussion-flow.py`, the flow test that owns `_review_discussion`'s
coverage and the only test file this batch edits. Its existing cases already assert the shape of
both ERROR entries, so a regression in the untouched fields fails there too.
