# Discussion: Fix agent-dispatch prepare stage to emit namespaced subagent_type

```yaml
task: Fix agent-dispatch prepare stage to emit namespaced subagent_type
slug: agent-dispatch-namespace-fix
status: discussing
parent: main
```

## Problem

The `SUBAGENT_REVIEWER` and `SUBAGENT_IMPLEMENTER` constants in `_agent_dispatch.py` use bare agent names (`"mill-reviewer"`, `"mill-implementer"`). The Agent tool's `subagent_type` parameter requires plugin-namespaced names (`"mill:mill-reviewer"`, `"mill:mill-implementer"`) — formed by prefixing the plugin's `name` field from `plugin.json` (`"mill"`) with a colon. Without the namespace prefix, Claude Code cannot resolve which plugin owns the agent, causing agent-mode dispatch to fail silently or error on every review and implement invocation.

Additionally, `_implementer_common.py` hardcodes the string `"mill-implementer"` directly in `emit_prepare` and `emit_prepare_no_dispatch` instead of referencing `SUBAGENT_IMPLEMENTER`, so fixing the constant alone is insufficient — both sites must be corrected.

## Scope

**In:**
- `plugins/mill/scripts/_agent_dispatch.py` — update `SUBAGENT_REVIEWER` and `SUBAGENT_IMPLEMENTER` constants to namespaced values; update docstring examples
- `plugins/mill/scripts/_implementer_common.py` — replace hardcoded `"mill-implementer"` in `emit_prepare` (line 118) and `emit_prepare_no_dispatch` (line 155) with `_agent_dispatch.SUBAGENT_IMPLEMENTER`; add import if not already present
- `plugins/mill/unit_tests/test-agent-dispatch.py` — update `test_subagent_constants()` expected values to `"mill:mill-reviewer"` and `"mill:mill-implementer"`
- `plugins/mill/unit_tests/test-implementer-common.py` — update assertion at line 419 to `"mill:mill-implementer"`
- `plugins/mill/skills/mill-go/SKILL.md` — update line 113 documentation example to show namespaced values

**Out:**
- `plugins/mill/agents/mill-reviewer.md` and `mill-implementer.md` — the `name:` frontmatter field is the agent's own identity, not a dispatch reference; stays as-is
- `millpy-review-discussion.py`, `millpy-review-code.py`, `millpy-review-plan.py` — already reference `SUBAGENT_REVIEWER` constant; inherit the fix automatically, no direct edits needed
- `millpy-implement.py` and `millpy-fix.py` — call `emit_prepare` from `_implementer_common.py`; inherit the fix from there
- `test-agents-defs.py` — validates agent definition file `name:` fields, which are correct and unchanged

## Decisions

### Use constant in emit_prepare

- Decision: Import and use `_agent_dispatch.SUBAGENT_IMPLEMENTER` in `_implementer_common.py` instead of the hardcoded string `"mill-implementer"`.
- Rationale: Eliminates a duplicate string that diverges independently from the constant. The constant is the single source of truth.
- Rejected: Fix the string value in place but leave hardcoding. Creates future drift risk if the constant is ever changed again.

### Fix both emit_prepare variants

- Decision: Apply the constant fix to both `emit_prepare` and `emit_prepare_no_dispatch`.
- Rationale: Both functions populate the `subagent_type` field in the prepare envelope. Fixing only one leaves the no-dispatch variant broken for any flow that calls it.
- Rejected: Fix only `emit_prepare`. Incomplete — `emit_prepare_no_dispatch` also emits `subagent_type`.

### Update SKILL.md documentation

- Decision: Update `mill-go/SKILL.md` line 113 to show namespaced values.
- Rationale: Documentation that diverges from runtime behavior creates confusion when diagnosing dispatch failures. The SKILL is the operator's reference for what values to expect in the prepare envelope.
- Rejected: Leave documentation stale. Stale docs cause operators to emit wrong values in manual intervention scenarios.

## Technical context

**Key files:**
- `plugins/mill/scripts/_agent_dispatch.py` — defines `SUBAGENT_REVIEWER = "mill-reviewer"` and `SUBAGENT_IMPLEMENTER = "mill-implementer"` at lines 35–36. Also exports `write_brief`, `resolve_dispatch_mode`, `model_to_tier`.
- `plugins/mill/scripts/_implementer_common.py` — `emit_prepare` (line 100) and `emit_prepare_no_dispatch` (line 129) print prepare JSON envelopes. Both hardcode `"mill-implementer"` at lines 118 and 155 respectively.
- `plugins/mill/.claude-plugin/plugin.json` — `"name": "mill"` establishes the namespace prefix used by Claude Code to qualify agent names.
- `plugins/mill/agents/mill-reviewer.md` / `mill-implementer.md` — agent definition files with `name: mill-reviewer` / `name: mill-implementer` in frontmatter. These names are correct — they are the agents' own identities. The dispatch reference is a separate concern.

**Import situation in `_implementer_common.py`:** `_agent_dispatch` is already imported at line 4 of `_implementer_common.py`. The fix only needs to replace the two hardcoded string literals with `_agent_dispatch.SUBAGENT_IMPLEMENTER`.

**No other callers emit `subagent_type` directly** — all review CLIs already go through the `SUBAGENT_REVIEWER` constant. The only bare-string sites are in `_implementer_common.py`.

**mill-go SKILL.md context:** Line 113 documents what values the SKILL should expect in the `subagent_type` field of the prepare envelope. It reads: `one of "mill-implementer" or "mill-reviewer"`. This must be updated to `"mill:mill-implementer"` and `"mill:mill-reviewer"`.

## Testing

The existing unit-test suite covers the affected constants and the `emit_prepare` output. Update expected values in two tests; no new test cases are required.

**`test-agent-dispatch.py`** — `test_subagent_constants()` asserts `SUBAGENT_REVIEWER == "mill-reviewer"` and `SUBAGENT_IMPLEMENTER == "mill-implementer"`. Update both to namespaced values.

**`test-implementer-common.py`** — Case 12 asserts `data["subagent_type"] == "mill-implementer"` on the `emit_prepare` output (line 419). Update to `"mill:mill-implementer"`. Case 14 (`emit_prepare_no_dispatch`) has no `subagent_type` assertion; add `assert data["subagent_type"] == "mill:mill-implementer"` there so the no-dispatch path is also covered after the fix.

Verify command: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`

## Q&A log

- **Q:** Should `_implementer_common.py:emit_prepare` use `_agent_dispatch.SUBAGENT_IMPLEMENTER` instead of the hardcoded string? **A:** [auto-pick] Yes, import and use the constant. **Why:** Eliminates duplicate-string drift; constant is the single source of truth.
- **Q:** Should both `emit_prepare` and `emit_prepare_no_dispatch` be fixed? **A:** [auto-pick] Yes, both variants use the constant. **Why:** Both populate `subagent_type`; fixing only one leaves the other broken.
- **Q:** Should `mill-go/SKILL.md` be updated to show namespaced values? **A:** [auto-pick] Yes, keep docs in sync. **Why:** Docs diverging from code cause confusion when debugging dispatch failures.
