# Harness Tool Contracts

This file records confirmed return/notification shapes for harness tools used by mill orchestrator skills (mill-plan, mill-go).
These shapes were confirmed via live spikes and are not documented by the harness itself.
Four skill files already carry inline copies of this material, load-bearing for each one's own logic — this doc consolidates and cross-references them;
it does not replace any of them.
`orch-wait`, `orch-review` and `ask-thread` are three further consumers of this contract, referencing it rather than carrying inline copies.

---

## Agent tool

A background subagent dispatched via `Agent(subagent_type: ..., model: ..., prompt: ...)`:

- Returns immediately with a launch acknowledgement carrying an `agentId` — the harness runtime handle for the live subagent.
  Retain it: it is what `SendMessage`/`TaskOutput` address to warm-resume or probe the same session.
- Delivers two separate events when a background subagent finishes, is stopped, or is interrupted:
  1. A SubagentHandback message from the `agentId`, carrying the subagent's final report text. In every reported run it arrives before the notification.
  2. The `<task-notification>`, whose `<result>` may carry only a pointer saying the report was delivered as a message. Agent-tool `<task-notification>`s always carry a `<status>` tag, with `completed` for clean success and other values (`failed`, `stopped`, `interrupted`) for everything else, alongside the existing message-text-based signals.
- The notification payload is a fallback report source only: use it when no hand-back message was received and the payload is non-empty.
- A background agent IS a detached worker and CAN be stopped or interrupted independently of the orchestrator;
  a stopped/ interrupted notification can be stale (an agent reported "killed" can still be running and deliver a real completion notification later).
  Probe with `TaskOutput(task_id: <agentId>, block: false)` before trusting a stop/interrupt notification as terminal.
- `agentId` is distinct from any LLM-conversation `session_id` / `implementer_session` recorded in `status.md` — the former is the harness worker handle, the latter identifies the LLM conversation for finalize/cleanup purposes.

See `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" section for the full dispatch/recovery pattern built on this contract.

## Monitor tool

The `Monitor` tool schema was directly reconfirmed via a live tool-schema read on 2026-09-23: parameters `command`/`ws`, `description`, `timeout_ms` (number, default `300000`, JSON `maximum: 3600000`, but the tool's own description states deadlines above `1800000` are capped to `1800000` — treat `1800000` as the real ceiling). There is no `persistent` parameter. This confirms the "no `persistent` parameter" claim common to ten independent field reports — GitHub issues #1058, #1062, #1066, #1067, #1078, #1085, #1088, #1096, #1100, #1108 — and supersedes this section's own prior claim (from an earlier, since-disproven 2026-09-21 read) that `persistent` existed; the five wait sections cited at the bottom of this section (the two entry-gate sections, the `orch-wait` Step 2 wait, the `orch-review` Step 2 wait, and the `ask-thread` Step 4 wait) now document the resulting design: every wait re-arms at least once whenever its configured `giveup_s` exceeds 1800s, since no `Monitor` build holds a wait open indefinitely.

A poll script run via `Monitor(command: ..., timeout_ms: 1800000, ...)`:

- Delivers ONE `<task-notification>` PER stdout line the script emits, each carrying that line's content in an `<event>` tag.
- Followed by a SEPARATE, terminal `<status>completed</status>` notification once the script's process actually exits — this one carries no `<event>` tag and no further information.
- This two-notification shape (one-per-line, then a separate event-less terminal notification) is NOT the same shape as `Agent`'s single combined-result notification.
  Do not conflate the two when writing a new entry-gate wait or similar poll-and-notify pattern.
- Runs bash, not PowerShell, regardless of the operator's terminal — see `cli/SKILL.md`.
- An expiry with no `<event>` content (a notification whose payload is neither `READY` nor a `TIMEOUT after ...` line) fires whenever the poll script is still running when `Monitor`'s `timeout_ms` cap is reached — expected for any wait exceeding 30 minutes, not build-specific. All five wait sections below re-arm on this outcome, recomputing the remaining budget from wall-clock elapsed time rather than restarting it.

See `mill-go-base/SKILL.md`'s "### Entry-gate wait for upstream mill-plan" section and `mill-plan/SKILL.md`'s "### Entry-gate wait for upstream mill-start" section, `orch-wait/SKILL.md`'s Step 2, and `orch-review/SKILL.md`'s Step 2 (tracking `wait_started_epoch` and `task_id` per slug), and `ask-thread/SKILL.md`'s Step 4 (Wait) for five consumers of this contract.

## SendMessage to a peer session

- Verified: `ListAgents` in a live session lists peer local Claude sessions by name (the orchestrator session appeared as `MH:orch`), so a named peer is addressable for an outbound `SendMessage(to: <name>, message: ...)`.
- Verified: on 2026-09-26 `ListAgents`' first output line was `This session is <name> [<id>] ...` (e.g. `This session is mh:ask-thread-skill:start [68784b]`), which is how `ask-thread` learns its own name for `--reply-to`.
- Verified (user report, 2026-09-26): a `SendMessage` to an idle peer session is delivered and wakes it, as long as the peer is listed by `ListAgents`.
  `orch-wait` Step 1 relies on this for its one-way "discussion.md is ready" notification to `parent_thread`.
- Unverified: whether a woken session can be held open with a timeout.
- Unverified: whether name lookup is case-sensitive.
  `_vscode_tasks.session_prefix` lower-cases the names it assembles (e.g. `mh:orch`) while `ListAgents` listed `MH:orch`, so a spawner passing a differently-cased `--parent` value can surface as the unreachable fallback.
- Design consequence: `ask-thread` asks the target to reply with one `SendMessage` and always to write the reply file too.
  A matching reply message is written into the reply file and ends the wait early, while the `Monitor` poll on the file plus the timeout bound every unverified case; a `SendMessage` error is "target unreachable".
