# Batch: discussion-backend

```yaml
task: "Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch"
batch: "discussion-backend"
number: 2
cards: 4
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-discussion-flow.py test-review-cli-error-envelope.py test-bg-json-contract.py test-bg-liveness.py"
depends-on: [1]
```

## Batch Scope

Wires the discussion-review backend onto batch 1's engine: `_review_discussion.finalize` resolves the stage's `blocking_classes` from `cfg` and passes them to `finalize_scope`, and carries the resulting `findings` list into the `ReviewResult` envelope both per-scope and at the top level.
It also fixes the one shared CLI error envelope so an ERROR-shaped result carries `findings: []` alongside its hardcoded `blocking_count: 0`, and retires the last `GAPS_FOUND` / `[GAP]` / `[NOTE]` occurrences from the discussion flow test, the two bg-log tests, the discussion integration test, and the reviewer benchmark harness -- the last of which is a live-dispatch script, not a fixture, and would silently report zero discussion findings forever once batch 5 lands.
This batch consumes only the module-level names batch 1 exports; it adds no ceiling logic of its own.
It runs in parallel with batches 3 and 4, which touch disjoint files.

## Cards

### Card 9: Discussion finalize resolves and applies the stage ceiling

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_discussion.py`, add `resolve_blocking_classes` to the existing `from _review_common import (...)` block.
  In `finalize`, compute `blocking_classes = resolve_blocking_classes(cfg, "discussion", "holistic")` and pass it as the keyword argument `blocking_classes=blocking_classes` to the `finalize_scope` call.
  On the success path, set `findings=review_entry["findings"]` on the returned `ReviewResult` and add `"findings": review_entry["findings"]` to the single dict inside its `reviews=[...]` list.
  On the `ReviewError` path, leave the ERROR-shaped `ReviewResult` as it is but add `"findings": []` to its `reviews[0]` dict, and do the same for every other hand-built dict inside a `reviews=[...]` list elsewhere in `_review_discussion.py` -- including the skipped-scope entry -- so every envelope carries the per-scope key with a consistent shape.
  The enclosing `ReviewResult(...)` calls need no explicit `findings` argument: the dataclass field defaults to an empty list.
  Remove the now-unused `parse_blocking_count` name from `_review_discussion.py`'s import block only if nothing else in the file references it.
- **Commit:** `feat(review): thread blocking_classes and findings through discussion finalize`

### Card 10: ERROR envelope carries an empty findings list

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `print_error_envelope`, add `"findings": []` to the envelope dict immediately after `"blocking_count": 0`, and add `"findings": []` to the single dict inside its `reviews` list.
  Update `print_error_envelope`'s docstring to state that the envelope mirrors `ReviewResult.to_dict()`'s key set with zeroed counts and an empty findings list.
  In `test-review-cli-error-envelope.py`, extend the existing key-set assertions to require `findings` at both the top level and inside `reviews[0]`, and assert both are empty lists.
- **Commit:** `feat(review): add findings to the shared ERROR envelope`

### Card 11: Discussion flow test on the unified vocabulary

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace every `### [GAP]` heading in the fixture review texts with `### [BLOCKING:design]`, every `### [NOTE]` heading with `### [NIT:design]`, and every `verdict: GAPS_FOUND` fixture line with `verdict: REQUEST_CHANGES`, then update the assertions those fixtures feed so the expected verdict is `REQUEST_CHANGES` rather than `GAPS_FOUND`.
  Use `design` as the class in migrated blocking fixtures so they survive the discussion stage's `blocking_classes` ceiling and keep asserting the same blocking counts as before -- a fixture migrated to any other class would be demoted and would silently change the test's meaning.
  Add one new test asserting the envelope from `_review_discussion.finalize` carries a `findings` list whose length equals `blocking_count + nit_count`, present both at the top level and inside `reviews[0]`.
  Add one new test asserting that a fixture emitting only `### [BLOCKING:scope]` findings yields verdict `APPROVE`, `blocking_count == 0`, `nit_count` equal to the number of such findings, and a `findings` list whose entries all carry `demoted: true`.
- **Commit:** `test(review): migrate discussion flow tests to unified vocabulary`

### Card 12: Retire the old vocabulary from remaining fixtures and the benchmark

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-bg-json-contract.py`
  - `plugins/mill/unit_tests/test-bg-liveness.py`
  - `plugins/mill/integration_tests/test-review-discussion.py`
  - `plugins/mill/integration_tests/bench-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-bg-json-contract.py` and `test-bg-liveness.py`, change the literal `"verdict": "GAPS_FOUND"` inside the synthetic bg-log JSON lines to `"verdict": "REQUEST_CHANGES"`.
  These fixtures exercise JSON-line extraction from a bg log and treat the verdict as an opaque string, so the change is a vocabulary-hygiene rename with no assertion impact; verify no assertion in either file matches on the literal `GAPS_FOUND` before changing it, and update it too if one does.
  In `plugins/mill/integration_tests/test-review-discussion.py`, change the verdict membership check from `("APPROVE", "GAPS_FOUND")` to `("APPROVE", "REQUEST_CHANGES")`.
  Add no new integration assertions -- live reviewer output format is explicitly out of test scope.
  In `plugins/mill/integration_tests/bench-reviewers.py`, the `findings` computation branches on `if review_type == "discussion":` to count `parse_blocking_count(text, severity="GAP")` plus `severity="NOTE"`, while its `else:` branch already counts `severity="BLOCKING"` plus `severity="NIT"`.
  Under the unified vocabulary the two branches become identical, so delete the `if review_type == "discussion":` branch and compute `findings` unconditionally from `severity="BLOCKING"` plus `severity="NIT"`.
  This is required, not cosmetic: once batch 5 card 20 stops the discussion template emitting `[GAP]` / `[NOTE]`, this branch silently and permanently reports `0` discussion findings, and nothing else in the file would fail to signal it.
  Leave that file's `parse_verdict` call and its `format_ok` checks untouched -- `parse_verdict` still accepts historical values and the format checks are vocabulary-independent.
- **Commit:** `test(review): retire GAP/NOTE/GAPS_FOUND from bg, integration, and bench harnesses`

## Batch Tests

`verify:` runs the four unit-test files this batch edits or whose subject it changes: `test-review-discussion-flow.py` (the discussion backend's envelope contract), `test-review-cli-error-envelope.py` (the shared ERROR envelope), and `test-bg-json-contract.py` plus `test-bg-liveness.py` (the two files carrying migrated fixture strings).
`plugins/mill/integration_tests/test-review-discussion.py` and `plugins/mill/integration_tests/bench-reviewers.py` are edited but deliberately excluded from `verify:` -- both invoke a real reviewer and are never run as a per-round gate.
The bench harness change in card 12 is a two-branch collapse with no assertion surface of its own; it is verified by review against the `else:` branch it merges into.
