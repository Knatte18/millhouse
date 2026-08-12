# Batch: renumber-and-siblings

```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'renumber-and-siblings'
number: 5
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-base-agent-only.py test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
depends-on: [4]
```

## Batch Scope

Closes the task: renumbers the `## Agent-mode dispatch` steps that batch 2 left starting at 2, sweeps every reference to them across the five affected files, corrects the two sibling SKILLs whose statements this task falsified, and regenerates the generated skills index under three explicit invariants.

This is the highest-risk batch in the task and the risk is entirely in the sweep.
`SKILL.md` carries four independent numbered-step namespaces whose surface text is identical, and only the first is being renumbered.
Cards 21 and 22 are therefore written as classify-then-edit passes, never as find/replace.

Batch-local decision: the sweep is driven by an enumeration taken from the post-batch-4 files themselves.
The per-token counts recorded in the discussion were measured before batches 2 through 4 deleted and relocated large amounts of text and are used only as a completeness cross-check.

## Cards

### Card 20: Renumber the Agent-mode dispatch steps

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `## Agent-mode dispatch` only, renumber the step list itself — not references to it, which cards 21 and 22 own.
  Batch 2 deleted step 1, so the list currently runs 2 through 7 with sub-labels `4(a)`, `4(b)`, `4(c)`, `6.5`, `6.5.1`, and `6.5.2`.
  Apply this mapping to the list markers and to the bold step titles: step 2 becomes 1, 3 becomes 2, 4 becomes 3, 5 becomes 4, 6 becomes 5, 7 becomes 6; `4(a)`/`4(b)`/`4(c)` become `3(a)`/`3(b)`/`3(c)`; `6.5` becomes `5.5`, and its two numbered sub-items keep their `1.`/`2.`/`3.` local numbering.
  Where the section's own prose refers to its own steps by number — for example step 3's "the value from step 2", step 4's "using the `agentId` retained per step 3", the Clean mid-work stop paragraph's "invoke the `--stage finalize` step (step 6)", step 5's "see step 5 below", step 6.5's "re-run `--stage finalize` (step 6)" and "branch in step 7" — apply the same mapping, because these are all first-namespace references and are inside the section being renumbered.
  Verify afterwards that the numbered list reads 1 through 6 with no gap and no duplicate.
- **Commit:** `docs(mill-go-base): renumber Agent-mode dispatch steps after the step-1 deletion`

### Card 21: Namespace-scoped reference sweep across SKILL.md

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Enumerate every occurrence of the pattern `step ` followed by a number anywhere in the file outside `## Agent-mode dispatch`, and classify each against the four numbered-step namespaces before changing anything.
  Only namespace 1 shifts:
  1. **Agent-mode dispatch steps** — apply card 20's mapping.
  2. **The batch loop's own section headings** `### 0.`, `### 0.5`, `### 0.55`, `### 0.6`, `### 1. Implement`, `### 2. Parse implementer report`, `### 2b. Cleanliness gate`, `### 3. Code Review loop` — untouched.
  3. **The Code Review loop's internal steps** 1, 1.5, 2, 3, 3.5, 4, 4.5, 5 — untouched.
  4. **References into another skill's namespace**, such as "mirrors mill-plan's existing step 4.5" — untouched.
  Known collision sites to re-read by hand after the sweep, each of which must still name the number it names today: the "see step 3 of 'Code Review loop'" reference (namespace 3), `### 0.6`'s reference to its insertion point in `### 1. Implement` (namespace 2), `### 2b`'s "Inline Python (in step 2b …)" (namespace 2), `### 3`'s "the cold-start fixer used in step 4 REQUEST_CHANGES" (namespace 3), the mill-plan step 4.5 reference (namespace 4), and `## Entry` step 3's "Handoff step 6" reference (a namespace of its own inside `handoff.md`, and one that card 18 already rewrote to name that file — leave its number alone).
  Both failure modes must be checked explicitly and neither is detectable by string matching, because the namespaces share identical surface text: an *under-shift* is a namespace-1 reference still naming its old number; an *over-shift* is a namespace-2/3/4 reference that moved when it should not have.
  Cross-check completeness against the discussion's recorded pre-strip counts, treating a mismatch as a prompt to re-read rather than as a defect — most of those counts are stale by construction, since batches 2 through 4 deleted or relocated much of the text they were measured over.
- **Commit:** `docs(mill-go-base): sweep Agent-mode step references in SKILL.md`

### Card 22: Namespace-scoped reference sweep across the three companion files

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Apply card 21's classify-then-edit method to the three companion files, using card 20's mapping for namespace-1 references only.
  Each file has its own untouched local namespace that must not shift: `resume.md`'s steps 1 through 4 and its references back into the batch loop ("continue at Execute step 2b", "Execute step 3 sub-step 3", "Execute step 3 sub-step 5"); `holistic-review.md`'s steps 0 through 7 including sub-steps 2.5, 3.5, and 3.6, and every "sub-step 3", "sub-step 3.5", "sub-step 3.6" reference among them; and `handoff.md`'s steps 1 through 6 plus its `**0. Pre-done gate.**`.
  The namespace-1 references to look for in these files are the ones naming the Agent-mode dispatch pattern's own steps — for instance `handoff.md`'s "this marker is written automatically by the NIT-fix pass's `--stage finalize` call (see '## Agent-mode dispatch' step 6)", which becomes step 5.
  Card 18 already rewrote each such reference to name `plugins/mill/skills/mill-go-base/SKILL.md`; this card changes only the number inside it.
