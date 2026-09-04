---
name: mill-pause
description: gracefully pause an orchestrator session after the current operation completes.
---

# mill-pause

Signals the running orchestrator to stop cleanly after its current in-progress operation completes, without starting new work.
Safe at any point in a mill-go or mill-plan session.
The machine can be put to sleep;
resume picks up where it left off.

## When invoked

- **If a `millpy-bg` poll is in progress:** let the current poll run to completion — poll `cat <log-path>` until `[mill-bg] EXIT` appears, extract and parse the JSON summary as usual.
  Do NOT dispatch any subsequent CLI call.
- **If no poll is in progress** (e.g. between dispatch decisions, or during Entry/Prepare): stop immediately — do not dispatch the next CLI call.
- **If an Agent-mode dispatch (implementer/reviewer/fixer) is in flight:** wait for its `<task-notification>` to arrive, then run the CLI's `--stage finalize` call so the round is correctly recorded in status.md/reviews, then stop cleanly — do not dispatch the next round or batch. Calling `TaskStop` on a running Agent-mode dispatch is **forbidden**: the round is not resumable from a kill, and `discover_round` would just re-run it from scratch on the next `/mill-go` or `/mill-plan`, silently discarding the in-flight work.

## On stopping

- **mill-go session:** `Paused after [batch/review/fix description]. State is consistent. Run /mill-go to resume.`
- **mill-plan session:** `Paused after [review/fix-round description]. State is consistent. Run /mill-plan to resume.`

Write nothing to `task/status.md` or any file.
The existing phase and batch state are sufficient for resume.
