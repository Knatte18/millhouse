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

(none)

Load the `mill:mill-go-base` skill via the Skill tool, unconditionally and
immediately, before any other action.
All of this skill's behaviour — the Builder role, the entry phase gate, Prepare,
the sequential batch loop, Agent-mode dispatch, Resume, holistic code review, and
Handoff — lives in that skill.
Follow `mill-go-base` from its `## Entry` onward with `VARIANT_LABEL` bound to the
value declared above.
