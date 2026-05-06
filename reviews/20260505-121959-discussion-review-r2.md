Now I have enough to write the review.

# Review: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-05-05
```

## Findings

### [GAP] Holistic dispatch site not addressed in SKILL.md update
**Section:** `### mill-go-skill-update` / Scope
**Issue:** The confirmed SKILL.md `## Holistic code review` section (lines 143–149) also calls `_implementer_sonnet.run(...)` directly on `REQUEST_CHANGES`. The `mill-go-skill-update` decision lists only the initial-dispatch and per-batch fix-cycle blocks for replacement; the holistic dispatch site is unmentioned. A plan writer cannot determine whether to update it (consistent CLI use) or leave it raw (inconsistent, bypasses resume support).
**Fix:** Add an explicit statement: either the holistic dispatch is also replaced with a `millpy-implement.py` call (and what flags), or it's deliberately left out-of-scope with rationale (e.g., holistic never resumes, so resume advantage doesn't apply).

### [GAP] `--round` default-vs-required contradiction
**Section:** `### CLI surface` — Flags
**Issue:** The flags table says `--round N` "defaults to 1," implying it's optional. The `--resume` description says "Requires `--round` and `--review-file`." Testing scenario 8 only tests `--resume` without `--review-file` (no matching scenario for `--resume` without `--round`). The plan writer must pick: argparse `required=True` when `--resume`, or a default that makes the flag optional — the discussion commits to neither.
**Fix:** State explicitly whether `--round` is required when `--resume` is set, or drop the "Requires `--round`" phrasing and confirm the default of 1 is intentional.

### [NOTE] `fixing`-state crash-recovery on `--resume` unspecified
**Section:** `### crash-recovery-initial` / Testing scenarios
**Issue:** `crash-recovery-initial` addresses `running` state only. If `--resume` is called for a batch already in `fixing` state (crash during fix-cycle), no behavior is specified and no test covers it.
**Fix:** Add one line to `crash-recovery-initial` stating whether `fixing`-state on `--resume` is treated as a restart (overwrite `fixing` fields, re-resume) or an error.

### [NOTE] `LLMError` (non-session) on resume path has no test
**Section:** `### session-error-handling` / Testing scenarios
**Issue:** `session-error-handling` explicitly says both `LLMSessionError` and bare `LLMError` produce the same synthetic stuck JSON. Testing scenario 5 covers only `LLMSessionError` on resume. No scenario exercises `LLMError` on the resume path.
**Fix:** Add scenario: `--resume` path, `run` raises `LLMError` → same stdout shape as `LLMSessionError`, exit 1.

## Verdict

GAPS_FOUND  
Two GAPs block planning: the holistic dispatch site's in/out-of-scope status is unresolved, and `--round` required-vs-default is contradictory.