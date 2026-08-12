# Batch: dispatcher-flip

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "dispatcher-flip"
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-review-plan-flow.py
depends-on: [1]
```

## Batch Scope

Deletes batch 1's temporary adapter so `_reviewer_single.run()` returns `ReviewerCallResult`, and
updates every one of its callers to the new shape with a purely mechanical unwrap: the three review
backends, the benchmarking tool, and the two test call sites. No metric is threaded into any
`reviews[...]` entry or review file yet — that is batches 4/5/6, one per backend. Keeping this batch
mechanical is what lets the three metadata batches run in parallel afterwards without fighting over
the same lines.

The interface batches 4/5/6 consume: inside each backend's `run()`, the reviewer call's result
object is in scope under a local name (`res`, and `retry_res` on the `NEED_CONTEXT` path), carrying
`duration_s`/`tool_calls`/`cost_usd` ready to be summed and threaded.

## Cards

### Card 10: remove the dispatcher adapter

- **Context:**
  - `plugins/mill/scripts/_llm_common.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Edits:**
  - `plugins/mill/scripts/_reviewer_single.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Change `run`'s return annotation from `tuple[str, str]` to `ReviewerCallResult` (imported from
  `_llm_common` under `if TYPE_CHECKING:` or at module level — module level is fine, the module
  already has no import-cycle risk). Replace the two temporary unwraps added in batch 1 with direct
  returns: `return stub.run(...)` in the `provider == "test_stub"` branch and
  `return fn(prompt_text, **kwargs)` at the end. Delete the temporary-adapter comments and the
  matching note in the module docstring, and update the docstring's description of what `run`
  returns.
- **Commit:** `refactor(reviewers): return ReviewerCallResult from _reviewer_single.run`

### Card 11: mechanical unwrap in the three review backends

- **Context:**
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Every site that currently reads `raw, session_id = _reviewer_single.run(...)` becomes
  `res = _reviewer_single.run(...)` followed by `raw = extract_review_content(res.text)` and
  `session_id = res.session_id`, preserving each site's existing `extract_review_content` call
  (`_review_plan`'s two sites and `_review_code`'s two sites already call it on the next line;
  `_review_discussion`'s single site does too). On the `NEED_CONTEXT` resume-retry sites, name the
  local `retry_res` rather than reusing `res`, so batch 4/5/6 can sum both calls' metrics without
  re-deriving the first call's values.
  The call sites, by function, are: `_review_discussion.run`; `_review_code.run` (initial call and the
  `NEED_CONTEXT` retry); `_review_plan._review_one_batch` (initial call and the `NEED_CONTEXT`
  retry); `_review_plan.run`'s holistic block (initial call and the `NEED_CONTEXT` retry) — seven
  call sites in total across the three files.
  No behaviour changes here: no new dict key, no new function parameter, no change to any
  `except LLMError` or `except ReviewError` branch. Confirm by grep that no `raw, session_id =`
  unpack of a `_reviewer_single.run` call survives in `plugins/mill/scripts/`.
- **Commit:** `refactor(review): unwrap ReviewerCallResult at every backend call site`

### Card 12: benchmarking tool keeps working

- **Context:**
  - `plugins/mill/scripts/_reviewer_single.py`
- **Edits:**
  - `plugins/mill/integration_tests/bench-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  The `text, _sid = _reviewer_single.run(...)` unpack becomes attribute access on the returned
  result. This tool already collects and tabulates its own wall-clock timing; where it records that
  per-call metric, additionally record the result's `tool_calls` and `cost_usd` into the results
  table it writes under `.scratch/`, rendering an absent value as `n/a`. This file is outside
  `run-all.py`'s coverage and has no automated safety net — it must be run by hand per its own
  docstring after this batch.
- **Commit:** `refactor(bench): consume ReviewerCallResult in bench-reviewers`

### Card 13: update the two test call sites

- **Context:**
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `test-reviewers.py`, the four assertion sites that unpack `_reviewer_single.run(...)` as a
  2-tuple (`text, session_id = ...` and the three `text, sid = ...` sites) now read `.text` and
  `.session_id` off the returned `ReviewerCallResult`. The provider fakes updated in batch 1 stay as
  they are. Add one assertion that `_reviewer_single.run` passes the provider's `duration_s`,
  `tool_calls` and `cost_usd` through untouched — the dispatcher must not invent, round, or default
  any of them.
  In `test-review-plan-flow.py`, the `mock_run` double patched over
  `_review_plan._reviewer_single.run` returns a bare `(APPROVE_TEXT, "test-session-id")` tuple; it
  must return a `ReviewerCallResult` with the same text and session id. Its captured-timeout
  assertion is otherwise unchanged.
- **Commit:** `test(review): consume ReviewerCallResult at dispatcher test call sites`

## Batch Tests

`verify:` runs `test-reviewers.py` (the dispatcher's own coverage) and `test-review-plan-flow.py`
(the only flow test this batch edits, and the one carrying a hand-rolled `_reviewer_single.run`
double). `test-review-discussion-flow.py` and `test-review-code-flow.py` drive their backends
through `_reviewer_test_stub` rather than a hand-rolled double, so this batch's mechanical unwrap
needs no edit in them; they are exercised by batches 4 and 5, which do edit them. Per the batch
verify Shared Decision, naming an unedited flow test here would be rejected by the
`verify-unrelated-test-file` validator check.

`bench-reviewers.py` is an `integration_tests/` tool outside `run-all.py`; per discussion.md's
Testing section it is checked by a manual run, not by `verify:`.
