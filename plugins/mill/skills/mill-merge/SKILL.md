---
name: mill-merge
description: Squash-merge a completed task branch to its parent, create archive tag, flip Home.md [done]. Direct merge only — PR dispatch lives in mill-finalize. Worktree, branch, portal, and legacy wiki cleanup handled by /mill-cleanup. Runs from the child worktree.
---

# mill-merge

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are an integration engineer.
You never force-merge and never lose work.
`millpy-merge.py` runs the deterministic merge path;
this skill runs it, branches on its JSON, and handles the two callbacks and the lock wait.

Cross-worktree invariants:

- Run from the child worktree, never from the parent.
- Never `cd` to the parent worktree; it corrupts the shell cwd for the rest of the session.
- Parent-branch git operations go through `git -C <parent-path>`, which the script does.

## Run

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge.py" [args]
```

Run it with the Bash tool `timeout: 600000`.
Parse the last stdout line as JSON.
Print every `report` line verbatim, then every `warnings` entry prefixed `WARNING: `.

Args accumulate within one `/mill-merge` invocation.
Each re-run passes the stop's `resume` list.
Once a `--parent <new>` has been passed, pass it on every later re-run.

## Branch on the result

| `status` | `action` / `step` | Do |
| --- | --- | --- |
| `ok` | -- | Done; the report is already printed. For `route: "branch-protection-pr"` the PR URL is in `data.pr_url` and teardown completes on a later `/mill-merge` after the PR lands. |
| `halt` | `step: "lock"` | Follow `## Lock wait`. |
| `halt` | any other | Stop and report; the reason says what to fix and whether to re-run. |
| `callback` | `merge-in` | Follow `## Callback: merge-in`. |
| `callback` | `confirm-parent` | Follow `## Callback: confirm-parent`. |

## Callback: merge-in

Invoke the `mill-merge-in` skill with `data.parent_branch` as its positional argument.
If it fails, halt and report; no lock is held.
If its report carries `Substituted parent branch: <old> -> <new>`, add `--parent <new>` to the args.
Re-run the script with `resume` (`--merged-in`) appended.

## Callback: confirm-parent

The `report` already holds the operator message.
Ask with a numbered list per `mill:conversation`:

1. Proceed against `<data.candidate>` (Recommended)
2. Halt

On 1, re-run with `resume` (`--confirm-parent <candidate>`) appended.
On 2, halt.

## Lock wait

Arm the `Monitor` tool on a poll loop over `data.lock_path`.
Every 10 s it checks the file and prints one line when the file is gone or its second line (the timestamp) is older than 5 min.
After 5 min it gives up with a `TIMEOUT` line.
Write the loop with `[ -f ... ]`, `head -n 2 | tail -n 1`, and `date` only; no `sed`.

On the event, re-run the script once with the same args.
A second `lock` halt is reported to the operator with the holder info from `data`.

## No JSON

A non-zero exit with no JSON line is a crash or a hard kill.
Report the stderr tail and tell the operator to re-run `/mill-merge`.

On any failure or SIGTERM before the squash reaches origin, the script rolls the parent back to `origin/<parent_branch>` and releases the lock itself.
After a `SIGKILL` the lock goes stale in 5 min, and a half-applied squash surfaces on the next run as the dirty-parent halt, whose text says how to commit or reset it.
Once the squash is on origin nothing is rolled back; post-squash halts say `Merge landed on <parent> but ...`.

## Report

No self-report from this skill.
Reflection is the orchestrator's job: `mill-go` fires `/mill-self-report --auto` at its Handoff when `pipeline.auto_report: true`.
When invoked standalone, run `/mill-self-report` manually if reflection is wanted.

## Board discipline

- Wiki mutations go through `_client` calls (`set_phase`, `upsert_task`, `merge_tasks`);
  the daemon serializes all writes and pushes automatically.
- Task state (status file, discussion file, plan dir, reviews dir) lives in the task directory on the task branch, never in the wiki.
- Phase transitions go through `_status.append_phase`;
  hand-editing `_mill/status.md` is banned.
- Merge-lock file lives at `<parent-path>/.scratch/merge.lock`.
  Never placed anywhere else; other skills expect it there.
