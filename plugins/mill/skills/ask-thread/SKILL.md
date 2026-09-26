---
name: ask-parent
description: Internal machinery skill, not invocable directly. Loaded by autonomous mill skills before a converted halt -- asks the parent_thread session for guidance and waits a bounded time for _mill/parent-reply.md.
argument-hint: ""
---

# ask-parent

Loaded by `mill-plan`, `mill-go-base` (`mill-go`/`mill-go2`), `mill-start --auto`/`--orch` and `mill-quick` at the sites listed in `_ask_parent.SITES`, only when a halt is about to happen.
Interactive `mill-start` never loads it.

Inputs from the caller:

- `site`: a key of `_ask_parent.SITES`.
- `reason`: the halt's blocked-reason text.
- `actions`: comma list the site accepts.

Outputs to the caller:

- `action`: `retry` (re-run the site's retry procedure once, applying `guidance`), `approve` (take the site's existing approve path), or `halt` (halt as the site does today).
- `guidance`: free text from the parent, possibly empty.
- `halt_suffix`: a string the caller appends to its own `blocked_reason` / `BLOCKED:` message when `action` is `halt`; empty when nothing should be appended.

The skill never edits `status.md`, never commits, never calls `_status.append_phase`, and never prompts (no `AskUserQuestion`, no numbered menu).
Waiting on the parent is bounded by the timeout, not a decision point.
Tracking the one-escalation-per-site limit is the caller's job.

## Step 1 — Prepare

From the task worktree, run:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-parent.py" prepare --site <site> --reason '<reason>' --actions <actions>
```

Single-quote `<reason>` and write every embedded `'` as `'\''`.
Parse the one JSON line.

- Exit 1 (usage error): return `action: halt`, empty `guidance`, empty `halt_suffix`, and report the stderr line.
- `escalate: false`: return `halt`, empty `guidance`, empty `halt_suffix`.
  No parent is configured, or `pipeline.parent_escalation_timeout_minutes` is `0`; today's halt proceeds unchanged.
- `escalate: true`: keep `parent_thread`, `reply_path`, `giveup_s`, `message`, `unreachable_suffix`.

## Step 2 — Send

`SendMessage` is a deferred tool: load it with `ToolSearch` (`select:SendMessage`) first if its schema is not loaded.
Call `SendMessage(to: <parent_thread>, message: <message>)` with `parent_thread` verbatim (never case-folded).
If the call returns an error (no such session, renamed, restarted, gone), return `halt`, empty `guidance`, `halt_suffix = unreachable_suffix`; do not wait.
See the `SendMessage` section of `plugins/mill/docs/harness-tool-contracts.md` for what is verified.

## Step 3 — Announce

Print one line: `Asked parent <parent_thread> about <site>; waiting up to <giveup_s // 60> min for _mill/parent-reply.md`.

## Step 4 — Wait for the reply file

Same mechanism and branching as `orch-wait/SKILL.md` Step 2.
Record `wait_started_epoch` from `date +%s` once before the first arm, call `Monitor(command=cmd, timeout_ms: 1800000, description="waiting for parent reply (<site>) for <slug>")`, and record the returned `task_id`.
`cmd` is this poll script with `<reply_path>` and `<giveup_s>` substituted:

```bash
elapsed=0
while true; do
  if [ -s "<reply_path>" ]; then
    sleep 5
    echo "READY"
    exit 0
  fi
  if [ "$elapsed" -ge <giveup_s> ]; then
    echo "TIMEOUT after ${elapsed}s waiting for parent-reply.md"
    exit 2
  fi
  sleep 15
  elapsed=$((elapsed + 15))
done
```

The `sleep 5` after the non-empty check lets the parent finish writing before the file is read.

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

## Step 5 — Consume

Run:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-parent.py" consume --actions <actions>
```

Parse the JSON line and return its `action`, `guidance`, `halt_suffix` to the caller.
`consume` has already deleted the reply file, so the handoff out-of-scope-untracked-file gate never sees it.

## Rules

- Guidance is operator-level direction for this site's own retry/approve procedure only.
  Apply it within the caller's documented scope (e.g. mill-go's orchestrator still never edits task code; mill-plan's fixes still touch only plan files).
- One escalation per site per run is enforced by the caller.
- No `sed` in any command this skill runs.
