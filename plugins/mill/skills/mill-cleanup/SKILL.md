---
name: mill-cleanup
description: "sweeper: reconcile hub git worktrees, wiki active/<slug>/ dirs, and Home.md markers based on status.md phase."
---

# mill-cleanup

Sweeps task artefacts: removes worktrees, branches, portals, and legacy wiki active-dirs for tasks whose Home.md marker is `[done]` (with archive tag confirming the squash landed); polls `gh pr list` for `[pr-pending]` tasks and finalises teardown when the PR merges; reports orphan worktrees and stranded Home.md markers. Runs from the hub, never from a task worktree.

## States handled

| Home.md marker | status.md phase | Action |
|---|---|---|
| `[done]` | `done` (+ archive tag present) | Remove worktree, branch, portal, legacy wiki active-dir |
| `[done]` | `done` (archive tag absent) | Report — squash never landed, run mill-merge first |
| `[ready-to-merge]` | `done` | Skip — task is live, waiting on mill-merge |
| `[pr-pending]` | `pr-pending` | Poll `gh pr list`; if MERGED → create archive tag (if absent) + flip `[done]` + teardown; OPEN → skip; CLOSED → report for manual triage |
| `[active]` / `[ready-to-merge]` / `[pr-pending]` with no active worktree | n/a | Report as orphan Home.md marker |

Cleanup takes the wiki lock only when `--apply` is set. PR-reap also runs only under `--apply` — dry-run mode reports which `[pr-pending]` tasks WOULD be polled.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-cleanup.py" [--apply]
```

Default is dry-run — pass `--apply` to execute removals. Must run from the hub, not from a worktree. Takes the wiki lock only when `--apply` is set.
