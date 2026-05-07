# Batch: auto-report SKILL.md edits

```yaml
task: 26 (A) — auto-report-auto-submit
batch: auto-report SKILL.md edits
number: 1
cards: 3
verify: null
depends-on: []
```

## Batch Scope

This batch delivers all three SKILL.md edits required to make auto-report work hands-free: (1) mill-self-report gains a `--auto` mode that skips the confirmation prompt and files all candidates directly; (2) mill-go passes `--auto` when it auto-fires mill-self-report; (3) mill-plan does the same. All changes are pure text edits to three SKILL.md files — no Python code, no config, no tests. The batch has no external interface for a next batch to consume; this is the entire task.

## Cards

### Card 1: Update mill-self-report/SKILL.md with --auto mode

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-self-report/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In the frontmatter, change `argument-hint: "[free-text steering]"` to `argument-hint: "[--auto | free-text steering]"`.
  2. In Section 2 "Invocation modes", the auto-fire bullet currently says: `The skill receives no argument in this mode.` Replace that sentence with: `The skill receives \`--auto\` as its argument. This signals auto-file-all mode: all distilled candidates are filed without user confirmation.`
  3. In Step 4 "Present numbered list": add a conditional branch at the very start of the step. When the skill argument is `--auto`, skip the numbered list entirely — proceed directly to Step 5 with all distilled candidates selected (equivalent to the user having typed `all`). Step 6 (the summary line) always runs regardless of mode. The existing numbered-list flow (for no-arg or free-text-steering invocations) is unchanged.
- **Commit:** `feat(mill-self-report): add --auto mode — file all candidates without confirmation`

### Card 2: Update mill-go/SKILL.md to pass --auto

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In the Handoff section, Step 5 currently reads: `If \`pipeline.auto_report: true\` → invoke \`/mill-self-report\` directly with no argument.` Change `invoke \`/mill-self-report\` directly with no argument` to `invoke \`/mill-self-report --auto\``. The rest of the sentence ("The skill checks `gh auth` itself and bails cleanly if absent. Wait for it to finish before continuing.") is unchanged.
- **Commit:** `feat(mill-go): pass --auto to mill-self-report on auto-fire`

### Card 3: Update mill-plan/SKILL.md to pass --auto

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In the Handoff section, the auto_report line currently reads: `invoke \`/mill-self-report\` with no argument`. Change it to `invoke \`/mill-self-report --auto\``. The surrounding sentence ("If the deep-merged config has `pipeline.auto_report: true`, … and let it finish before reporting to the user.") is unchanged.
- **Commit:** `feat(mill-plan): pass --auto to mill-self-report on auto-fire`

## Batch Tests

`verify: null` — this batch edits SKILL.md files only. There is no runnable test surface. Manual verification: invoke `/mill-self-report --auto` and confirm candidates are filed without prompting; invoke `/mill-self-report` with no arg and confirm the numbered list still appears.
