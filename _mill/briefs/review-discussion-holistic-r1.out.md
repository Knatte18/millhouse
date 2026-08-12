MILL_REVIEW_BEGIN
# Review: millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort; cannot verify with certainty)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:scope] Fourth ERROR-only-aggregate site omitted from Scope
**Section:** Scope (In) / Technical context. **Issue:** Scope names exactly three SKILL sites (mill-start Step 3.5, mill-plan Step 4.5, mill-go-base Step 4.5) and Technical context asserts "grep confirms all three are the only skills referencing `ERROR-only-aggregate`/`verdict.*ERROR`" — this is false: `plugins/mill/skills/mill-go-base/holistic-review.md` sub-step 3.5 independently implements the identical pattern (checks top-level `verdict: "ERROR"`, two-pass retry, `BLOCKED: holistic code review ERROR-only round {H}`), and `mill-go-base/SKILL.md:420` explicitly documents it as a separate dispatch point from the per-batch Step 4.5. Grep across `plugins/mill/skills/` for `ERROR-only-aggregate` returns 4 files, not 3. **Fix:** Add `mill-go-base/holistic-review.md` sub-step 3.5 to Scope's In list with the same `error_kind`-keyed retry-semantics change as the other three sites; correct the false "only three skills" claim in Technical context.

### [NIT:consistency] Full-stage error-kind rationale premise is inaccurate
**Section:** Decisions → "error_kind bucketing", Rejected bullet. **Issue:** States full-stage `ReviewError` is "not used by the current Agent-mode dispatch path this task is scoped around" — but `mill-plan/SKILL.md:370` documents `--stage full` via `millpy-bg` as the actual second-consecutive-Agent-API-error fallback inside mill-plan's own Agent-mode error recovery, so the premise is factually wrong even though the decision's independent rationale ("wraps a multi-round loop, many possible causes") still supports defaulting to `"usage"`. **Fix:** Drop or correct the "not used by Agent-mode dispatch" clause; rely solely on the multi-cause rationale, which stands on its own.

## Verdict

REQUEST_CHANGES
Scope's SKILL-site enumeration is incomplete and its own grep claim is contradicted by a fourth matching file.
MILL_REVIEW_END
