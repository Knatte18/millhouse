---
name: ask-thread
description: Ask another Claude session. Automatic mode -- loaded by autonomous mill skills before a converted halt, asks the parent_thread session for retry/approve/halt. Direct mode -- /ask-thread [thread-name] routes this session's operator questions to that session (default parent_thread). Waits a bounded time for a reply message or _mill/ask-reply.md.
argument-hint: "[thread-name]"
---

# ask-thread

Asks a named Claude session and waits a bounded time for its answer.
Two modes share one send/wait/consume mechanism (Steps 0-5).

## Automatic mode

Loaded by `mill-plan`, `mill-go-base` (`mill-go`/`mill-go2`), `mill-start --auto`/`--orch` and `mill-quick` at the sites listed in `_ask_thread.SITES`, only when a halt is about to happen.
Interactive `mill-start` never loads it.
The target is always `parent_thread`.

Inputs from the caller:

- `site`: a key of `_ask_thread.SITES`.
- `reason`: the halt's blocked-reason text.
- `actions`: comma list the site accepts.

Outputs to the caller:

- `action`: `retry` (re-run the site's retry procedure once, applying `guidance`), `approve` (take the site's existing approve path), or `halt` (halt as the site does today).
- `guidance`: free text from the target, possibly empty.
- `halt_suffix`: a string the caller appends to its own `blocked_reason` / `BLOCKED:` message when `action` is `halt`; empty when nothing should be appended.

The skill never edits `status.md`, never commits, never calls `_status.append_phase`, and never prompts (no `AskUserQuestion`, no numbered menu).
Waiting on the target is bounded by the timeout, not a decision point.
Tracking the one-escalation-per-site limit is the caller's job.

## Direct mode