- **Commit:** `docs(mill-go-base): sweep Agent-mode step references in the companion files`

### Card 23: Correct the two sibling SKILLs

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Three corrections, all of statements this task's own changes made false.
  1. **`mill-go2` "Known limits".** The sentence "Engages under `dispatch: agent` only (cold under `subprocess`/`psmux`)" describes a distinction that no longer exists — the base has one dispatch mode.
     Rewrite it to drop the conditional entirely while keeping the two limits that remain true: the fork runs on the driver's model, so `roles.implementer.model` and the per-tier agent files stop applying; and the lean driver's context gives a fork orchestrator instructions rather than code orientation.
  2. **`mill-go2` step references.** Apply card 20's mapping to every Agent-mode-namespace reference in the file — "base step 4", "step 4(a)'s transient re-dispatch", "the default `Agent()` call at step 3", "step 6.5.2's `--resume-incomplete`", and "6.5.1's warm `SendMessage` resume".
     Classify each before editing, exactly as in card 21; the discussion's recorded count for this file does not match its actual contents (it records a bare `step 6.5` that the file does not contain), so enumerate from the file itself.
  3. **Base-coverage enumerations in both files.** Both end with an identical sentence listing what lives in `mill-go-base`: "the Builder role, the entry phase gate, Prepare, the sequential batch loop, Agent-mode dispatch, Resume, holistic code review, and Handoff".
     Resume, holistic code review, and Handoff now live in that skill's companion files rather than in `SKILL.md` itself.
     Reword both sentences so the claim is true — the three named phases are still part of the skill, reached through mandatory-read pointers in its SKILL.md — without naming the companion files' paths, which would put base machinery detail into a file that must stay thin.
     Both variant files must stay under 4096 bytes and must not gain any of the literals `## Agent-mode dispatch`, `## Holistic code review`, `## Execute`, or `You are the **Builder**`; `test-mill-go-variants.py` asserts both.
- **Commit:** `docs(mill-go,mill-go2): correct sibling claims falsified by the base strip`

### Card 24: Regenerate the skills index and confirm no companion file was indexed

- **Context:**
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Regenerate the skills index by invoking `/mill-skills-index`, then inspect `git diff -- SKILLS.md` rather than asserting the diff is empty.
  An empty diff is **not** the expected outcome: the committed index already carries a stale `mill-go2` row whose description reads "Behaviourally identical to /mill-go today; exists so fork-dispatch experiments never destabilise the production orchestrator", while that skill's frontmatter `description:` has since been rewritten to "Forks the fixer role instead of dispatching it cold; otherwise identical to /mill-go, so fork-dispatch experiments never destabilise the production orchestrator."
  This drift predates the task and is unrelated to every edit in it; regenerating picks it up as an incidental true-up, which is exactly what a generated index is for.
  The invariant this card actually gates is narrower — assert all three of:
  1. No row exists for `resume.md`, `holistic-review.md`, or `handoff.md`.
     The generator scans `plugins/*/skills/**/SKILL.md` for frontmatter, so a companion file can only appear if it grew a `name:`/`description:` block, which cards 14 through 16 forbid.
     If one appears, that is a defect in the companion file: remove its frontmatter and regenerate, do not edit the index by hand.
  2. The total row count is unchanged from the committed version.
  3. Every changed row is a description true-up for an already-indexed skill whose text matches that skill's current frontmatter.
     For the `mill-go` and `mill-go2` rows specifically, read both files' frontmatter and confirm the new row text matches it — card 23 edits their bodies only, so a *frontmatter* change there would be an accidental edit to fix in card 23's files before regenerating.
  Commit the regenerated index once all three hold.
  If any of the three fails, halt and report which one; the remedy always lives in the source file, never in `SKILLS.md`.
- **Commit:** `docs(skills): regenerate the skills index after the mill-go-base strip`

## Batch Tests

`verify:` runs the same four tests as batch 4.

Two of them carry real weight here.
`test-mill-go-variants.py` is the direct gate on card 23: it asserts both variant files stay under 4096 bytes, carry none of the base's machinery literals, still bind their own `VARIANT_LABEL`, still declare both override-point sections, and still lock `mill-go2`'s fixer override — every one of which card 23's edits sit next to.
`test-mill-go-base-agent-only.py` guards cards 21 and 22 against collateral damage: a sweep that mangles one of the three mandatory-read directives or a companion path reference fails immediately.

Neither failure mode of the renumbering sweep is mechanically detectable, because all four namespaces share identical surface text.
The under-shift and over-shift checks named in cards 21 and 22 are a deliberate manual read-through, not an assertion, and card 24's three index invariants are likewise a gate rather than a test.
This is the reason the discussion designates a real `/mill-go2` run on the next task as the live end-to-end verification, backed by the `## History` restore note card 17 added.
