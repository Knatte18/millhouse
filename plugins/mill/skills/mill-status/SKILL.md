---
name: mill-status
description: print a status table for all active tasks.
---

# mill-status

Prints a multi-column table cross-referencing Home.md markers, wiki `active/` dirs, git worktrees, phase, current batch, and last timeline event. Reach for it when you need a consolidated view of all in-flight tasks.

## Run it

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy-status.py [--json] [--no-color] [--sort {slug,phase}]
```

Outputs colored text by default; `--no-color` disables ANSI. `--json` emits a JSON array for scripting. Sorts by `slug` (default) or `phase`.
