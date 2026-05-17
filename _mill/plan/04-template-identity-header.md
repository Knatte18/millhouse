# Batch: template-identity-header

```yaml
task: '63 (A) — Reviewer tool-sandbox: git snapshot guard + fix --allowedTools'
batch: template-identity-header
number: 4
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Prepend a verbatim "you are a READ-ONLY reviewer" identity paragraph to each of the five review prompt templates. The text is the proposal's recommended hardening: defense-in-depth alongside the snapshot guard (batch 1+2) and the corrected `--disallowedTools` argv (batch 3). The identity paragraph becomes the new FIRST paragraph of each template, separated from the existing first sentence (`"You are an independent ... reviewer for **<TASK_TITLE>**."`) by a blank line.

No render-pipeline change: the text contains no `<TOKEN>` placeholders, so `render_prompt` passes it through unchanged. No new template token, no `_review_common.render_prompt` modification.

Independent of batches 1, 2, 3 — no shared files, no shared symbols. `verify: null` because templates have no runnable surface; the implicit verification is that existing review-template-rendering tests in `test-review-common.py` still pass (they render the templates and would fail at first-paragraph mismatch only if the test asserted exact contents, which it does not).

## Cards

### Card 8: Prepend READ-ONLY identity header to five review templates

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-discussion.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. For each of the five templates listed in Edits:, prepend the following exact block as the new first paragraph, followed by a single blank line:

     ```text
     **You are a READ-ONLY reviewer. You MUST NOT call Edit, Write, Bash, or any
     tool that modifies files or runs commands. You MUST NOT make git commits.
     Your sole output is the review file in the format below. If you find issues,
     REPORT them — do NOT fix them.**
     ```

     The block uses an em-dash (`—`) in "REPORT them — do NOT fix them". This is markdown prompt content (delivered to the LLM), NOT a `print()` / log string, so the ASCII rule does not apply. Use the actual em-dash character.

  2. The exact placement: line 1 of each file becomes the first line of the identity block (`**You are a READ-ONLY reviewer...`). Lines 2-4 of each file become the continuation lines. Line 5 is a blank line. Line 6 onward is the prior content of the file (the existing `"You are an independent ... reviewer for **<TASK_TITLE>**."` first sentence and everything below it).

  3. Each template file's existing content is preserved verbatim — no deletion, no reordering, no edit beyond the prepend. The `<TOOL_RULE>` block, `<ARTEFACT_SECTION>`, `## Criteria`, `## Source-grounding rule`, and `## Output` sections remain untouched and in the same relative order.

  4. After the edit, the five files share an identical first-five-lines block. **Verification gate before commit:** run `head -5 plugins/mill/templates/review-plan-batch.md plugins/mill/templates/review-plan-holistic.md plugins/mill/templates/review-code-batch.md plugins/mill/templates/review-code-holistic.md plugins/mill/templates/review-discussion.md` and visually confirm that the first five lines are byte-identical across all five files (only the file-header banner each `head` invocation emits between files should differ). If any file diverges, the prepend was mis-applied — fix and re-run. Do not commit until this gate passes.

  5. The 5-file pattern is intentional: the proposal calls for ALL review templates to carry the same identity header, including templates that fire from `bulk` and `tool-use` mode reviewers and the discussion reviewer. Skipping any template re-opens the soft-constraint failure mode in that scope.

- **Commit:** `feat(templates): prepend READ-ONLY identity header to all review-*.md`

## Batch Tests

`verify: null`

The templates have no runnable verification surface. The implicit verification is two-step:

1. The existing `test-review-common.py` imports `_review_common` and may exercise `render_prompt` — if any of its templates fail to render or render with unexpected token leakage, that test would surface it. Running it after this batch confirms no breakage.
2. After batches 1+2+3 are merged into mill-go's end-to-end review-pass smoke (the integration tests, run separately from unit tests), a clean APPROVE round demonstrates that the new first paragraph does not regress existing review prompt behaviour or trigger NEED_CONTEXT loops.

Neither check is invoked by this batch's `verify:` because they belong to the global / integration suite, not a template-edit batch. mill-go's batch-level `verify: null` is appropriate per the plan-batch template's stated convention ("If `verify: null`, state why").
