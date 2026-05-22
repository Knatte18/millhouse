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

Replaces `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` with `"$MILL_PYTHON"` in `mill-go/SKILL.md` (31 invocation occurrences) and `mill-autofix/SKILL.md` (14 occurrences). Uses `replace_all: true` then restores the 2 venv-check blocks in mill-go to the explicit path — venv-check blocks must use the explicit path so they work correctly even when `$MILL_PYTHON` is unset (e.g. before mill-setup has been run). The `PYTHONPATH=` prefix before each command is left unchanged per the `pythonpath-prefix-stays-inline` shared decision.

## Cards

### Card 5: Replace python.exe path in mill-go SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Read `plugins/mill/skills/mill-go/SKILL.md`.

  **Step 1 — bulk replace.** Use Edit with `replace_all: true`:
  - `old_string`: `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`
  - `new_string`: `"$MILL_PYTHON"`

  This replaces all 33 occurrences, including the 2 venv-check blocks. Steps 2 and 3 restore those blocks.

  **Step 2 — restore venv-check block 1 (no surrounding indent).**

  Use Edit (no `replace_all`) with:
  - `old_string`:
    ```
    if [ ! -f "$MILL_PYTHON" ]; then
        echo "[mill-go] venv missing -- attempting uv sync"
        uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
        if [ ! -f "$MILL_PYTHON" ]; then
            echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
            exit 1
        fi
    fi
    ```
  - `new_string`:
    ```
    if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
        echo "[mill-go] venv missing -- attempting uv sync"
        uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
        if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
            echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
            exit 1
        fi
    fi
    ```

  **Step 3 — restore venv-check block 2 (3-space outer indent).**

  Use Edit (no `replace_all`) with:
  - `old_string`:
    ```
       if [ ! -f "$MILL_PYTHON" ]; then
           echo "[mill-go] venv missing -- attempting uv sync"
           uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
           if [ ! -f "$MILL_PYTHON" ]; then
               echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
               exit 1
           fi
       fi
    ```
  - `new_string`:
    ```
       if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
           echo "[mill-go] venv missing -- attempting uv sync"
           uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
           if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
               echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
               exit 1
           fi
       fi
    ```

  After all three steps, verify with grep:
  ```bash
  grep -c '\.venv/Scripts/python\.exe' plugins/mill/skills/mill-go/SKILL.md
  ```
  Expected output: `2` (the two restored venv-check blocks).

- **Commit:** `docs(mill-go): replace python.exe with $MILL_PYTHON in invocations, preserve venv-check`

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
grep -c '\.venv/Scripts/python\.exe' plugins/mill/skills/mill-go/SKILL.md plugins/mill/skills/mill-autofix/SKILL.md
```
Expected: `plugins/mill/skills/mill-go/SKILL.md:2` (the two preserved venv-check blocks) and `plugins/mill/skills/mill-autofix/SKILL.md:0`.
