---
kind: plan-batch
batch-name: templates
batch-depends: []
approved: false
---

# Batch 03: Templates — 5 prompts + 1 schema

## Batch-Specific Context

Templates are Markdown files with `<TOKEN>` placeholders (uppercase per
`_render.py` grammar). Drafted from v1's prompts in
`C:/Code/millhouse-legacy/plugins/mill/doc/prompts/`, which "funka ganske bra."
Each template is reviewed by the user before the batch is approved.

v1 mapping:
- `review-discussion.md` → lift from `doc/prompts/discussion-review.md` (tool-use variant).
- `review-plan-batch.md` → lift from `doc/prompts/plan-review-bulk.md` (per-batch mode).
- `review-plan-holistic.md` → lift from `doc/prompts/plan-review.md` (holistic, but bulk-mode; drop the tool-use instructions).
- `review-code-single.md` → lift from `doc/prompts/code-review.md` (bulk variant, single file focus).
- `review-code-multi.md` → lift from `doc/prompts/code-review-bulk.md` (multi-file cross-cutting).

No Python dependency. Batch runs in parallel with Batches 01 and 02.

## Batch Files

- templates/review-discussion.md
- templates/review-plan-batch.md
- templates/review-plan-holistic.md
- templates/review-code-single.md
- templates/review-code-multi.md
- templates/review-output.schema.md

## Steps

### Step 4: Create `review-discussion.md` (tool-use, reviewer reads files itself)

- **Creates:** `templates/review-discussion.md`
- **Modifies:** none
- **Reads:** `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/discussion-review.md`
- **Requirements:**
  - Template instructs the reviewer to read the discussion file at
    `<ARTEFACT_PATH>`, follow any references, and produce a review.
  - The reviewer is told to **return** the full review output as its final
    response (NOT use the `Write` tool to create files). The backend writes.
  - Placeholders used: `<TASK_TITLE>`, `<ARTEFACT_PATH>`, `<CONSTRAINTS>`,
    `<ROUND>`, `<REVIEWER_MODEL>`.
  - Output format specified in prompt: YAML frontmatter with `verdict:`,
    `reviewer_model:`, `reviewed_file:`, `date:` — matching `review-output.schema.md`.
  - CRITICAL instruction: "Do NOT use the Write tool to create files. Return
    your review as text."
  - CRITICAL instruction: "Do NOT read any files in the `reviews/`
    directory — evaluate the discussion fresh each round."
- **Explore:**
  - `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/discussion-review.md` — lift wording and structure; drop legacy path hardcodes; adapt CRITICAL banners.
- **depends-on:** []
- **Test approach:** documentation review. Confirm tokens match the set the
  backend renders with (`_review_discussion.py` in Batch 04 will pass these).
- **Key test scenarios:**
  - Happy: `render_prompt("review-discussion", task_title="X", artefact_path="/tmp/d.md", constraints="", round=1, reviewer_model="sonnetmax_tool")` renders without `KeyError`.
- **Commit:** `feat(review): add review-discussion.md template (tool-use)`

### Step 5: Create plan templates (batch + holistic, both bulk)

- **Creates:** `templates/review-plan-batch.md`, `templates/review-plan-holistic.md`
- **Modifies:** none
- **Reads:** `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/plan-review-bulk.md`, `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/plan-review.md`
- **Requirements:**
  - `review-plan-batch.md`: evaluates a single batch given the batch file
    plus the plan overview plus any `Reads:`/`Modifies:` files, all
    pre-bulked into `<ARTEFACT_CONTENT>`.
    - Placeholders: `<TASK_TITLE>`, `<BATCH_NAME>`, `<ARTEFACT_CONTENT>`,
      `<CONSTRAINTS>`, `<ROUND>`, `<REVIEWER_MODEL>`.
    - Explicit instruction: bulk mode — do not use tools, answer from
      provided content.
  - `review-plan-holistic.md`: evaluates whole plan (overview + all batches
    + all referenced files) bulked into `<ARTEFACT_CONTENT>`.
    - Placeholders: `<TASK_TITLE>`, `<ARTEFACT_CONTENT>`, `<CONSTRAINTS>`,
      `<ROUND>`, `<REVIEWER_MODEL>`.
  - Both instruct the reviewer to return the review as text (no Write tool).
  - Both specify the output format matching `review-output.schema.md`.
- **Explore:**
  - `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/plan-review-bulk.md` — per-batch bulk evaluation criteria.
  - `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/plan-review.md` — holistic evaluation criteria; adapt to bulk mode.
- **depends-on:** []
- **Test approach:** documentation review.
- **Key test scenarios:**
  - Happy: both templates render cleanly with the token set the plan backend will pass.
- **Commit:** `feat(review): add plan-batch and plan-holistic templates`

### Step 6: Create code templates (single + multi, both bulk)

- **Creates:** `templates/review-code-single.md`, `templates/review-code-multi.md`
- **Modifies:** none
- **Reads:** `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/code-review.md`, `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/code-review-bulk.md`
- **Requirements:**
  - `review-code-single.md`: review of a single-file diff. Prompt wording
    emphasises that one file is the primary scope.
    - Placeholders: `<TASK_TITLE>`, `<DIFF>`, `<PLAN_CONTENT>`,
      `<ARTEFACT_CONTENT>`, `<CONSTRAINTS>`, `<ROUND>`, `<REVIEWER_MODEL>`.
  - `review-code-multi.md`: review of multi-file diff. Prompt wording
    emphasises cross-file consistency, API contracts, shared patterns.
    - Same placeholder set.
  - Both: bulk mode instructions; return text; no Write tool.
- **Explore:**
  - `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/code-review.md` — criteria wording for code review.
  - `C:/Code/millhouse-legacy/plugins/mill/doc/prompts/code-review-bulk.md` — multi-file bulk wording.
- **depends-on:** []
- **Test approach:** documentation review.
- **Key test scenarios:**
  - Happy: both render cleanly with the code backend's token set.
- **Commit:** `feat(review): add code-single and code-multi templates`

### Step 7: Create `review-output.schema.md`

- **Creates:** `templates/review-output.schema.md`
- **Modifies:** none
- **Reads:** none
- **Requirements:**
  - Document the canonical review-output format:
    ```markdown
    ---
    verdict: APPROVE | REQUEST_CHANGES
    reviewer_model: <reviewer name from config, e.g. sonnetmax>
    reviewed_file: <path to the artefact that was reviewed>
    date: <UTC YYYY-MM-DD>
    ---

    # Review: <title>

    ## Findings

    ### [BLOCKING|NIT] <title>
    **Section:** ...
    **Issue:** ...
    **Suggested fix:** ...

    ## Verdict

    APPROVE | REQUEST_CHANGES
    <one-sentence summary>
    ```
  - Required frontmatter fields: `verdict`, `reviewer_model`, `reviewed_file`, `date`.
  - Required sections: `## Findings`, `## Verdict`.
  - Finding severity is `BLOCKING` or `NIT`.
  - `parse_verdict()` in `_review_common.py` validates against this schema
    (specifically the `verdict:` frontmatter field).
- **Explore:**
  - (The discussion's "review-output format" section carries the shape; lift it into this schema file.)
- **depends-on:** []
- **Test approach:** documentation review.
- **Key test scenarios:**
  - Happy: a valid review output per this schema parses correctly via `parse_verdict()`.
  - Error: missing `verdict:` frontmatter → `parse_verdict` raises ReviewError.
- **Commit:** `feat(review): add review-output.schema.md`
