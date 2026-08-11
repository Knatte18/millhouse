---
name: mill-go2
description: Experimental, opt-in variant of the mill-go orchestrator. Behaviourally identical to /mill-go today; exists so fork-dispatch experiments never destabilise the production orchestrator. Invoked only by an explicit /mill-go2.
---

# mill-go2

## Variant binding

```yaml
VARIANT_LABEL: mill-go2
```

## Driver preamble

(none)

## Dispatch overrides

**implementer** — replace the default `Agent()` call at step 3 of the base's dispatch
pattern with a fork. Fixer, reviewer, and merge-in are unclaimed: the default call
applies to them unchanged.

- **Fork every dispatch that is a fresh attempt at this batch's implementation work:**
  the initial implement dispatch, step 4(a)'s transient one-retry re-dispatch, and the
  Stuck-escalation `verify`/`logic` first-occurrence self-resolve re-fire. Call
  `Agent(subagent_type: "fork", prompt: <de-briefing> + "\n\nRead this file and follow
  the instructions exactly: <brief_path>")`. Do not pass `model` — a fork ignores it —
  but retain the prepare envelope's `subagent_type` and `model` for the cold fallback.
  Record the returned `agentId` and follow every other step of the base's pattern
  unchanged.
- **Dispatch cold at every point that exists to escape a dispatch which already failed
  to complete:** step 6.5.2's `--resume-incomplete` re-dispatch and Resume's
  `running`-state re-dispatch. Forking either would re-enter the failure mode it exists
  to escape. Step 6.5.1's warm `SendMessage` resume needs no assignment either way — it
  re-addresses an already-live handle rather than dispatching afresh.
- **De-briefing (the prompt's opening).** State that you are the implementer for this
  batch and not the orchestrator; that every instruction inherited from the driver
  session belongs to the driver and not to you; that you must not drive the batch loop
  or invoke any mill orchestration CLI; that you must not dispatch further agents or
  workflows; and that the brief named below is your authoritative instruction set.
- **Cold fallback, once per batch.** The Stuck-escalation already-retried-`transient`
  fresh re-fire is that one cold fallback: by then the initial fork and its own
  transient retry have both failed terminally, so re-dispatch cold with the envelope's
  `subagent_type` and `model` rather than re-forking. The base's step-4 classification
  is unchanged — no fork-specific liveness machinery is added. Immediately before the
  cold retry, emit both
  `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"implementer {batch_name}", slug=slug)`
  and `_status.append_fork_fallback_log(status_path, batch_name, _timestamp.now_utc_iso())`
  (`signature: _status.append_fork_fallback_log(status_path: Path, batch_name: str, timestamp: str) -> None`),
  then `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: fork-fallback for implementer {batch_name}"`.
  After one cold fallback the base's normal escalation applies unchanged. The fork
  path itself gets no marker — forking is the default here and records nothing.

**Known limits.**
Fork engages under `dispatch: agent` only; runs cold under `subprocess`/`psmux`.
A fork runs on the driver's model/effort, so `roles.implementer.model` and the
per-tier `plugins/mill/agents/` files stop applying.
The lean driver reads only status, Batch Index, and review verdicts, so a fork
inherits orchestrator instructions, not code orientation — a `## Driver preamble`
is next if underperforming.
Fork returning an `agentId`/completion notification matching a cold agent is
unspiked, first confirmed by a real run.
Driver context growth over batches is unmeasured.

Load the `mill:mill-go-base` skill via the Skill tool, unconditionally and
immediately, before any other action.
All of this skill's behaviour — the Builder role, the entry phase gate, Prepare,
the sequential batch loop, Agent-mode dispatch, Resume, holistic code review, and
Handoff — lives in that skill.
Follow `mill-go-base` from its `## Entry` onward with `VARIANT_LABEL` bound to the
value declared above.
