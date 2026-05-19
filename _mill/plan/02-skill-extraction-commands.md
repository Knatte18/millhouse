# Batch: SKILL.md extraction commands

```yaml
task: Silence verbose review log lines cluttering orchestrator output
batch: SKILL.md extraction commands
number: 2
cards: 3
verify: null
depends-on: []
```

## Batch Scope

Replace vague poll-extraction prose in three SKILL.md files with the unambiguous `grep '^{' <log-path> | tail -1` command. There are 5 occurrences in `mill-go/SKILL.md`, 2 in `mill-start/SKILL.md`, and 3 in `mill-plan/SKILL.md`. The change is purely instructional (these files guide LLM orchestrators, not compiled code) and has no test surface. No surrounding logic in the skill files is changed.

## Cards

### Card 4: Update poll-extraction in `mill-go/SKILL.md`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace 5 poll-extraction wording occurrences in `plugins/mill/skills/mill-go/SKILL.md`. For each occurrence, replace only the trailing extraction clause while leaving the preceding `Poll \`cat <log-path>\` until \`[mill-bg] EXIT\` appears` sentence intact.

  **Occurrence 1** (around line 179) — current text ends with:
  `read the log and extract the JSON summary line (the last non-empty, non-sentinel line in the log).`
  Replace that clause with:
  `run \`grep '^{' <log-path> | tail -1\` to extract the JSON summary line.`

  **Occurrence 2** (around line 236) — current text ends with:
  `then extract the JSON summary line (last non-empty, non-sentinel line).`
  Replace that clause with:
  `then run \`grep '^{' <log-path> | tail -1\` to extract the JSON summary line.`

  **Occurrence 3** (around line 253) — current text ends with:
  `read the log and extract the JSON summary line (the last non-empty, non-sentinel line in the log).`
  Replace that clause with (same as occurrence 1):
  `run \`grep '^{' <log-path> | tail -1\` to extract the JSON summary line.`

  **Occurrence 4** (around line 270) — current text ends with:
  `then extract the JSON summary line from the log.`
  Replace that clause with:
  `then run \`grep '^{' <log-path> | tail -1\` to extract the JSON summary line.`

  **Occurrence 5** (around line 454) — current text ends with:
  `then extract the JSON summary line from the log.`
  Replace that clause with (same as occurrence 4):
  `then run \`grep '^{' <log-path> | tail -1\` to extract the JSON summary line.`
- **Commit:** `docs(mill-go): use grep for JSON extraction in poll steps`

### Card 5: Update poll-extraction in `mill-start/SKILL.md`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace 2 poll-extraction wording occurrences in `plugins/mill/skills/mill-start/SKILL.md`.

  **Occurrence 1** (around line 120) — current text ends with:
  `read the log and extract the JSON summary line (the last non-empty, non-sentinel line in the log).`
  Replace that clause with:
  `run \`grep '^{' <log-path> | tail -1\` to extract the JSON summary line.`

  **Occurrence 2** (around line 136) — current text ends with:
  `then extract the JSON summary line.`
  Replace that clause with:
  `then run \`grep '^{' <log-path> | tail -1\` to extract the JSON summary line.`
- **Commit:** `docs(mill-start): use grep for JSON extraction in poll steps`

### Card 6: Update poll-extraction in `mill-plan/SKILL.md`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace 3 poll-extraction wording occurrences in `plugins/mill/skills/mill-plan/SKILL.md`.

  **Occurrence 1** (around line 98) — current text ends with:
  `then extract the JSON line from the log.`
  Replace that clause with:
  `then run \`grep '^{' <log-path> | tail -1\` to extract the JSON line.`

  **Occurrence 2** (around line 133) — current text ends with:
  `then read the log and extract the JSON summary line (the last non-empty, non-sentinel line).`
  Replace that clause with:
  `then run \`grep '^{' <log-path> | tail -1\` to extract the JSON summary line.`

  **Occurrence 3** (around line 155) — current text ends with:
  `then read the log and extract the JSON summary line (the last non-empty, non-sentinel line).`
  Replace that clause with (same as occurrence 2):
  `then run \`grep '^{' <log-path> | tail -1\` to extract the JSON summary line.`
- **Commit:** `docs(mill-plan): use grep for JSON extraction in poll steps`

## Batch Tests

`verify: null` — SKILL.md changes are instructional text for LLM orchestrators; there is no runnable test surface. Correctness is verified by visual inspection: confirm each updated occurrence uses the `grep '^{' <log-path> | tail -1` form and the surrounding poll sentence is intact.
