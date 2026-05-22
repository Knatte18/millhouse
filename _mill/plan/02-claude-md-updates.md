# Batch: CLAUDE.md updates

```yaml
task: Set MILL_PYTHON via mill-setup, use in all skill invocations
batch: CLAUDE.md updates
number: 2
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Updates two CLAUDE.md files: the hub project CLAUDE.md (`CLAUDE.md` at the worktree root) and the user-global CLAUDE.md at `C:\Users\hanf\.claude\CLAUDE.md`. The hub CLAUDE.md's `## Script invocation` section needs the canonical form and the Exceptions note updated. The user CLAUDE.md's note about mill script paths needs to reference `$MILL_PYTHON` as the standard form with a bootstrapper exception callout.

## Cards

### Card 3: Update hub CLAUDE.md Script invocation section

- **Context:** none
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  **Edit A — update canonical form in the fenced bash block.**

  In the `## Script invocation` section, the fenced bash block contains:

  ```
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"
  ```

  Replace `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` with `"$MILL_PYTHON"` so the line reads:

  ```
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"
  ```

  **Edit B — update the Exceptions note.**

  The line immediately after the fenced block reads:

  ```
  Exceptions: unit tests use `uv run --project plugins/mill`; mill-go uses `$MILL_PYTHON`; nested calls after `--` in millpy-bg inherit PYTHONPATH automatically and must not carry the prefix.
  ```

  Replace it with:

  ```
  Exceptions: unit tests use `uv run --project plugins/mill`; mill-setup keeps the full path (bootstrapper — it writes `MILL_PYTHON` to `~/.claude/settings.json` via Phase 4.8); nested calls after `--` in millpy-bg inherit PYTHONPATH automatically and must not carry the prefix. `$MILL_PYTHON` is now the standard form for all other mill skills.
  ```

- **Commit:** `docs(CLAUDE.md): update Script invocation to use $MILL_PYTHON`

### Card 4: Update user CLAUDE.md mill script path reference

- **Context:** none
- **Edits:**
  - `C:\Users\hanf\.claude\CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  In `C:\Users\hanf\.claude\CLAUDE.md`, locate the bullet that reads:

  ```
  - **Never use `python3`.** On Windows, `python3` is a broken Microsoft Store alias. Bare `python` works (Python 3.13.1 is installed). For mill scripts, always use the explicit cache venv: `${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe`.
  ```

  Replace it with:

  ```
  - **Never use `python3`.** On Windows, `python3` is a broken Microsoft Store alias. Bare `python` works (Python 3.13.1 is installed). For mill scripts, use `$MILL_PYTHON` (set by mill-setup in `~/.claude/settings.json`). Exception: mill-setup itself uses the full path `${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe` since it is the bootstrapper.
  ```

- **Commit:** none — `C:\Users\hanf\.claude\CLAUDE.md` is outside the task git repository. Make the edit directly; do not attempt `git add` or `git commit` for this file. The change is tracked only in the user's local file system, not in the repo history.

## Batch Tests

Documentation-only batch; `verify: null`. After implementing, confirm:
1. `CLAUDE.md` `## Script invocation` code block contains `"$MILL_PYTHON"` not the full venv path.
2. `CLAUDE.md` Exceptions line no longer says `mill-go uses $MILL_PYTHON` and now describes the bootstrapper exception.
3. `C:\Users\hanf\.claude\CLAUDE.md` mill-scripts bullet says `$MILL_PYTHON` and has the bootstrapper exception note.
