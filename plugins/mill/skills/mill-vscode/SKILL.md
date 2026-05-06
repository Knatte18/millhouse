---
name: mill-vscode
description: open VS Code in an active worktree.
---

# mill-vscode

Scans active worktrees and opens VS Code in the selected one. When no active worktrees exist and no flags are set, auto-invokes mill-spawn to create a new worktree first. Use `--slug` to skip the interactive picker or `--list` to enumerate active worktrees without launching.

## Run it

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-vscode.py" [--slug <slug>] [--list]
```

Exits 0 (with a message) when no active worktrees exist and the backlog is empty after auto-spawn. Auto-selects when only one worktree is found. Probes `code.cmd`, `code`, and the Windows `LOCALAPPDATA` install path.
