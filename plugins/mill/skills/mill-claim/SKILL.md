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
