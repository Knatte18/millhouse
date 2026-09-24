---
name: mill-spawn
description: claim one task from the wiki Home.md and spin up a worktree for it.
---

# mill-spawn

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

Picks an unclaimed task from `Home.md`, marks it `[active]` under the wiki lock, creates a git worktree on a new branch, propagates `.millhouse/`, creates a portal entry `container/portals/<slug>` pointing to `wts/<slug>/_mill/`, recreates junctions (including `.wiki`, `.active`, and `.portals` in the new worktree), updates the hub's `.active` junction, assigns a VS Code title-bar color, seeds `.vscode/tasks.json` with the six session launch tasks (`mill: start`, `start-auto`, `start-orch`, `plan`, `go`, `quick`; session names `<slug>:<phase>`, model and effort from `spawn.sessions`), and writes the initial `_mill/status.md`.

The keyboard shortcuts for those tasks are user-level and are seeded by `/mill-setup`, not by mill-spawn.
Run `millpy-session-tasks` in a worktree after changing `spawn.sessions` to refresh its `tasks.json`.
The preferred way to start work on a new task.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-spawn.py" [--slug <slug>] [--dry-run]
```

Exits 0 (not 1) when the backlog is empty.
Prints worktree path, branch, and status path on success.
Takes and releases the wiki lock during the claim step.

Use mill-claim instead when you want to claim the task in the current checkout (in-place) without creating a separate worktree directory.
