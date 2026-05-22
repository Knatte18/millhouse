# Batch: skill replace remaining

```yaml
task: Set MILL_PYTHON via mill-setup, use in all skill invocations
batch: skill replace remaining
number: 4
cards: 4
verify: null
depends-on: []
```

## Batch Scope

Replaces all occurrences of `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` with `"$MILL_PYTHON"` in the remaining 21 non-mill-setup SKILL.md files not covered by batch 3. Grouped into 4 cards by occurrence volume. Each card uses `replace_all: true` — one Edit call per file. The `PYTHONPATH=` prefix before each command is left unchanged.

File / occurrence counts:
- Card 7: mill-fold (6), mill-plan (5), mill-groom (5), mill-add (5)
- Card 8: mill-vscode (4), mill-start (4), mill-ghissues-to-tasks (4)
- Card 9: mill-wiki-push (2), mill-skills-from-scripts (2), mill-merge-in (2), mill-terminal (1), mill-status (1)
- Card 10: mill-spawn (1), mill-skills-index (1), mill-resume (1), mill-inspect (1), mill-color (1), mill-cleanup (1), mill-claim (1), mill-abandon (1), git-commit (1)

## Cards

### Card 7: Replace python.exe in mill-fold, mill-plan, mill-groom, mill-add

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-fold/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-groom/SKILL.md`
  - `plugins/mill/skills/mill-add/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  For each file in Edits:, Read it then use Edit with `replace_all: true`:
  - `old_string`: `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`
  - `new_string`: `"$MILL_PYTHON"`

  Expected occurrence counts after replacement (all should reach 0):
  - mill-fold: was 6
  - mill-plan: was 5
  - mill-groom: was 5
  - mill-add: was 5

- **Commit:** `docs(mill-fold,mill-plan,mill-groom,mill-add): replace python.exe with $MILL_PYTHON`

### Card 8: Replace python.exe in mill-vscode, mill-start, mill-ghissues-to-tasks

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-vscode/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  For each file in Edits:, Read it then use Edit with `replace_all: true`:
  - `old_string`: `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`
  - `new_string`: `"$MILL_PYTHON"`

  Expected occurrence counts after replacement (all should reach 0):
  - mill-vscode: was 4
  - mill-start: was 4
  - mill-ghissues-to-tasks: was 4

- **Commit:** `docs(mill-vscode,mill-start,mill-ghissues-to-tasks): replace python.exe with $MILL_PYTHON`

### Card 9: Replace python.exe in mill-wiki-push, mill-skills-from-scripts, mill-merge-in, mill-terminal, mill-status

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-wiki-push/SKILL.md`
  - `plugins/mill/skills/mill-skills-from-scripts/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
  - `plugins/mill/skills/mill-terminal/SKILL.md`
  - `plugins/mill/skills/mill-status/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  For each file in Edits:, Read it then use Edit with `replace_all: true`:
  - `old_string`: `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`
  - `new_string`: `"$MILL_PYTHON"`

  Expected occurrence counts after replacement (all should reach 0):
  - mill-wiki-push: was 2
  - mill-skills-from-scripts: was 2
  - mill-merge-in: was 2
  - mill-terminal: was 1
  - mill-status: was 1

- **Commit:** `docs(mill-wiki-push,mill-skills-from-scripts,mill-merge-in,mill-terminal,mill-status): replace python.exe with $MILL_PYTHON`

### Card 10: Replace python.exe in mill-spawn, mill-skills-index, mill-resume, mill-inspect, mill-color, mill-cleanup, mill-claim, mill-abandon, git-commit

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-spawn/SKILL.md`
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/skills/mill-inspect/SKILL.md`
  - `plugins/mill/skills/mill-color/SKILL.md`
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
  - `plugins/mill/skills/mill-claim/SKILL.md`
  - `plugins/mill/skills/mill-abandon/SKILL.md`
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  For each file in Edits:, Read it then use Edit with `replace_all: true`:
  - `old_string`: `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`
  - `new_string`: `"$MILL_PYTHON"`

  Each file has exactly 1 occurrence. All should reach 0.

- **Commit:** `docs(mill-spawn,mill-skills-index,mill-resume,mill-inspect,mill-color,mill-cleanup,mill-claim,mill-abandon,git-commit): replace python.exe with $MILL_PYTHON`

## Batch Tests

Documentation-only batch; `verify: null`. After all 4 cards, run:
```bash
grep -l '\.venv/Scripts/python\.exe' \
  plugins/mill/skills/mill-fold/SKILL.md \
  plugins/mill/skills/mill-plan/SKILL.md \
  plugins/mill/skills/mill-groom/SKILL.md \
  plugins/mill/skills/mill-add/SKILL.md \
  plugins/mill/skills/mill-vscode/SKILL.md \
  plugins/mill/skills/mill-start/SKILL.md \
  plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md \
  plugins/mill/skills/mill-wiki-push/SKILL.md \
  plugins/mill/skills/mill-skills-from-scripts/SKILL.md \
  plugins/mill/skills/mill-merge-in/SKILL.md \
  plugins/mill/skills/mill-terminal/SKILL.md \
  plugins/mill/skills/mill-status/SKILL.md \
  plugins/mill/skills/mill-spawn/SKILL.md \
  plugins/mill/skills/mill-skills-index/SKILL.md \
  plugins/mill/skills/mill-resume/SKILL.md \
  plugins/mill/skills/mill-inspect/SKILL.md \
  plugins/mill/skills/mill-color/SKILL.md \
  plugins/mill/skills/mill-cleanup/SKILL.md \
  plugins/mill/skills/mill-claim/SKILL.md \
  plugins/mill/skills/mill-abandon/SKILL.md \
  plugins/mill/skills/git-commit/SKILL.md
```
Expected: no output (zero matches in all files).
