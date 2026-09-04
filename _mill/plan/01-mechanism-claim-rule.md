# Batch: mechanism-claim-rule

```yaml
task: 'millpy-review-plan: verdict/envelope disagreement and reviewer_model mis-recording'
batch: 'mechanism-claim-rule'
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-templates.py
depends-on: []
```

## Batch Scope

This is the only batch in the plan. It adds the mechanism-claim source-verification rule (fixing #949) to both plan-review reviewer prompt templates, and covers it with a template-content assertion test. No external interface changes -- these are prompt/test files only, nothing else in the repo depends on their content at import time.

## Cards

### Card 1: Add mechanism-claim source-verification rule to plan-review templates

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/unit_tests/test-review-templates.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `review-plan-holistic.md`, insert the new paragraph below at the end of the `## Source-grounding rule` section -- directly after the existing sentence that ends "Fabricating file contents — or inferring them from filename / position alone — is a worse failure than halting honestly." and immediately before the `## Criteria (apply to the plan as a whole)` heading. Reproduce this block byte-for-byte, at column 0 (no extra indentation), as a new paragraph (blank line before it, blank line after it, before the next heading):

  ```
  **Mechanism claims must be source-verified.**
  A finding that rests on a claim about how the target repo's production code behaves — which branch executes, what a predicate selects, which value survives a mutation — must name the file and the function/method/construct it was verified against, in the finding's own text.
  Do not assert a mechanism claim from memory, naming convention, or plausible-sounding inference.
  If you cannot verify the claim against source in your context (not bulked into this prompt, and not Read-able in bulk mode), do not assert it: downgrade the finding to a question under `## Missing context`, or drop it — never write an unverified mechanism claim into a BLOCKING or NIT finding as fact.
  Tool-use-mode reviewers may Read/Grep the target repo's source directly to verify a mechanism claim even when the relevant file was not bulked into this prompt; bulk-mode reviewers have no such option and must rely on this rule alone.
  ```

  In `review-plan-batch.md`, insert the identical block (byte-for-byte the same five lines) at the same relative position: end of its own `## Source-grounding rule` section (which is byte-identical to the holistic template's today), directly after the same closing "Fabricating file contents..." sentence, immediately before the `## Criteria (apply briefly)` heading.

  In `plugins/mill/unit_tests/test-review-templates.py`, add a new test function `test_plan_mechanism_claim_rule_present`, placed immediately after `test_plan_criteria_bullets_present` (defined at line 126). Model it directly on `test_plan_criteria_bullets_present`'s own body (loop over `["review-plan-holistic", "review-plan-batch"]`, call `_read_template_source(name)`, assert a fixed phrase is `in source`): assert the literal substring `"Mechanism claims must be source-verified."` is present in both templates' raw source, with a failure message naming the missing template (e.g. `f"{name} missing the mechanism-claim-verification rule"`). End the function with `print("PASS test_plan_mechanism_claim_rule_present")`, matching every other test function's own closing line in this file.

  Register the new function in `main()`'s `tests` list (defined at line 198), inserting `test_plan_mechanism_claim_rule_present,` immediately after the existing `test_plan_criteria_bullets_present,` entry (line 202) and before `test_no_output_file_token,`.
- **Commit:** `docs(review-plan): require source-verified mechanism claims in plan-review templates (#949)`

## Batch Tests

`verify:` runs `test-review-templates.py` directly (not through `run-all.py`) since this batch touches only that one test file plus the two templates it reads -- no other test file imports from `plugins/mill/templates/`. The new `test_plan_mechanism_claim_rule_present` function is the only new coverage; every existing test in the file (`test_all_templates_render`, `test_deleted_prose_stays_deleted`, `test_kept_prose_stays_kept`, `test_plan_criteria_bullets_present`, `test_no_output_file_token`, `test_unified_vocabulary_and_class_taxonomy`) must continue to pass unchanged, confirming the new paragraph didn't break template rendering or any other content assertion.
