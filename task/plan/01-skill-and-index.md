# Batch: skill-and-index

```yaml
task: 'mill-pause: graceful orchestrator pause between operations'
batch: skill-and-index
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Delivers the entire task in two sequential cards: write `plugins/mill/skills/mill-pause/SKILL.md` (the ~20-line behavioral skill), then run `millpy-skills-index.py` to regenerate `SKILLS.md` so the new skill appears in the index table. No scripts, no status schema changes, no modifications to existing skills or orchestrators. This is the only batch; nothing depends on it.

## Cards

### Card 1: Write mill-pause SKILL.md

- **Context:**
  - `plugins/mill/skills/mill-color/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/mill-pause/SKILL.md`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/skills/mill-pause/SKILL.md` with the following content:

  Front matter:
  - `name: mill-pause`
  - `description: gracefully pause an orchestrator session after the current operation completes.`

  Body (≤~20 lines):
  - H1 `# mill-pause`
  - One-paragraph intro: signals the running orchestrator to stop cleanly after its current in-progress operation completes, without starting new work; safe at any point in a mill-go or mill-plan session; machine can be put to sleep; resume picks up where it left off.
  - H2 `## When invoked` with two cases:
    - **If a `millpy-bg` poll is in progress:** let the current poll run to completion — poll `cat <log-path>` until `[mill-bg] EXIT` appears, extract and parse the JSON summary as usual. Do NOT dispatch any subsequent CLI call.
    - **If no poll is in progress** (e.g. between dispatch decisions, or during Entry/Prepare): stop immediately — do not dispatch the next CLI call.
  - H2 `## On stopping` with context-sensitive confirmation messages:
    - **mill-go session:** `Paused after [batch/review/fix description]. State is consistent. Run /mill-go to resume.`
    - **mill-plan session:** `Paused after [review/fix-round description]. State is consistent. Run /mill-plan to resume.`
  - Final line: "Write nothing to `task/status.md` or any file. The existing phase and batch state are sufficient for resume."

- **Commit:** `feat(mill-pause): add mill-pause SKILL.md`

### Card 2: Regenerate SKILLS.md

- **Context:**
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Run `millpy-skills-index.py` to regenerate `SKILLS.md`:
  ```bash
  uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-skills-index.py"
  ```
  Confirm that `SKILLS.md` now contains a row for `mill-pause` in the `## mill` table with description `gracefully pause an orchestrator session after the current operation completes.`. Do not hand-edit `SKILLS.md`.
- **Commit:** `chore(mill-pause): regenerate SKILLS.md`

## Batch Tests

`verify: null` — this batch delivers one SKILL.md and one SKILLS.md regeneration. There is no runnable test suite for a pure behavioral skill. Manual verification (documented in `task/discussion.md`) requires a live orchestrator session and is out of scope for the implementer.
