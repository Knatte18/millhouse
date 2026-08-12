# Batch: plan-metadata

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "plan-metadata"
number: 6
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py
depends-on: [2, 3]
```

## Batch Scope

Threads `duration_s`/`tool_calls`/`cost_usd` through the plan review backend — the last and most
branch-heavy of the three. `_review_plan.py` has three distinct reviewer-call regions (the per-batch
`_review_one_batch`, the holistic block inside `run`, and the agent-mode `finalize`) and five
`ReviewError` sites, one of which deliberately writes no review file. That one site stays file-less:
the `_review_plan.py` file/no-file inconsistency Shared Decision forbids unifying it here.

## Cards

### Card 23: `_review_one_batch` reports its own cost

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Import `apply_cost_metadata` and `sum_optional` from `_review_common` alongside the existing
  imports.
  As the very first statement inside `_review_one_batch`'s outer `try:` block — before the
  `round_n = discover_round(...)` line — initialise `duration_s = tool_calls = cost_usd = None`.
  That `try` wraps code which can raise `ReviewError` before any reviewer call runs (the
  `round_n > max_rounds` guard and `resolve_ref_paths`' hard-fails), so without this the outer
  handler's read of those names would be an `UnboundLocalError`.
  In `_review_one_batch`, capture the first call's `res.duration_s`/`res.tool_calls`/`res.cost_usd`,
  fold the `NEED_CONTEXT` retry's `retry_res` values in with `sum_optional`, pass the running totals
  to the `finalize_scope` call, and add the three keys to the returned success dict.
  The `except LLMError` branch after the first call sets `duration_s` from
  `getattr(exc, "duration_s", None)` with the other two `None`; the retry's `except LLMError` branch
  sums the first call's values with the exception's duration via `sum_optional`.
  The function's outer `except ReviewError` handler (the one returning `"file": None`) gets the
  three keys populated from whatever totals are in scope at raise time, but must NOT start writing a
  review file — that file-less shape is pre-existing and deliberately preserved, so there is nothing
  for `apply_cost_metadata` to inject into on this path and it must not be called there. Add a short
  comment recording that this asymmetry with the other four `ReviewError` sites is intentional and
  out of scope to unify.
- **Commit:** `feat(review): report per-batch plan review cost`

### Card 24: `finalize()` accepts and persists the three metrics

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add keyword-only `duration_s`, `tool_calls`, `cost_usd` (all `None`-defaulted) to `finalize`,
  documented in its Args section alongside `actual_model`, forwarded to `finalize_scope`, and added
  to the returned success dict.
  In `finalize`'s `except ReviewError` branch — which does call `write_review_file` — apply
  `apply_cost_metadata` to `raw_text` before that write and add the three keys to the returned
  `ERROR` dict.
- **Commit:** `feat(review): thread cost metadata through plan finalize`

### Card 25: holistic `run` block carries the metrics through every branch

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `run`'s holistic block, capture the first call's metrics from `res`, fold the `NEED_CONTEXT`
  retry's `retry_res` in with `sum_optional`, and add the three keys to every `reviews.append(...)`
  dict in that block: the initial `except LLMError` entry (duration from the exception, others
  `None`), the retry `except LLMError` entry (first call's values summed with the exception's
  duration), and each of the three success entries (the post-retry `finalize_scope` entry, the
  no-resolvable-paths entry, and the plain non-`NEED_CONTEXT` entry), passing the running totals into
  each of those three `finalize_scope` calls.
  The block's trailing `except ReviewError` handler (which writes a raw file via
  `write_review_file`) applies `apply_cost_metadata` to `raw` before that write and carries the
  three keys in its `ERROR` entry.
  The `rounds == 0`/skip entries and `_scan_approved_batches`' carried-forward entries are left
  alone — a carried-forward batch's cost was already recorded in the round that produced it, and
  re-synthesising a value for it here would double-count.
- **Commit:** `feat(review): report holistic plan review cost through every branch`

### Card 26: flow-test coverage across all three regions

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add cases.
  (1) Holistic happy path: `reviews[0]` carries the three keys and the written file's header has a
  `duration_s:` line.
  (2) Holistic summation across the `NEED_CONTEXT` retry, including the `None`-absorbing case where
  the retry supplies no `tool_calls`/`cost_usd`.
  (3) Holistic call-failure and parse-failure ERROR entries carry the metrics, with the
  parse-failure case also asserting the injected `duration_s:` line in the raw file.
  (4) Per-batch path: a `_review_one_batch` round's entry carries the three keys.
  (5) Per-batch outer `ReviewError` path: assert the entry still has `"file": None` and carries the
  metrics envelope-only — this case is the regression guard for the preserved-inconsistency Shared
  Decision, so it must assert no review file was written for that round.
  (6) Per-batch pre-call `ReviewError`: trip the `round_n > max_rounds` guard (which raises before
  any reviewer call) and assert the returned entry is the normal `ERROR` shape with the three metrics
  `None` — the regression guard for card 23's initialisation requirement, which would otherwise
  surface as an `UnboundLocalError`.
- **Commit:** `test(review): cover plan review cost metadata across batch and holistic paths`

## Batch Tests

`verify:` runs `test-review-plan-flow.py`, which owns `_review_plan`'s coverage across the per-batch,
holistic, and finalize regions, and is the only test file this batch edits. Card 26's case (5) is
the specific guard against a well-meaning implementer "fixing" the file-less `ReviewError` site.
