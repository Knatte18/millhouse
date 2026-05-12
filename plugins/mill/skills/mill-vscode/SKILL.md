---
name: mill-vscode
description: open VS Code in an active worktree, filtering out ones already open.
---

# mill-vscode

Lists active worktrees that do **not** already have a VS Code window open in them, then prompts:
- `<Enter>` — spawn a new task and open it
- `1`–`N` — open the listed worktree at that index
- `q` — quit without launching

When every worktree is already open (filter empties the list), falls through to spawn-and-open — same as the zero-active-worktrees path.

Open-window detection is best-effort (Windows via `Get-CimInstance Win32_Process`, Linux via `ps`). On macOS or when the probe fails, all active worktrees are shown unfiltered.

## Flags

- `--new` — spawn a new task and open it without showing the existing-worktrees list. Mutually exclusive with `--slug`.
- `--slug <slug>` — open the worktree for slug `<slug>` without showing the picker.
- `--list` — print every active worktree without launching VS Code or applying the filter.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-vscode.py"          # default
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-vscode.py" --new    # spawn-and-open
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-vscode.py" --slug <slug>
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-vscode.py" --list
```
