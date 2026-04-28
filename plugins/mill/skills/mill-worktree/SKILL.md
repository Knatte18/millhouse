---
name: mill-worktree
description: generic worktree management (no wiki claim).
---

# mill-worktree

Creates, removes, or lists git worktrees without touching the wiki or claiming a task. Use `create` for a scratch worktree not tied to a Home.md task. VS Code title color is assigned automatically on create.

## Run it

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy-worktree.py create --branch <name> [--dir-name <name>] [--color <name>] [--dry-run]
python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy-worktree.py remove <worktree_path>
python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy-worktree.py list
```

Does not write `active.slug.md` or `status.md` — this worktree is not claimed against the wiki. `create` creates the branch locally if it does not exist.
