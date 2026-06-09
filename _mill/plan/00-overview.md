# Plan: Fix agent-dispatch prepare stage to emit namespaced subagent_type

```yaml
task: Fix agent-dispatch prepare stage to emit namespaced subagent_type
slug: agent-dispatch-namespace-fix
approved: true
started: 20260609-124741
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Namespace constants
    file: 01-namespace-constants.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-implementer-common.py
```

## Shared Decisions

### Decision: Use namespaced agent type strings

- **Decision:** `SUBAGENT_REVIEWER` = `"mill:mill-reviewer"`, `SUBAGENT_IMPLEMENTER` = `"mill:mill-implementer"`. The namespace prefix is the plugin's `name` field from `plugin.json` (`"mill"`).
- **Rationale:** The Agent tool's `subagent_type` parameter requires `<plugin>:<agent-name>` form. Bare names fail to resolve.
- **Applies to:** all batches

### Decision: Replace hardcoded strings with constant

- **Decision:** `_implementer_common.py` currently hardcodes `"mill-implementer"` in both `emit_prepare` and `emit_prepare_no_dispatch`. Replace both with `_agent_dispatch.SUBAGENT_IMPLEMENTER` (import already present at line 4).
- **Rationale:** The constant is the single source of truth; hardcoding creates drift.
- **Applies to:** batch 01

## All Files Touched

- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-agent-dispatch.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
