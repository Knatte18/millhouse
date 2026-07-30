MILL_REVIEW_BEGIN
# Review: Blocking phase-wait gate for mill-plan/mill-go chaining

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not introspectable)
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

## Findings

### [GAP] 4c's pre-Handoff plan-fix-r{N} write omitted from site enumeration
**Section:** ### Decision: Exact phase-table edit sites
**Issue:** Verified against `mill-plan/SKILL.md`: step 4c (line 236, `REQUEST_CHANGES` + `blocking_count == 0`) also writes `plan-fix-r{N}` to status.md immediately before breaking to Handoff — the same short pre-Handoff pattern the Decision attributes only to 4a (208) and 4b (210), alongside the long-running 4d case (238-244). 4c's write is phrased in prose ("append `plan-fix-r{N}` to status timeline") rather than a literal `_status.append_phase(...)` call, which is plausibly why a call-site grep missed it.
**Fix:** Add 4c to the enumerated list of pre-Handoff `plan-fix-r{N}` writers alongside 4a/4b. No behavior change follows — `plan-fix-r{N}` is already in the widened regex trigger set regardless of which step writes it — but the Decision's "verified line-by-line against both SKILL.md files' actual `append_phase` call sites" claim is currently inaccurate/incomplete.

### [NOTE] Give-up timeout default has no stated rejected alternative
**Section:** ### Decision: Poll interval and give-up timeout values
**Issue:** Unlike every other `### Decision:` in this file, this one has no `Rejected:` bullet — the specific 120-minute default is justified only forward (accommodates long batch chains, bounds abandoned runs) with no alternative value considered and rejected.
**Fix:** Optional: add a one-line `Rejected:` noting why a shorter (e.g. 60 min) or longer default was not chosen, for consistency with the rest of the document's Decision shape.

## Verdict

GAPS_FOUND
One GAP: the phase-table-edit-sites verification omits mill-plan step 4c's pre-Handoff plan-fix-r{N} write.
MILL_REVIEW_END
