---
name: mill-claim
description: claim a task from the wiki Home.md in the current worktree.
---

# mill-claim

Like `mill-spawn` but in-place: claims a task and creates a new branch in the current checkout without creating a separate worktree directory. Handles dirty working trees with a stash/carry/abort prompt.

## Run it

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-claim.py" [--slug <slug>] [--dry-run]
```

Does not create a new worktree directory. Exits 0 (not 1) when the backlog is empty. Takes the wiki lock during the claim step.

## In-place mode

mill-claim does NOT create a `<container>/wts/<slug>/` directory. The current worktree (the hub itself) IS the task worktree for this slug. The task branch is checked out in place. The "this is a mill task worktree" signal is the branch+Home.md pair, not a marker file.

Downstream skills (mill-start, mill-plan, mill-go, review scripts) resolve the active worktree via `_paths.resolve_active_worktree(container, slug, *, cfg, git_root)`, which returns the hub path in in-place mode. `task/discussion.md`, `task/plan/`, `task/reviews/`, and `task/status.md` live at `<active_hub>/task/...` — when `hub_relative_path` is set in `.millhouse/config.local.yaml`, that is `<git_root>/<hub_relative_path>/task/...`, NOT `<git_root>/task/...`.

Use mill-spawn instead when you want a separate worktree directory for the task.
