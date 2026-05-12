---
name: mill-status
description: print a status table for all active tasks.
---

# mill-status

Prints a multi-column table cross-referencing Home.md markers, wiki `active/` dirs, git worktrees, phase, current batch, and last timeline event. Reach for it when you need a consolidated view of all in-flight tasks.

## Run it

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-status.py" [--json] [--no-color] [--sort {slug,phase}]
```

Outputs colored text by default; `--no-color` disables ANSI. `--json` emits a JSON array for scripting. Sorts by `slug` (default) or `phase`.

## Phase reference

| Home.md marker | status.md phase | Written by | Next action |
|---|---|---|---|
| (unmarked) | n/a | — backlog | run `/mill-spawn` to claim |
| `[s]` | n/a | — spawn-ready fast-path | run `/mill-spawn` to claim |
| `[active]` | `discussing`/`discussed`/`planning`/`planned`/`implementing`/`reviewing`/`fixing`/`blocked` | mill-spawn / mill-claim | continue work via mill-start, mill-plan, mill-go |
| `[ready-to-merge]` | `done` | mill-go Handoff step 2 | run `/mill-merge` to squash to parent |
| `[pr-pending]` | `pr-pending` | mill-merge Step 5 (both PR-creation paths) | wait for GitHub PR to merge, then `/mill-cleanup --apply` |
| `[done]` | `done` | mill-merge Step 7 (post-squash) | run `/mill-cleanup --apply` for worktree/branch/portal teardown |
| `[abandoned]` | `abandoned` | mill-abandon | run `/mill-cleanup --apply` for teardown |

Lifecycle: `active → ready-to-merge → done` for the common path; `active → ready-to-merge → pr-pending → done` for the PR path; `active → abandoned` for the abandon path. Teardown for both `[done]` and `[abandoned]` is handled by `/mill-cleanup`, not by `/mill-merge`.
