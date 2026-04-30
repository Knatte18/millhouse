---
name: mill-terminal
description: open Claude Code in an active worktree.
---

# mill-terminal

Scans the worktrees container for directories with an `active.slug.md` marker, presents a numbered picker, and launches `claude --name <slug>` in the selected worktree. Auto-selects when only one active worktree exists.

## Run it

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-terminal.py"
```

Takes no arguments. Exits 0 (with a message) when no active worktrees are found. Exits 1 on invalid selection or if the `claude` launcher is not on PATH.
