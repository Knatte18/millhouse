# Batch: skill replace heavy

```yaml
task: Set MILL_PYTHON via mill-setup, use in all skill invocations
batch: skill replace heavy
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Replaces all occurrences of `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` with `"$MILL_PYTHON"` in the two highest-occurrence SKILL.md files: `mill-go/SKILL.md` (33 occurrences) and `mill-autofix/SKILL.md` (14 occurrences). Uses `replace_all: true` in the Edit tool — one call per file handles every occurrence. The `PYTHONPATH=` prefix before each command is left unchanged per the `pythonpath-prefix-stays-inline` shared decision.

## Cards

### Card 5: Replace python.exe path in mill-go SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Read `plugins/mill/skills/mill-go/SKILL.md`. Use Edit with `replace_all: true`:
  - `old_string`: `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`
  - `new_string`: `"$MILL_PYTHON"`

  This replaces all 33 occurrences. Verify with grep after editing:
  ```bash
  grep -c '\.venv/Scripts/python\.exe' plugins/mill/skills/mill-go/SKILL.md
  ```
  Expected output: `0`.

- **Commit:** `docs(mill-go): replace python.exe path with $MILL_PYTHON (33 occurrences)`

### Card 6: Replace python.exe path in mill-autofix SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-autofix/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Read `plugins/mill/skills/mill-autofix/SKILL.md`. Use Edit with `replace_all: true`:
  - `old_string`: `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`
  - `new_string`: `"$MILL_PYTHON"`

  This replaces all 14 occurrences. Verify with grep after editing:
  ```bash
  grep -c '\.venv/Scripts/python\.exe' plugins/mill/skills/mill-autofix/SKILL.md
  ```
  Expected output: `0`.

- **Commit:** `docs(mill-autofix): replace python.exe path with $MILL_PYTHON (14 occurrences)`

## Batch Tests

Documentation-only batch; `verify: null`. After implementing both cards, run:
```bash
grep -l '\.venv/Scripts/python\.exe' plugins/mill/skills/mill-go/SKILL.md plugins/mill/skills/mill-autofix/SKILL.md
```
Expected: no output (zero matches in either file).
