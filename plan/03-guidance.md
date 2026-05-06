# Batch: guidance

```yaml
task: 10 (B) — Plan-template format-forbedringer
batch: guidance
cards: 3
verify: null
depends-on: [field-rename]
```

## Batch Scope

This batch adds stable-identifier and allowlist guidance for mill-plan. It strengthens three files: the `plan-batch.md` template (card 13), the plan-review templates (card 14), and the mill-plan SKILL.md (card 15). No code changes. Cards read files renamed in batch 02 and add new content only. `verify: null` because these are documentation/instruction changes with no runnable test surface.

## Cards

### Card 13: Strengthen `plan-batch.md` template — Requirements and Context guidance

- **Context:**
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  After batch 02, `plan-batch.md` has `Context:` and `Edits:` field labels. Add the following strengthened description to the `Requirements:` field bullet in the template body (the `### Card N:` example section):

  Change the current `- **Requirements:** what the card must achieve. Prose — exact assertions live in tests, not here.` to:

  `- **Requirements:** what the card must achieve. Use stable identifiers — name the specific function, class, or constant being added, changed, or deleted (e.g., "replace \`_load_config\` in \`mill-claim.py\` with \`from _config import load_config\`"). Never write vague prose ("refactor X") without the specific identifier. Exact assertion shapes live in tests, not here.`

  Add to the `Context:` field description bullet (which after batch 02 reads "every file the implementer reads but does not change..."):

  Append: `Context: is an allowlist — the implementer reads ONLY the files listed here. A file needed but not listed is a plan defect. Files listed in Edits: are implicitly read — do not repeat them in Context:.`

  So the full `Context:` description becomes: `- **Context:** every file the implementer reads but does not change. Non-empty. One backtick-wrapped path per indented bullet. Context: is an allowlist — the implementer reads ONLY the files listed here. A file needed but not listed is a plan defect. Files listed in Edits: are implicitly read — do not repeat them in Context:.`

- **Commit:** `docs(plan-batch): strengthen Context: allowlist and Requirements: stable-identifier guidance`

### Card 14: Add BLOCKING criteria to plan-review templates

- **Context:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In both `review-plan-batch.md` and `review-plan-holistic.md`, add two new criteria bullets to the `## Criteria` section:

  1. After the existing `**Reads field**` / `**Context field**` criterion (whichever name it has after batch 02), add:
     `- **Context completeness** — BLOCKING if \`Requirements:\` mentions a function, class, or constant from a file not listed in \`Context:\` or \`Edits:\`. The implementer may only read files in \`Context:\`; a missing entry means cold-start exploration.`

  2. After the `**Step granularity**` / `**Step granularity + atomicity**` criterion, add:
     `- **Requirements specificity** — BLOCKING if \`Requirements:\` uses vague prose ("refactor X", "update to use helper") without naming the specific function, class, or constant being changed. Stable identifiers are required.`

  In `review-plan-batch.md` only, these new criteria appear in the per-batch criteria section.
  In `review-plan-holistic.md` only, these new criteria appear in the full-plan criteria section.

- **Commit:** `docs(review-templates): add Context-completeness and Requirements-specificity BLOCKING criteria`

### Card 15: Strengthen `mill-plan/SKILL.md` — guidance section

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  After batch 02, mill-plan SKILL.md uses `Context:` and `Edits:` throughout. Make two targeted updates:

  1. In the Principles section, update the `**Card \`Context:\` must be comprehensive**` bullet (renamed from `Reads:` in batch 02) to read:
     `**Card \`Context:\` is an allowlist** — list every file the implementer needs to read WITHOUT editing. An empty or terse \`Context:\` is a review-blocker. The implementer reads ONLY listed files; any unlisted file is a plan defect. \`Edits:\` files are implicitly read — do not repeat them in \`Context:\`. All paths must be backtick-wrapped, one per bullet; no inline prose, no line-range suffixes.`

  2. Add a new bullet immediately after the `Context:` bullet:
     `**\`Requirements:\` must use stable identifiers** — name the specific function, class, or constant being changed. "Replace \`_load_config\` in \`mill-claim.py\` with \`from _config import load_config\`" is correct. "Refactor config loading to use the shared helper" is not — it forces the implementer to explore, defeating the cold-start guarantee.`

- **Commit:** `docs(mill-plan): add Context: allowlist rule and Requirements: stable-identifier mandate to Principles`

## Batch Tests

`verify: null` — all three cards add or strengthen documentation text. There is no runnable test surface for template and SKILL.md prose changes.
