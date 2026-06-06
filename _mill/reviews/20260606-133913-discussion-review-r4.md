# Review: Replace subprocess LLM dispatch with the Claude Code Agent tool

```yaml
verdict: APPROVE
reviewer_model: agent-tool/general-purpose
reviewed_file: _mill/discussion.md
date: 2026-06-06
round: 4
dispatch: agent-tool (dogfooded; read-only subagent via Agent tool, orchestrator wrote this file)
```

## Findings

### [NOTE] Large-prompt switch needs rendered prompt first
**Section:** Decisions / model-and-effort
**Issue:** `maybe_switch_spec_for_large_prompt` takes `prompt_text` and fires for holistic (not batch) reviews, so `prepare` must render the brief before finalizing the model -- the doc stated both steps but not their dependency.
**Fix:** Note the switch is computed from rendered brief size and applies to holistic reviews only.

### [NOTE] Plugin agents declaration unverified in manifest
**Section:** Decisions / subagent-types
**Issue:** plugin.json has no `agents` field and `plugins/mill/agents/` does not exist yet, so the exact plugin-provided-agents convention is unconfirmed.
**Fix:** None required -- the doc already instructs the plan to confirm the plugin-manifest field/dir against the installed layout.

## Verdict

APPROVE
All codebase claims verified against source; prior-round fixes hold; only non-blocking notes remain.