Invoked as `/ask-thread [thread-name]` by the operator or another agent.
Run once:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-thread.py" resolve [--to '<thread-name>']
```

- Exit 1: tell the user direct mode needs a mill task worktree (this includes the hub orch session) and stop.
- `target: null`: tell the user direct mode cannot start (no thread name and no `parent_thread`) and stop.
- Otherwise remember `target`, run Step 0 once, and print one line that direct mode is on and questions go to `<target>`.

Direct mode lasts for the rest of the session until it ends or the operator says stop, and binds skills loaded before or after it.
Whenever the session would ask the operator a question (a `mill:conversation` numbered-options menu, a free-text question in prose, or `AskUserQuestion` from a non-mill skill), send the questions to the target instead, in batches of at most 5 (Steps 1-5).
Each question is numbered, numbers continue across batches for the whole session, and each carries the asker's recommended answer first and lists the alternatives.

Harness permission prompts are not covered.
There is no hook or flag; the rule lives in this loaded skill only.

Automatic-mode halt sites in the same session still run automatic mode.
Under `--auto`/`--orch` nothing is asked of the operator, so direct mode routes nothing there.

Fallback (prepare exit 1, `SendMessage` error, empty or timed-out reply): ask the operator directly with the same numbered questions.

## Step 0 — Tools and own name

Load with `ToolSearch` (`select:` listing only the missing ones among `SendMessage`, `ListAgents`, `Monitor`) any whose schema is not loaded.
Call `ListAgents`; take `reply_to` from the first line `This session is <name> [<id>] ...` (the text between `This session is ` and ` [`).
If `ToolSearch` has no match, the call errors, or no such line exists, omit `--reply-to`.
Never use `TaskStop`.

## Step 1 — Prepare

Automatic mode, from the task worktree:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-thread.py" prepare --site <site> --reason '<reason>' --actions <actions> [--reply-to '<reply_to>']
```

Single-quote `<reason>` and write every embedded `'` as `'\''`.
Parse the one JSON line.

- Exit 1 (usage error): return `action: halt`, empty `guidance`, empty `halt_suffix`, and report the stderr line.
- `escalate: false`: return `halt`, empty `guidance`, empty `halt_suffix`.
  No parent is configured, or `pipeline.parent_escalation_timeout_minutes` is `0`; today's halt proceeds unchanged.
- `escalate: true`: keep `target`, `ask_id`, `reply_path`, `giveup_s`, `message`, `unreachable_suffix`.

Direct mode: write the batch's questions with the Write tool to `.scratch/ask-thread-questions.md` in the task worktree (overwrite; not committed), then run:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-thread.py" prepare --questions-file .scratch/ask-thread-questions.md --to '<target>' [--reply-to '<reply_to>']
```

Exit 1: direct-mode fallback.

## Step 2 — Send

Call `SendMessage(to: <target>, message: <message>)` with `target` verbatim, never case-folded, and no retry with another casing.
On error (no such session, renamed, restarted, gone): automatic mode returns `halt`, empty `guidance`, `halt_suffix = unreachable_suffix`, and does not wait; direct mode uses the fallback.
See the `SendMessage` section of `plugins/mill/docs/harness-tool-contracts.md` for what is verified.

## Step 3 — Announce

Print one line.
Automatic: `Asked <target> about <site>; waiting up to <giveup_s // 60> min for a reply (message or _mill/ask-reply.md)`.
Direct: `Asked <target> questions <first>-<last>; waiting up to <giveup_s // 60> min for a reply (message or _mill/ask-reply.md)`.

## Step 4 — Wait

Same mechanism and branching as `orch-wait/SKILL.md` Step 2.
Record `wait_started_epoch` from `date +%s` once before the first arm, call `Monitor(command=cmd, timeout_ms: 1800000, description="waiting for ask-thread reply (<site or direct>) for <slug>")`, and record the returned `task_id`.
`cmd` is this poll script with `<reply_path>`, `<ask_id>` and `<giveup_s>` substituted:

```bash
elapsed=0
while true; do
  if awk 'NF{print; exit}' "<reply_path>" 2>/dev/null | grep -qxE "ask-id: <ask_id>[[:space:]]*"; then
    sleep 5
    echo "READY"
    exit 0
  fi
  if [ "$elapsed" -ge <giveup_s> ]; then
    echo "TIMEOUT after ${elapsed}s waiting for ask-reply.md"
    exit 2
  fi
  sleep 15
  elapsed=$((elapsed + 15))
done
```

The `sleep 5` after the match lets the target finish writing before the file is read.

Branching:

- `READY`: Step 5.
- `TIMEOUT after <N>s ...`: Step 5.
  A missing file reads as `halt`; a reply that landed at the last moment is still honoured.
- Any other event content is an early `Monitor` expiry.
  Compute `remaining_s = giveup_s - (now - wait_started_epoch)` from a fresh `date +%s`.
  `remaining_s <= 0`: Step 5.
  Otherwise re-arm with `<giveup_s>` replaced by `remaining_s`, record the new `task_id`, and keep waiting.
- A harness-level stop of the recorded `task_id`: Step 5.

The second, event-less `<status>completed</status>` notification needs no branch (see `plugins/mill/docs/harness-tool-contracts.md`).

Message handling: when a message from the target arrives while waiting, check its first non-empty line for `ask-id: <ask_id>`.

- No match: ignore it and keep waiting (re-arm per the expiry rules if the Monitor already expired).
- Match: unless the reply file's first non-empty line already is the matching `ask-id` line (the file wins), write the message text verbatim to `reply_path` with the Write tool.
  Never cancel the Monitor; the running poll sees the file on its next tick and ends with `READY`, then Step 5.
  If no Monitor is armed at that moment, go to Step 5 directly.

After Step 5, ignore any later event from an earlier `task_id` of this batch.

## Step 5 — Consume

Automatic mode:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-thread.py" consume --ask-id <ask_id> --actions <actions>
```

Parse the JSON line and return its `action`, `guidance`, `halt_suffix` to the caller.

Direct mode:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-thread.py" consume --ask-id <ask_id> --open
```

A non-empty `reply` is the decision for this batch and the session continues.
An empty `reply` or exit 1: fallback.

`consume` deletes the reply file on every path, so the handoff out-of-scope-untracked-file gate never sees it.

## Rules

- Guidance is operator-level direction for this site's own retry/approve procedure only.
  Apply it within the caller's documented scope (e.g. mill-go's orchestrator still never edits task code; mill-plan's fixes still touch only plan files).
- One escalation per site per run is enforced by the caller.
- No `sed` in any command this skill runs.
