---
name: mill-vscode
description: open VS Code in an active worktree.
---

# mill-vscode

Scans active worktrees and opens VS Code in the selected one. Use `--slug` to skip the interactive picker or `--list` to enumerate active worktrees without launching.

## Run it

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-vscode.py" [--slug <slug>] [--list]
```

Exits 0 (with a message) when no active worktrees exist. Auto-selects when only one worktree is found. Probes `code.cmd`, `code`, and the Windows `LOCALAPPDATA` install path.
