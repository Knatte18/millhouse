---
name: mill-go
description: In a spawned worktree with an approved plan, sequentially execute every batch in the plan's DAG. Per batch spawn one implementer Sonnet, run code review, loop with receive-review on REQUEST_CHANGES, halt on stuck. Hand off to mill-finalize.
---

# mill-go

## Variant binding

```yaml
VARIANT_LABEL: mill-go
```

## Driver preamble

(none)

## Dispatch overrides

(none)

Load the `mill:mill-go-base` skill via the Skill tool, unconditionally and
immediately, before any other action.
All of this skill's behaviour — the Builder role, the entry phase gate, Prepare,
the sequential batch loop, and Agent-mode dispatch — lives in that skill; Resume,
holistic code review, and Handoff are reached through its own mandatory-read
pointers.
Follow `mill-go-base` from its `## Entry` onward with `VARIANT_LABEL` bound to the
value declared above.
