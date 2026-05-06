# Batch: mill-plan SKILL.md fixes

```yaml
task: 22 (A) — SKILL.md round-2 fixes
batch: mill-plan SKILL.md fixes
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Two adjacent edits to step 1.5 of the Plan Review phase in `plugins/mill/skills/mill-plan/SKILL.md`. Card 1 adds the missing `wiki-config-mutation` row to the mechanical-fix table. Card 2 updates the "never passes --skip-validate" sentence that now contradicts the new row. Both edits are in the same section of the same file; they are one batch because the table row and the sentence update are semantically coupled — the sentence must be updated to not contradict the row.

No batch-local decisions differ from Shared Decisions.

## Cards

### Card 1: Add wiki-config-mutation row to step-1.5 fix table

- **Reads:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the step-1.5 mechanical-fix table, insert a new row for `wiki-config-mutation` after the `all-files-touched-mismatch` row and before the `missing-overview` row. The row content must state:
  - This check cannot be fixed by editing plan files — the batch intentionally modifies `wiki/config.yaml`.
  - To proceed, verify one of two conditions: (a) a bootstrap card is present — a card whose body explains why the config.yaml change is safe mid-flight for the currently-shipping task; or (b) the modified keys are provably unused — meaning key *removal or rename* where zero grep hits across `scripts/` and `skills/` confirm no existing code references them. (For key *addition* where consuming code is also being added in the same plan, zero grep hits does NOT satisfy condition (b); use (a) or halt.)
  - If either condition holds: document the justification in the validator-fix commit message and re-run the CLI with `--skip-validate`. If `wiki-config-mutation` co-occurs with other fixable validator errors, fix those first per their rows, then re-run with `--skip-validate`.
  - If neither condition holds: halt — the plan requires redesign.
- **Commit:** `docs(mill-plan): add wiki-config-mutation row to step-1.5 fix table`

### Card 2: Update "never passes --skip-validate" sentence

- **Reads:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In step 1.5, find the sentence "As of today, mill-plan never passes `--skip-validate`." (it is the last sentence of the paragraph that begins "If `pipeline.skip_validate: true` ever appears in config"). Replace it with: "mill-plan passes `--skip-validate` only when the fix table instructs it — see the `wiki-config-mutation` row." The rest of the paragraph is unchanged.
- **Commit:** `docs(mill-plan): update --skip-validate sentence to allow contextual use`

## Batch Tests

`verify: null` — pure documentation batch. No runnable test surface. Manual verification: after both cards are applied, read the changed section of `plugins/mill/skills/mill-plan/SKILL.md` and confirm (1) the `wiki-config-mutation` row is present in the table with the correct content, (2) the updated sentence is in place, and (3) no other text in the file was inadvertently modified.
