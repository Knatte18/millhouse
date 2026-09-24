---
name: mill-session-tasks
description: re-render this worktree's .vscode/tasks.json (session launch tasks) from the current mill config.
---

# mill-session-tasks

Rewrites `.vscode/tasks.json` in the current worktree with the session launch tasks.
The model and effort of each session come from `spawn.sessions` in `mill-config.yaml` / `.millhouse/config.local.yaml`.
Model and effort are baked into the file, so re-run this after changing those values.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-session-tasks.py"
```

Exits 0 on success (including when the file is already up to date), 1 on any error.
