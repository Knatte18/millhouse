MILL_REVIEW_BEGIN
# Review: mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Holistic digest is blind to batch-scope BLOCKING history
**Section:** Decisions / `prior-blocking-digest-is-cumulative` + `symmetric-batch-and-holistic-application`
**Issue:** Both decisions scope the digest to "every review file from round 1 through N-1 at this scope (batch or holistic)" — siloed per scope. A BLOCKING finding fixed during per-batch review (when a hub enables `roles.code-review.batch.reviewer`) is invisible to the holistic-scope digest, since holistic review files never record it. A later holistic-scope NIT-fix pass can therefore undo a batch-scope BLOCKING fix with zero protection — the exact regression this task exists to close, just crossing scopes instead of rounds. This contradicts the stated rationale for the symmetric decision ("hubs that do enable batch review get the same protection the holistic scope gets") — the protection is not actually the same; it's scope-siloed.
**Fix:** Either state this as an accepted, documented limitation (batch-scope fixes get no cross-scope protection) or add batch-scope review files for this task's batches into the holistic-scope digest's scan set when batch review was enabled.

### [NIT:consistency] New deterministic helper vs. existing prose-driven digest is unaddressed
**Section:** Scope / Technical context — "New pure-Python helper... reusing the existing extraction pattern already used for the NIT digest"
**Issue:** Verified against `mill-go/SKILL.md` (batch ~682-687, holistic ~1044-1050): the existing prior-nonblocking NIT digest has no backing Python module — it is built by the orchestrating agent following prose instructions, with no unit tests (confirmed: no `_fix.py`/digest helper exists in `plugins/mill/scripts/`). The new prior-BLOCKING digest is scoped as a unit-tested pure-Python helper. The discussion doesn't say whether the old NIT digest should migrate to the same helper (DRY) or whether near-identical extraction logic now permanently exists in two different forms (LLM-prose vs. code).
**Fix:** State explicitly that the old NIT digest stays prose-driven and is out of scope for this task, to close off plan-writer uncertainty about refactoring it.

## Verdict

REQUEST_CHANGES
Cross-scope BLOCKING-protection gap (batch fixes invisible to holistic digest) needs an explicit decision before planning.
MILL_REVIEW_END
