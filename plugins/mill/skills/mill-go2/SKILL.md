---
name: mill-go2
description: Experimental, opt-in variant of the mill-go orchestrator. Forks the fixer role instead of dispatching it cold; otherwise identical to /mill-go, so fork-dispatch experiments never destabilise the production orchestrator. Invoked only by an explicit /mill-go2.
---

# mill-go2

## Variant binding

```yaml
VARIANT_LABEL: mill-go2
```

## Driver preamble

(none)

## Dispatch overrides

### fixer

Governs the **first** fixer dispatch per scope/round.
`fork_attempted` is true when this session already forked this scope+round, or
`_status.read_fixer_fork_fallback_log(status_path)` has a row for it; then
(incl. step 3's re-dispatch) use the default `Agent()` call (envelope's own
`subagent_type`/`model`).

Otherwise: `Agent(subagent_type: "fork", prompt: "Read this file and follow the
instructions exactly: <brief_path>")`. Omit `model`/`isolation` -- a fork runs on
the driver's model regardless and must commit in the real worktree.

On the first terminal failure (base step 3), record the fallback and re-dispatch
cold, consuming the retry budget:

- `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"fixer {scope} r{N}", slug=slug)`
- `_status.append_fixer_fork_fallback_log(status_path, scope, N, _timestamp.now_utc_iso())`
- `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: fork-fallback for fixer {scope} r{N}"`

Commit **before** the cold retry -- resume reconstructs `fork_attempted` from it;
`{scope}` is the batch name, or `holistic`.

Risks: inherits the driver's broader tool grant (scope discipline still comes
from the brief/`scope_violations`); forfeits `roles.fixer.model` -- drive from
a solid model tier.

**implementer** — replace the default `Agent()` call at step 2 with a fork.
Reviewer/merge-in unclaimed (default call applies unchanged).

- **Fork every fresh attempt:** initial dispatch, step 3(a)'s transient
  re-dispatch, and the Stuck-escalation `verify`/`logic` self-resolve re-fire --
  `Agent(subagent_type: "fork", prompt: <de-briefing> + "\n\nRead this file and
  follow the instructions exactly: <brief_path>")`. Omit `model` (ignored);
  keep the envelope's `subagent_type`/`model` for the cold fallback. Record
  `agentId`.
- **Dispatch cold to escape a failed dispatch:** step 5.5.2's
  `--resume-incomplete` and Resume's `running`-state re-dispatch stay cold.
  5.5.1's warm `SendMessage` resume needs no assignment (already live).
- **De-briefing (prompt opening):** you are the implementer, not the orchestrator;
  inherited instructions belong to the driver, not you; do not drive the batch
  loop, invoke CLIs, or dispatch agents/workflows; the brief is authoritative.
- **Cold fallback, once per batch:** the already-retried-`transient`
  Stuck-escalation re-fire is the fallback -- re-dispatch cold (envelope
  `subagent_type`/`model`), not another fork. Before it:
  `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"implementer {batch_name}", slug=slug)`,
  `_status.append_fork_fallback_log(status_path, batch_name, _timestamp.now_utc_iso())`,
  `git -C <worktree> add <status_path> && git -C <worktree> commit -m
  "<VARIANT_LABEL>: fork-fallback for implementer {batch_name}"`. Normal
  escalation applies; forking gets no marker.

**Known limits.** Runs on the driver's model, so `roles.implementer.model`
and per-tier agent files stop applying. The lean driver reads only status,
Batch Index, and review verdicts -- a fork inherits orchestrator instructions,
not code orientation (`## Driver preamble` next if underperforming).

Load the `mill:mill-go-base` skill via the Skill tool, unconditionally and
immediately, before any other action.
All of this skill's behaviour — the Builder role, the entry phase gate, Prepare,
the sequential batch loop, and Agent-mode dispatch — lives in that skill; Resume,
holistic code review, and Handoff are reached through its own mandatory-read
pointers.
Follow `mill-go-base` from its `## Entry` onward with `VARIANT_LABEL` bound to the
value declared above.
