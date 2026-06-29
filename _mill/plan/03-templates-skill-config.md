# Batch: templates-skill-config

```yaml
task: "Add first-class Moves/Renames field to plan cards for rename-heavy batches"
batch: "templates-skill-config"
number: 3
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
depends-on: []
```

## Batch Scope

This batch authors all the human-readable surface of the feature into the plan
pipeline itself (the issue's core thesis — the mechanic must live in the PLAN,
not the implementer brief): the `Moves:` field and the canonical
`## Rename mechanic` section in `plan-batch.md`; review criteria in the three
review templates; planner instructions and the Step 1.5 validator-fix rows in
`mill-plan/SKILL.md`; and registration of the `pipeline.rename_detect_pct`
config knob in both the template and hub `mill-config.yaml`. It is independent
of the code batches (pure text/config) and touches no script. Card 17 is a
deliberate bootstrap card for the `mill-config.yaml` edit (see its Requirements).

## Cards

### Card 12: Moves field and Rename mechanic section in plan-batch template

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Cards` field documentation, add a `**Moves:**` bullet describing it as a required field of old->new rename pairs, listed immediately after the `**Deletes:**` bullet and before `**Requirements:**`. Document the grammar: multi-line sub-bullets each `` `old/path` -> `new/path` `` (ASCII ` -> `), or the literal `none` on the field line; a path expressed in `Moves:` must NOT also appear in `Creates:`/`Deletes:`; an extraction is a `Moves:` pair plus a separate `Creates:` for the new file. Add `- **Moves:** none` to the example `### Card N` block, positioned after `Deletes:`. Add a canonical `## Rename mechanic` section (placed before `## Batch Scope` in the template body, matching the issue's workaround placement) whose text instructs: for each `Moves:` pair run `git mv <old> <new>` FIRST, then make ONLY surgical edits to the lines that change (package/module declaration, imports, identifier retargeting, seam splits); use a full-file create only for genuinely new files with no predecessor; never write-from-scratch-then-delete. State that this section MUST be present in any batch that has a non-empty `Moves:` (enforced by the `move-mechanic-missing` validator check). ASCII only. Keep the existing "Strip this HTML comment before writing" guidance.
- **Commit:** `feat(templates): add Moves field and Rename mechanic section to plan-batch`

### Card 13: Move criteria in plan-review templates

- **Context:**
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In both templates' `## Criteria` lists add: (a) **Moves well-formed** — each `Moves:` entry is an `` `old` -> `new` `` pair; (b) **Rename mechanic present** — a batch with any non-empty `Moves:` states the `git mv` + surgical-edit mechanic via a `## Rename mechanic` section; (c) **No full-file rewrites of relocated files** — a plan that prescribes writing a relocated file from scratch (instead of git mv + surgical edits) is a finding. Update the existing **Completeness** criterion to mention that `Moves:` is now an expected card field. Keep the tight phrasing of the surrounding criteria bullets.
- **Commit:** `feat(templates): add move criteria to plan-review templates`

### Card 14: Rename-landed-as-rename criterion in code-review template

- **Context:**
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/templates/review-code-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a `## Criteria` bullet: for each planned `Moves:` pair (visible in the batch file), the relocated file should land as a `git mv` + surgical edit; a relocated file rewritten from scratch (lost structure, mass reformat, history-breaking diff) is **BLOCKING**. Note that an advisory NIT may also be present from the backend's mechanical rename check (per `## Shared Decisions` mechanical-rename-check-advisory) and that the reviewer is the layer empowered to escalate a genuine rewrite to BLOCKING.
- **Commit:** `feat(templates): add rename-landed-as-rename criterion to code review`

### Card 15: Planner Moves instructions in mill-plan SKILL

- **Context:**
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a `## Principles` bullet (and a short note in `Phase: Plan` near the card-field guidance) instructing the planner to: express renames as `Moves:` pairs and NEVER as a `Creates:` + `Deletes:` combination; include the `## Rename mechanic` section in any batch containing a non-empty `Moves:`; keep naming the specific surgical edits in `Requirements:` using stable identifiers; and represent a rename + extraction as the `Moves:` pair for the relocated file plus a separate `Creates:` for the newly extracted file.
- **Commit:** `docs(mill-plan): instruct planner to use Moves for renames`

### Card 16: New validator-fix rows in mill-plan Step 1.5 table

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the Step 1.5 fix table, add one row per new validator check: `move-format` (re-format the bullet to `` `old` -> `new` ``); `move-redundant` (remove the duplicated path from `Creates:`/`Deletes:`, keeping it only in `Moves:`); `move-source-missing` (correct a typo'd source, or halt if the source genuinely does not exist); `move-target-collision` (rename the colliding target or fix the duplicate; halt if two cards truly need the same destination); `move-mechanic-missing` (add the canonical `## Rename mechanic` section to the offending batch file). Extend the existing `card-missing-field` row note to mention that a missing `Moves:` is fixed by adding `Moves: none`.
- **Commit:** `docs(mill-plan): add move-check rows to validator-fix table`

### Card 17: Register pipeline.rename_detect_pct in config (bootstrap card)

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `rename_detect_pct: 30` with a short comment to the `pipeline:` block of BOTH `plugins/mill/templates/mill-config.yaml` (after `max_batch_context_tokens`, line ~125) and the hub `mill-config.yaml` (its `pipeline:` block, line ~14), keeping the two in sync per CLAUDE.md. Add/extend a `test-config.py` case asserting `rename_detect_pct` is a recognised `pipeline` key (loads without an unknown-key warning) and defaults sensibly. BOOTSTRAP JUSTIFICATION (this card edits `mill-config.yaml`, which trips the `wiki-config-mutation` validator check): the change is a purely additive key with a safe default (30); the only code that reads it is added in batch 4's `_review_code.py`, and operational mill-go reviews run from the hub/cache scripts (not this task's worktree), so the new reader is never active during this task's own execution — there is no self-applying mid-flight behavior change. mill-plan resolves the `wiki-config-mutation` finding via fix-table condition (a) and re-runs the validator with `--skip-check wiki-config-mutation`.
- **Commit:** `feat(config): register pipeline.rename_detect_pct knob`

## Batch Tests

`verify:` runs `test-config.py`, which is the only runnable surface this batch
changes (the config knob registration). The template/SKILL/markdown edits are
documentation text with no separate runnable test. The `## Rename mechanic`
heading string authored in card 12 is consumed by the batch-2
`move-mechanic-missing` check and exercised by that batch's tests.
