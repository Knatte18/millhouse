---
name: mill-abandon
description: mark the current task abandoned.
---

# mill-abandon

Updates `status.md` to `phase: abandoned`, commits, and pushes. Prompts for confirmation unless `--force`. After this, run `mill-cleanup --apply` from the hub to remove the worktree and active dir.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-abandon.py" [--force]
```

Must run from inside the task's worktree, not from the hub. Exits immediately if phase is already `abandoned` or `done`. Respects builder-lock guard unless `--force` is given.
