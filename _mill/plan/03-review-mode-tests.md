# Batch: review-mode-tests

```yaml
task: "Track _mill/briefs/ instead of gitignoring them"
batch: review-mode-tests
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
depends-on: []
```

## Batch Scope

Add regression coverage for the two halves of the bulking decision: a tool-use reviewer
must NOT inline reviewed source into its prompt (the property that makes briefs small
enough to track), and the demoted bulk path must still inline source when explicitly
selected (proving the `_bulk` opt-in survives). This is its own batch because the tests
exercise the review prompt-assembly code (`_review_code.py`, `_review_common.py`), whose
combined size dominates the context budget — isolating them keeps every batch within the
context-token limit. The tests use inline reviewer specs, so the batch is independent of
the catalogue rename in batch 1.

## Cards

### Card 9: Assert tool-use omits bulked bodies and bulk remains reachable

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewer_single.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add two tests to `test-review-common.py`. (1) A no-bulked-bodies test:
  build the review artefact/prompt section for a reviewer spec with `tooluse: true` over a
  fixture source file containing a unique sentinel line, and assert the rendered prompt
  contains the tool-use `<TOOL_RULE>` block (granting Read/Grep/Glob) and the file's
  *path* but NOT the sentinel line (no inlined body). Drive it through the same
  tool-use-mode assembly the prepare stage uses — `_review_code._build_artefact_section`
  with mode `"tool-use"` and `_review_common.build_tool_rule("tool-use")`. (2) A
  bulk-still-reachable test: for a spec with `tooluse: false`, assert the bulk assembly
  inlines the body — the sentinel line IS present — confirming `_read_for_bulk` /
  `bulk_files` remain reachable. Construct reviewer specs inline (do not import the
  production catalogue or `make_minimal_registry`). Use `tempfile` fixtures; no real
  git/LLM. Match the file's existing test signature/return convention.
- **Commit:** `test(review): assert tool-use omits bulked bodies and bulk stays reachable`

## Batch Tests

`verify` runs `test-review-common.py` via `run-all.py --only`, which now includes the two
new tests plus the file's existing review-common coverage. Scope is the single file this
batch edits, per the per-batch scoping rule. The new tests are pure unit tests over the
prompt-assembly helpers — no real LLM call, no network — so they run in the same fast
suite as the rest of `test-review-common.py`.
