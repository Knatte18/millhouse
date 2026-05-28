# Review: mill-go / mill-plan loop hardening

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-28
```

## Findings

### [NOTE] #360: holistic APPROVE NIT-dispatch site implicit
**Section:** Decisions — nits-on-approve (#360)
**Issue:** The dispatch rule ("On APPROVE with nit_count > 0, Builder dispatches fix pass") is mechanism-level only; the mill-go holistic APPROVE path (Holistic step 4, currently "Commit status. Proceed to Handoff.") is not enumerated as a fix site alongside the per-batch APPROVE path, leaving a plan writer to infer it applies to both paths.
**Fix:** Add "applies to both per-batch and holistic APPROVE paths in mill-go" to the Decision wording, or list Holistic step 4 alongside Execute step 3 sub-step 4 in Technical Context touchpoints for #360.

### [NOTE] #372: absent-JSON vs ERROR retry counter scope ambiguous
**Section:** Decisions — exit-without-json (#372)
**Issue:** The decision says absent-JSON is "treated as ERROR-equivalent and routed through the existing two-pass retry" but also "on the second consecutive absent-JSON, halt" — it is unclear whether absent-JSON occurrences share the same counter as ERROR-verdict rounds or are tracked separately.
**Fix:** State explicitly: either (a) absent-JSON increments the same consecutive-ERROR counter, so any mix of two ERROR-or-no-JSON rounds halts, or (b) absent-JSON has its own consecutive counter independent of the ERROR counter.

### [NOTE] #373: holistic timeline lookup for H>1 rounds implicit
**Section:** Decisions — crash-recovery-freshness (#373)
**Issue:** When `max_holistic_rounds > 1`, multiple `holistic-reviewing` entries exist in the timeline; the freshness probe must select the correct one for round H, but the selection strategy (e.g., Nth occurrence = round H, or last occurrence before the candidate file's mtime) is not stated.
**Fix:** Add one sentence: e.g., "For the holistic path, use the last `holistic-reviewing` timeline entry whose position corresponds to round H (the Hth occurrence)."

## Verdict

APPROVE
Discussion is well-scoped and source-verified; all seven bugs have clear decisions, rationale, and rejected alternatives. Three minor NOTEs for plan-writer clarity; none block planning.