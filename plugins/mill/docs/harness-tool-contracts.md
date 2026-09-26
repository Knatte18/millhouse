# Harness Tool Contracts

This file records confirmed return/notification shapes for harness tools used by mill orchestrator skills (mill-plan, mill-go).
These shapes were confirmed via live spikes and are not documented by the harness itself.
Four skill files already carry inline copies of this material, load-bearing for each one's own logic — this doc consolidates and cross-references them;
it does not replace any of them.
`orch-wait`, `orch-review` and `ask-parent` are three further consumers of this contract, referencing it rather than carrying inline copies.

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

See `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" section for the full dispatch/recovery pattern built on this contract.

## Monitor tool

The `Monitor` tool schema was directly reconfirmed via a live tool-schema read on 2026-09-23: parameters `command`/`ws`, `description`, `timeout_ms` (number, default `300000`, JSON `maximum: 3600000`, but the tool's own description states deadlines above `1800000` are capped to `1800000` — treat `1800000` as the real ceiling). There is no `persistent` parameter. This confirms the "no `persistent` parameter" claim common to ten independent field reports — GitHub issues #1058, #1062, #1066, #1067, #1078, #1085, #1088, #1096, #1100, #1108 — and supersedes this section's own prior claim (from an earlier, since-disproven 2026-09-21 read) that `persistent` existed; the five wait sections cited at the bottom of this section (the two entry-gate sections, the `orch-wait` Step 2 wait, the `orch-review` Step 2 wait, and the `ask-parent` Step 4 wait) now document the resulting design: every wait re-arms at least once whenever its configured `giveup_s` exceeds 1800s, since no `Monitor` build holds a wait open indefinitely.

A poll script run via `Monitor(command: ..., timeout_ms: 1800000, ...)`:

- Delivers ONE `<task-notification>` PER stdout line the script emits, each carrying that line's content in an `<event>` tag.
- Followed by a SEPARATE, terminal `<status>completed</status>` notification once the script's process actually exits — this one carries no `<event>` tag and no further information.
- This two-notification shape (one-per-line, then a separate event-less terminal notification) is NOT the same shape as `Agent`'s single combined-result notification.
  Do not conflate the two when writing a new entry-gate wait or similar poll-and-notify pattern.
- Runs bash, not PowerShell, regardless of the operator's terminal — see `cli/SKILL.md`.
- An expiry with no `<event>` content (a notification whose payload is neither `READY` nor a `TIMEOUT after ...` line) fires whenever the poll script is still running when `Monitor`'s `timeout_ms` cap is reached — expected for any wait exceeding 30 minutes, not build-specific. All five wait sections below re-arm on this outcome, recomputing the remaining budget from wall-clock elapsed time rather than restarting it.

See `mill-go-base/SKILL.md`'s "### Entry-gate wait for upstream mill-plan" section and `mill-plan/SKILL.md`'s "### Entry-gate wait for upstream mill-start" section, `orch-wait/SKILL.md`'s Step 2, and `orch-review/SKILL.md`'s Step 2 (tracking `wait_started_epoch` and `task_id` per slug), and `ask-parent/SKILL.md`'s Step 4 for five consumers of this contract.

## SendMessage to a peer session

- Verified: `ListAgents` in a live session lists peer local Claude sessions by name (the orchestrator session appeared as `MH:orch`), so a named peer is addressable for an outbound `SendMessage(to: <name>, message: ...)`.
- Unverified: whether a message wakes an idle peer session promptly, and whether a woken session can be held open with a timeout.
- Unverified: whether name lookup is case-sensitive.
  `_vscode_tasks.session_prefix` lower-cases the names it assembles (e.g. `mh:orch`) while `ListAgents` listed `MH:orch`, so a spawner passing a differently-cased `--parent` value can surface as the unreachable fallback.
- Design consequence: `ask-parent` never relies on a reply message.
  It treats a `SendMessage` error as "parent unreachable" and receives the answer as a file polled by `Monitor`, so the timeout bounds every unverified case.
