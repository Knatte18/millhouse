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

Governs the **first** fixer dispatch per scope and round only.
`fork_attempted` is true when this session already forked a fixer for that scope
and round, or when `_status.read_fork_fallback_log(status_path)` returns a row for
them; when it is true -- including step 4's re-dispatch -- use the default
`Agent()` call with the envelope's own `subagent_type` and `model`.

Otherwise dispatch `Agent(subagent_type: "fork", prompt: "Read this file and
follow the instructions exactly: <brief_path>")`.
Omit `model` and `isolation`: a fork runs on the driver's model regardless, and
the fixer must commit in the real worktree.
The brief stays the contract; inherited context never replaces reading it.

On the first terminal failure classification under the base's step 4, record the
fallback and re-dispatch cold, consuming the existing one-retry budget:

- `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"fixer {scope} r{N}", slug=slug)`
- `_status.append_fork_fallback_log(status_path, scope, N, _timestamp.now_utc_iso())`
- `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: fork-fallback for fixer {scope} r{N}"`

Commit that row **before** the cold retry -- a resumed session reconstructs
`fork_attempted` from it. `{scope}` is the batch name, or `holistic`.

Risks: a fork inherits the driver's broader tool grant (scope discipline still
comes from the brief and finalize's `scope_violations` gate), and forfeits
`roles.fixer.model` -- drive this variant from a solid model tier.

Load the `mill:mill-go-base` skill via the Skill tool, unconditionally and
immediately, before any other action.
All of this skill's behaviour — the Builder role, the entry phase gate, Prepare,
the sequential batch loop, Agent-mode dispatch, Resume, holistic code review, and
Handoff — lives in that skill.
Follow `mill-go-base` from its `## Entry` onward with `VARIANT_LABEL` bound to the
value declared above.
