---
name: mill-cleanup
description: "sweeper: reconcile hub git worktrees, wiki active/<slug>/ dirs, and Home.md markers based on status.md phase."
---

# mill-cleanup

Scans active dirs for tasks whose `status.md` shows `done` or `abandoned`, then removes matching worktrees, branches, and wiki dirs, and resets Home.md markers. Reports orphan worktrees and unreadable status files without removing them.

## Run it

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-cleanup.py" [--apply]
```

Default is dry-run — pass `--apply` to execute removals. Must run from the hub, not from a worktree. Takes the wiki lock only when `--apply` is set.
