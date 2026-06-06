# Review: Replace subprocess LLM dispatch with the Claude Code Agent tool

```yaml
verdict: GAPS_FOUND
reviewer_model: agent-tool/general-purpose
reviewed_file: _mill/discussion.md
date: 2026-06-06
round: 3
dispatch: agent-tool (dogfooded; read-only subagent via Agent tool, orchestrator wrote this file)
```

## Findings

### [GAP] Reviewer resolver entry point does not match source
**Section:** Decisions / model-and-effort (Resolution entry point)
**Issue:** The decision told the plan author to resolve reviewers via `_reviewers.resolve_role(cfg, registry, role, scope)`, but no CLI/backend calls it (dead code); the real path is `cfg["roles"][role][scope]["reviewer"]` then `_reviewers.resolve(registry, name)` + `maybe_switch_spec_for_large_prompt` (e.g. _review_discussion.py:83-88).
**Fix:** Correct the reviewer entry point to the actual `cfg[...][reviewer]` -> `resolve(registry, name)` path; drop `resolve_role`.

### [NOTE] Merge sub-agent model-resolution path unspecified
**Section:** Decisions / model-and-effort; Scope (dispatch sites)
**Issue:** The merge sub-agent's resolver was not in the entry-point list; `millpy-merge-in-subagent.py:155` resolves `cfg.merge.model` (fallback implementer.model, default haiku) then `_reviewers.resolve`.
**Fix:** Add merge to the resolution-entry-point list with its precedence.

## Verdict

GAPS_FOUND
Reviewer resolver decision cited resolve_role, which the source never uses; corrected before planning.

---

_Resolution: both findings fixed -- verified resolve_role is uncalled in scripts (only its def remains) and merge precedence read from millpy-merge-in-subagent.py:155. The model-and-effort resolution-entry-point bullet now lists implementer/fixer, reviewers (cfg[roles][role][scope][reviewer] -> resolve + maybe_switch_spec_for_large_prompt), and merge. Re-reviewed in round 4._
