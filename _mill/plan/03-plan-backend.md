# Batch: plan-backend

```yaml
task: "Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch"
batch: "plan-backend"
number: 3
cards: 4
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py"
depends-on: [1]
```

## Batch Scope

Wires the plan-review backend onto batch 1's engine.
Plan review is the only backend with two scopes, four `finalize_scope` call sites, a batch worker that does not receive `cfg`, an aggregation step over `reviews[]`, and two historical re-read sites that must stay ceiling-free.
This batch threads a resolved `blocking_classes` set into all four write-time call sites, concatenates the `findings` lists at the aggregation site, adds `findings` to the hand-built envelope in `millpy-review-plan.py`, and leaves the two re-read sites on the widened-regex-only path required by the `ceiling-applied-once-at-write-time` Shared Decision.
It runs in parallel with batches 2 and 4, which touch disjoint files.

## Cards

### Card 13: Thread blocking_classes into the batch worker

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `resolve_blocking_classes` to `_review_plan.py`'s `from _review_common import (...)` block.
  Add a keyword-only parameter `blocking_classes: frozenset[str]` to `_review_one_batch`, documented in its docstring as the pre-resolved per-scope ceiling supplied by the caller because this worker does not receive `cfg`.
  Pass it through to the `finalize_scope(reviews_dir, "plan", round_n, raw, scope=batch_path.stem)` call as `blocking_classes=blocking_classes`, and add `"findings": review_entry["findings"]` to the dict this function returns on the success path.
  On both of its ERROR-shaped return dicts -- the `LLMError` resume-retry failure and the outer `ReviewError` handler -- add `"findings": []`.
  At every call site of `_review_one_batch` inside `run`, pass `blocking_classes=resolve_blocking_classes(cfg, "plan", <that call site's batch scope value>)`.
- **Commit:** `feat(review): thread blocking_classes into the plan batch worker`

### Card 14: Plan finalize and run-level ceiling wiring

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_plan.finalize`, compute `blocking_classes = resolve_blocking_classes(cfg, "plan", scope)` and pass it as `blocking_classes=blocking_classes` to its `finalize_scope` call; add `"findings": review_entry["findings"]` to the success-path return dict and `"findings": []` to the `ReviewError`-path return dict.
  In `run`, do the same for each of the three remaining `finalize_scope(reviews_dir, "plan", round_n, raw, scope="holistic")` call sites, using `resolve_blocking_classes(cfg, "plan", "holistic")` for all three, and add `"findings": review_entry["findings"]` to each of the corresponding review-entry dicts built from those calls.
  Add `"findings": []` to every hand-built zero-count review-entry dict in `run` that currently sets `"blocking_count": 0` and `"nit_count": 0`, so the key is present on every entry regardless of path.
  Do not touch the `parse_blocking_count` / `count_unrecognized_severity_findings` calls in `_scan_approved_batches` or in `run`'s crash-recovery re-read block -- those are historical re-read sites and must stay ceiling-free per the `ceiling-applied-once-at-write-time` Shared Decision; add a one-line comment at each stating that the file being read was already written in its demoted form.
- **Commit:** `feat(review): apply blocking-class ceiling at plan finalize and run sites`

### Card 15: Aggregate findings across sub-reviews

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_plan.run`, next to the existing `aggregate_blocking = sum(...)` and `aggregate_nit = sum(...)` lines, add `aggregate_findings = [f for r in reviews for f in r.get("findings", [])]` and pass it as `findings=aggregate_findings` to the `ReviewResult(...)` constructor, so the top-level list is the concatenation of the per-scope lists exactly as the scalars are their summation.
  In `millpy-review-plan.py`, the hand-built `result_dict` for the finalize stage currently mirrors `ReviewResult.to_dict()` by hand: add `"findings": review_entry["findings"]` to it, positioned after `"nit_count"` and before `"reviews"` so the key order matches `to_dict()`.
- **Commit:** `feat(review): aggregate findings across plan sub-reviews`

### Card 16: Plan flow tests for the ceiling and envelope

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Update every fixture review text and every expected-value assertion affected by `finalize_scope` recomputing the verdict from the post-ceiling blocking count, and by the new `findings` key appearing in `_review_plan.finalize`'s and `_review_one_batch`'s returned dicts.
  Add one test asserting the top-level `findings` list on the `ReviewResult` from `run` equals the concatenation of the per-scope `findings` lists in `reviews[]`, and that `blocking_count` and `nit_count` remain consistent with it.
  Add one test asserting a `### [BLOCKING:consistency]` finding at the plan stage is demoted to `NIT` -- `consistency` is outside `plan-review`'s default `blocking_classes` -- while a `### [BLOCKING:scope]` finding at the same stage survives as `BLOCKING`, which is the distinction between the plan and discussion stages.
  Add one test asserting `_scan_approved_batches` returns the same counts for a review file already containing a demoted `### [NIT:scope]` heading with a `**Demoted-from:** BLOCKING` line as it does for a plain `### [NIT]` heading, confirming the re-read site applies no second ceiling.
- **Commit:** `test(review): cover plan-stage ceiling, aggregation, and re-read sites`

## Batch Tests

`verify:` runs `test-review-plan-flow.py`, the file that exercises `_review_plan.prepare`, `finalize`, `run`, and `_scan_approved_batches` end to end with in-memory fixtures, and the only unit-test file this batch edits.
`test-review-plan-finalize-round.py` is deliberately excluded: this batch does not touch round discovery or the finalize-round path it covers, and pulling it in would widen the gate beyond what the batch changes.
`millpy-review-plan.py`'s hand-built envelope has no dedicated unit test today; card 15 keeps its key set identical to `ReviewResult.to_dict()`, which `test-review-plan-flow.py` asserts on the `run` path.
