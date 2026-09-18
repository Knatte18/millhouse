MILL_REVIEW_BEGIN
# Review: mill-start Explore: Agent(subagent_type: fork) dispatch fails to perform assigned investigation

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (model ID claude-sonnet-5, per environment metadata)
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:consistency] Testing section's verify guidance risks tripping its own validator
**Section:** Testing **Issue:** "plan's batch, if any, should mark verification as a manual read-through rather than a `PYTHONPATH=` test invocation" is ambiguous about *how* to mark it. Verified against `_plan_dag.parse_verify_field` and `_plan_validate._check_verify_not_isolated`: only an absent/null/blank `verify:` field returns `command=None` and skips the PYTHONPATH= check ("the common case for pure-docs batches" per that function's own docstring); any non-blank string value (e.g. literally `verify: "manual read-through"`) is treated as a real command and, since this repo is a Python project (`plugins/mill/pyproject.toml`), gets flagged by `verify-not-isolated` for missing the `PYTHONPATH=` prefix — CLAUDE.md confirms mill-plan then auto-prepends the prefix on validator failure, producing a nonsensical `PYTHONPATH= manual read-through` artifact. **Fix:** State explicitly that the batch should leave `verify:` absent/null rather than writing any descriptive string, matching the "pure-docs batch" convention already established in the codebase.

### [NIT:consistency] Decision overstates "general-purpose" as already documented in mill-start
**Section:** Decisions — "Fallback destination" **Issue:** Says the cold-agent choice is "already documented one paragraph earlier" in mill-start's own "Sub-investigation guidance" bullet, but that bullet (verified in `mill-start/SKILL.md` lines 188-195) names only `Explore`, never `general-purpose` — only the later Technical Context section correctly notes `general-purpose` is borrowed from mill-plan's "Fork scope guardrail" wording, not already present in mill-start. **Fix:** Reword the Decision to note `general-purpose` is a new addition to mill-start sourced from mill-plan's precedent, not already present in the referenced bullet.

## Verdict

REQUEST_CHANGES
Testing section's verify-field guidance is ambiguous enough to trip `_plan_validate.py`'s PYTHONPATH= check.
MILL_REVIEW_END
