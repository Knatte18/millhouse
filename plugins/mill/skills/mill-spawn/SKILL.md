---
name: mill-spawn
description: claim one task from the wiki Home.md and spin up a worktree for it.
---

# mill-spawn

Picks an unclaimed task from `Home.md`, marks it `[active]` under the wiki lock, creates a git worktree on a new branch, propagates `.millhouse/`, creates `wiki/active/<slug>/task.md`, creates a portal entry `container/portals/<slug>` pointing to `wiki/active/<slug>/`, recreates junctions (including `.wiki` and `.portals` in the new worktree), updates the hub's `.active` junction, assigns a VS Code title-bar color, and writes the initial `task/status.md`. The preferred way to start work on a new task.

## Run it

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-spawn.py" [--slug <slug>] [--dry-run]
```

Exits 0 (not 1) when the backlog is empty. Prints worktree path, branch, and status path on success. Takes and releases the wiki lock during the claim step.
