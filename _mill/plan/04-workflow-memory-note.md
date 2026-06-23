# Batch: workflow-memory-note

```yaml
task: "Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts"
batch: workflow-memory-note
number: 4
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Adds a one-line guideline to the `mill:workflow` skill (loaded on every
startup) that harness file-memory is ephemeral in mill task worktrees and
durable notes belong in versioned files (#522). Pure documentation; no
runnable surface. Independent of every other batch (touches only
`skills/workflow/SKILL.md`).

## Cards

### Card 13: Note ephemeral harness memory in mill:workflow

- **Context:**
  - `plugins/mill/skills/workflow/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/workflow/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Append a single sentence to the end of the `## Wiki mutations` paragraph (the paragraph ending `...daemon-rendered derived files.` at line ~32, immediately before the `---` separator on line ~34). The sentence must state that harness file-memory (the `memory/` directory) is ephemeral in task worktrees and is discarded when the worktree is removed on merge/cleanup, so durable notes belong in versioned files that merge to main — `CLAUDE.md`, `_codeguide/`, or code comments — not in harness memory. Keep it to one sentence, ASCII only, matching the surrounding terse style. Do not add a new heading or restructure the section.
- **Commit:** `docs(workflow): note harness file-memory is ephemeral in task worktrees (#522)`

## Batch Tests

`verify: null` — this batch edits only `skills/workflow/SKILL.md`, a
documentation skill with no runnable surface. Correctness is validated by
code review (the note is present, accurate, and in the cited location).
