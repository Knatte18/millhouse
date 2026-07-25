# Batch: severity-vocabulary-docs

```yaml
task: mill-plan review severity counting and validation schema gaps
batch: severity-vocabulary-docs
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Defense-in-depth for the severity-vocabulary blind spot (batches 1-2 are the primary, code-level fix): pins each reviewer prompt template's finding-severity vocabulary explicitly, and documents the fail-loud behavior in the canonical schema doc. Pure prompt/doc text — no Python, no test surface. Independent of batches 1-2 (no shared file, no import dependency), safe to implement in either order.

## Cards

### Card 7: Pin the closed severity vocabulary in all 5 reviewer prompt templates

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-discussion.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add an explicit, self-contained "severity vocabulary is closed" instruction to each template. Each template is rendered and sent standalone to a fresh reviewer session, so a holistic template's existing "Severity / verdict rules match review-plan-batch.md." cross-reference line does NOT constrain that session's own vocabulary (it never sees `review-plan-batch.md`'s content) — every template needs its own explicit paragraph, not just the batch templates that already spell out `BLOCKING`/`NIT` inline.
  - `review-plan-batch.md`: immediately after the existing "Severity:" bullet list (`BLOCKING`/`NIT`, currently the two bullets right before the "Verdict:" bullet list), add: `**Severity vocabulary is closed.** Use ONLY \`BLOCKING\` or \`NIT\` as the bracketed label in a finding heading -- never invent another word (e.g. \`MAJOR\`, \`MINOR\`, \`CRITICAL\`, \`MEDIUM\`, \`HIGH\`). If a finding's severity feels ambiguous, default to \`BLOCKING\`, never \`NIT\` -- an over-cautious BLOCKING can be pushed back on by the orchestrator; a mislabeled NIT (or an unrecognized label) can silently skip review entirely.`
  - `review-code-batch.md`: identical addition, same wording, placed the same way relative to its own "Severity:" bullet list (`BLOCKING`/`NIT`, lines 82-84).
  - `review-plan-holistic.md`: immediately after the existing "Severity / verdict rules match review-plan-batch.md." line, add the same "**Severity vocabulary is closed.**" paragraph as a standalone addition (do not rely on the cross-reference line alone -- add the full explicit sentence here too).
  - `review-code-holistic.md`: identical addition, same wording, placed the same way relative to its own "Severity / verdict rules match review-code-batch.md." line.
  - `review-discussion.md`: immediately after the existing "Severity rules (discussion-specific, per v1 convention):" bullet list (`GAP`/`NOTE`, currently lines 70-71), add: `**Severity vocabulary is closed.** Use ONLY \`GAP\` or \`NOTE\` as the bracketed label in a finding heading -- never invent another word. If a finding's severity feels ambiguous, default to \`GAP\`, never \`NOTE\`.`
- **Commit:** `docs(review): pin closed severity vocabulary in all reviewer prompt templates`

### Card 8: Document the fail-loud behavior in the canonical review-output schema

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Under the "### `## Findings`" heading's "**Finding severity:**" bullet list (currently `BLOCKING`/`NIT` with their approval-blocking behavior), add a new paragraph documenting: (1) the severity vocabulary is closed per review type -- `BLOCKING`/`NIT` for plan and code reviews, `GAP`/`NOTE` for discussion reviews; (2) reviewer templates instruct reviewers to never invent an unrecognized severity word and to default an ambiguous finding to the blocking-equivalent label; (3) as a code-level backstop, `_review_common.finalize_scope()` treats any finding -- whether expressed as a markdown `### [XXX]` heading OR as a `severity:` entry inside a fenced yaml `findings:` block -- whose severity label matches neither of a review type's two recognized labels as blocking-equivalent (fail-loud) rather than silently dropping it from both counters, via `count_unrecognized_severity_findings()` in `_review_common.py`. Cover both output formats explicitly in this paragraph (not just headings) so a reader following this doc understands the YAML-fallback case is covered too, matching the actual implementation from batch 1.
- **Commit:** `docs(review): document fail-loud severity counting in review-output schema`

## Batch Tests

`verify: null` -- this batch edits only markdown prompt templates and one markdown schema doc; there is no runnable surface (no Python code, no test file targets these templates' prose content). The behavior these docs describe is exercised by batch 1's unit tests against the actual `count_unrecognized_severity_findings()` implementation.
