# Plan: Agent-tool dispatch discards the effort tier already encoded in mill-agents.yaml (opushigh/opusmedium/opusmax)

```yaml
task: "Agent-tool dispatch discards the effort tier already encoded in mill-agents.yaml (opushigh/opusmedium/opusmax)"
slug: "mill-agent-effort-gap"
approved: false
started: "20260725-174301"
parent: "hanf/linux-port-more"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: tier-agent-definition-files
    file: 01-tier-agent-definition-files.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-agents-defs.py
  - number: 2
    name: subagent-type-effort-wiring
    file: 02-subagent-type-effort-wiring.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-implementer-common.py test-review-prepare-envelope.py
  - number: 3
    name: merge-in-effort-forward
    file: 03-merge-in-effort-forward.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
```

## Shared Decisions

### Decision: single source of truth for tier-suffixed subagent_type

- **Decision:** `_agent_dispatch.resolve_subagent_type(base, effort)` is the ONLY place that computes a tier-suffixed `subagent_type` string (`f"{base}-{effort}"`). Every envelope-construction call site — `_implementer_common.emit_prepare` (covers implement/fix/merge-in dispatches) and each of the three review CLIs' own `--stage prepare` envelope block — calls it rather than re-implementing the string-building pattern inline.
- **Rationale:** keeps the effort-tier -> subagent_type mapping in one place. A future tier (e.g. `xhigh`) needs only a new entry in `EFFORT_TIERED_SUBAGENT_TYPES` plus matching agent-definition files, not a hunt across five call sites for a duplicated f-string.
- **Applies to:** all batches.

### Decision: unrecognized effort falls back to the base subagent_type

- **Decision:** `resolve_subagent_type` returns `base` unchanged for any `effort` value outside `{"medium", "high", "max"}`, including `None` or a future/unrecognized string. It never raises and never constructs a name for an agent-definition file that might not exist.
- **Rationale:** this fallback can never regress below today's always-base-effort behavior. Raising would turn a future catalog edit (e.g. someone adding `effort: low` to `mill-agents.yaml`) into a hard dispatch failure instead of a graceful, documented degrade. Mirrors `_mill/discussion.md`'s `subagent_type-selection` Decision.
- **Applies to:** all batches.

### Decision: `emit_prepare_no_dispatch` is out of scope

- **Decision:** `_implementer_common.emit_prepare_no_dispatch` keeps its hardcoded `subagent_type: _agent_dispatch.SUBAGENT_IMPLEMENTER` unchanged and gains no `effort` parameter.
- **Rationale:** this path only fires when `dispatch_needed: false` (verify already passed during prepare) — no Agent-tool call is ever made from this envelope, so its `subagent_type` value is inert/informational. Wiring effort through a value nothing dispatches against would be scope creep.
- **Applies to:** `subagent-type-effort-wiring` batch, Card 5.

### Decision: new agent-definition files are byte-identical to their base except name and effort

- **Decision:** the six new files under `plugins/mill/agents/` copy their base file's `description:` and entire body verbatim, character for character (including the base file's own self-referential prose, e.g. "You are a code reviewer..."). Only `name:` (set to the new filename stem) and an appended `effort: <tier>` frontmatter line differ from the base file.
- **Rationale:** matches `_mill/discussion.md`'s `tier-file-strategy` Decision — minimal diff, no behavior differs beyond the effort tier itself, and no operator-facing description text needs to explain the tier (the filename already does).
- **Applies to:** `tier-agent-definition-files` batch.

## All Files Touched

- `plugins/mill/agents/mill-implementer-high.md`
- `plugins/mill/agents/mill-implementer-max.md`
- `plugins/mill/agents/mill-implementer-medium.md`
- `plugins/mill/agents/mill-reviewer-high.md`
- `plugins/mill/agents/mill-reviewer-max.md`
- `plugins/mill/agents/mill-reviewer-medium.md`
- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-agent-dispatch.py`
- `plugins/mill/unit_tests/test-agents-defs.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-review-prepare-envelope.py`
