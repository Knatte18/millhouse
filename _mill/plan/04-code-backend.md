# Batch: code-backend

```yaml
task: "Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch"
batch: "code-backend"
number: 4
cards: 3
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-nit-gate.py"
depends-on: [1]
```

## Batch Scope

Wires the code-review backend onto batch 1's engine and confirms the one consumer that needs no code change at all.
`_review_code.finalize` already receives `cfg`, so the ceiling wiring is a two-line change plus the `findings` passthrough; the code stage's default `blocking_classes` is the full class set, so no finding is demoted there today, which makes the demotion-free path worth asserting explicitly rather than assuming.
`_nit_gate.find_unfixed_nit_scopes` delegates its counting to `parse_blocking_count`, so batch 1's widened regex already makes it match `### [NIT:consistency]` -- this batch adds the test that proves it and deliberately edits no `_nit_gate.py` source.
It runs in parallel with batches 2 and 3, which touch disjoint files.

## Cards

### Card 17: Code finalize resolves and applies the stage ceiling

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `resolve_blocking_classes` to `_review_code.py`'s `from _review_common import (...)` block.
  In `finalize`, compute `blocking_classes = resolve_blocking_classes(cfg, "code", scope)` after the `_splice_rename_nit_findings` call and pass it as `blocking_classes=blocking_classes` to the `finalize_scope` call.
  Resolving after the splice is required, not cosmetic: `_splice_rename_nit_findings` injects advisory `NIT` findings into `raw_text`, and those injected findings must be visible to the single `extract_findings` pass inside `finalize_scope`, which only sees the text passed to it.
  On the success path, set `findings=review_entry["findings"]` on the returned `ReviewResult` and add `"findings": review_entry["findings"]` to the dict inside its `reviews=[...]` list.
  On the `ReviewError` path, add `"findings": []` to its `reviews[0]` dict.
  Add `"findings": []` to every other hand-built review-entry dict in `_review_code.py` that currently sets `blocking_count=0`, so the key is present on every path.
  Remove the now-unused `parse_blocking_count` name from the import block only if nothing else in the file references it.
- **Commit:** `feat(review): thread blocking_classes and findings through code finalize`

### Card 18: Code flow tests for classed findings

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Update every fixture review text and expected-value assertion affected by `finalize_scope` recomputing the verdict from the post-ceiling blocking count and by the new `findings` key on `_review_code.finalize`'s envelope.
  Add one test asserting that at the code stage every one of `### [BLOCKING:design]`, `### [BLOCKING:scope]`, `### [BLOCKING:decision]`, and `### [BLOCKING:consistency]` survives as `BLOCKING`, that `blocking_count == 4`, and that no entry in `findings` carries `demoted: true` -- the code stage's default `blocking_classes` is the full class set, so it is the one stage where the ceiling is a no-op.
  Add one test asserting the advisory NITs injected by `_splice_rename_nit_findings` appear in the `findings` list of the resulting envelope, confirming the splice happens before extraction.
- **Commit:** `test(review): cover code-stage classed findings and splice ordering`

### Card 19: Nit gate matches classed NIT headings

- **Context:**
  - `plugins/mill/scripts/_nit_gate.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-nit-gate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a test asserting `find_unfixed_nit_scopes` reports a scope whose final code-review file contains only `### [NIT:consistency]` headings, proving batch 1's widened `parse_blocking_count` pattern reaches this call site with no change to `_nit_gate.py` itself.
  Add a second test asserting a file containing a demoted heading -- `### [NIT:scope]` immediately followed by a `**Demoted-from:** BLOCKING` line -- is counted exactly once, so the inserted field line cannot inflate the nit count.
  Do not edit `plugins/mill/scripts/_nit_gate.py`; it delegates all counting to `parse_blocking_count`, and adding ceiling logic there would violate the `ceiling-applied-once-at-write-time` Shared Decision.
- **Commit:** `test(nit-gate): assert classed and demoted NIT headings are counted`

## Batch Tests

`verify:` runs `test-review-code-flow.py` (the code backend's envelope and verdict contract) and `test-nit-gate.py` (the one downstream consumer of the widened `parse_blocking_count` regex that this batch is responsible for proving).
Both files are edited by this batch, so the gate is exactly its own surface.
Card 19's second test is the regression guard for the demotion rewrite's inserted `**Demoted-from:**` line, which is written by batch 1 but only observable at a re-read site like this one.
