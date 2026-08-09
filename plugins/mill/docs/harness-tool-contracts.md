# Harness Tool Contracts

This file records confirmed return/notification shapes for harness tools used by mill orchestrator skills (mill-plan, mill-go).
These shapes were confirmed via live spikes and are not documented by the harness itself.
Four skill files already carry inline copies of this material, load-bearing for each one's own logic — this doc consolidates and cross-references them;
it does not replace any of them.

---

## Agent tool

A background subagent dispatched via `Agent(subagent_type: ..., model: ..., prompt: ...)`:

- Returns immediately with a launch acknowledgement carrying an `agentId` — the harness runtime handle for the live subagent.
  Retain it: it is what `SendMessage`/`TaskOutput` address to warm-resume or probe the same session.
- Delivers exactly ONE combined-result `<task-notification>` when the subagent finishes, is stopped, or is interrupted — the notification payload carries the subagent's final message text. Agent-tool `<task-notification>`s also carry a `<status>` tag, with `completed` for clean success and other values (`failed`, `stopped`, `interrupted`) for everything else, alongside the existing message-text-based signals.
- A background agent IS a detached worker and CAN be stopped or interrupted independently of the orchestrator;
  a stopped/ interrupted notification can be stale (an agent reported "killed" can still be running and deliver a real completion notification later).
  Probe with `TaskOutput(task_id: <agentId>, block: false)` before trusting a stop/interrupt notification as terminal.
- `agentId` is distinct from any LLM-conversation `session_id` / `implementer_session` recorded in `status.md` — the former is the harness worker handle, the latter identifies the LLM conversation for finalize/cleanup purposes.

See `mill-go/SKILL.md`'s "## Agent-mode dispatch" section for the full dispatch/recovery pattern built on this contract.

## Monitor tool

A poll script run via `Monitor(command: ..., persistent: true, ...)`:

- Delivers ONE `<task-notification>` PER stdout line the script emits, each carrying that line's content in an `<event>` tag.
- Followed by a SEPARATE, terminal `<status>completed</status>` notification once the script's process actually exits — this one carries no `<event>` tag and no further information.
- This two-notification shape (one-per-line, then a separate event-less terminal notification) is NOT the same shape as `Agent`'s single combined-result notification.
  Do not conflate the two when writing a new entry-gate wait or similar poll-and-notify pattern.
- Runs bash, not PowerShell, regardless of the operator's terminal — see `cli/SKILL.md`.

See `mill-go/SKILL.md`'s "### Entry-gate wait for upstream mill-plan" section and `mill-plan/SKILL.md`'s "### Entry-gate wait for upstream mill-start" section for two independent consumers of this contract.
