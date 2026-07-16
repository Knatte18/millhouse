MILL_REVIEW_BEGIN
# Review: Agent-mode dispatch: envelope fields and session/runtime state are unreliable

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [GAP] session_id-reuse guard also mutates subprocess full-stage
**Section:** Decisions -> "session_id reuse on prepare re-run" / Scope Out
**Issue:** The reuse guard is placed in the shared non-`resume-incomplete` `else` branch (`millpy-implement.py:461`), which runs for `--stage full` (the subprocess/psmux path) as well as `--stage prepare`; a subprocess re-run against a `running` batch would then reuse the old session_id and skip snapshot/commit — a behavior change Scope Out explicitly forbids ("Any behavior change to subprocess/psmux dispatch modes ... out").
**Fix:** State whether the guard is gated on `args.stage == "prepare"` (agent-mode only) or whether the full-stage crash-recovery re-run is intentionally in scope.

### [NOTE] reviewer_model can diverge via auto spec-switch, not just override
**Section:** Decisions -> "reviewer_model / audit-trail accuracy"
**Issue:** `reviewer_model` is baked from `reviewer_name` at `_review_code.py:362` *before* `maybe_switch_spec_for_large_prompt` (line 371) may swap the spec; the returned `model` (line 377) then reflects the switched spec while the prompt-echoed `reviewer_model` reflects the old name — so the audit trail can lie even with no operator override, a case the orchestrator-passed `--actual-model` channel may not cover.
**Fix:** Acknowledge the large-prompt auto-switch divergence and say whether `--actual-model` (or the envelope `model`) is expected to capture it.

## Verdict

GAPS_FOUND
One scope conflict (reuse guard on shared branch) must be resolved before planning.
MILL_REVIEW_END
