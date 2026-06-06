# Review: Replace subprocess LLM dispatch with the Claude Code Agent tool

```yaml
verdict: GAPS_FOUND
reviewer_model: agent-tool/general-purpose
reviewed_file: _mill/discussion.md
date: 2026-06-06
round: 2
dispatch: agent-tool (dogfooded; read-only subagent via Agent tool, orchestrator wrote this file)
```

## Findings

### [GAP] Scope contradicts subagent-types on agent location
**Section:** Scope (In) / Decisions / subagent-types
**Issue:** Scope said "Define two custom sub-agent types under `.claude/agents/`", but the subagent-types Decision pins them to plugin-provided `plugins/mill/agents/` and explicitly rejects `.claude/agents/`.
**Fix:** Change the Scope bullet to reference `plugins/mill/agents/` (plugin-provided).

### [NOTE] "unknown-key error" mischaracterizes _config behavior
**Section:** Decisions / dispatch-config-flag
**Issue:** `_config` unknown-key handling only emits a stderr warning, never raises; "does NOT trip the unknown-key error" implied nonexistent error-raising code.
**Fix:** Reword: the shim must suppress the generic unknown-key warning for `via_psmux` and emit its own deprecation warning.

### [NOTE] resolve() returns a spec dict, not a model string
**Section:** Decisions / model-and-effort
**Issue:** `_reviewers.resolve(...)`/`resolve_role(...)` return a spec dict; the CLIs extract `spec["model"]` (e.g. `millpy-implement.py:101`).
**Fix:** State that `prepare` reads `spec["model"]` from the resolved spec before applying the family->tier map.

## Verdict

GAPS_FOUND
Round-1 items resolved, but Scope still named the rejected `.claude/agents/` location, contradicting subagent-types.

---

_Resolution: all three findings fixed in the same revision (Scope bullet -> `plugins/mill/agents/`; dispatch-config-flag reworded to warning-suppression; model-and-effort clarified to `spec["model"]` extraction). Re-reviewed in round 3._
