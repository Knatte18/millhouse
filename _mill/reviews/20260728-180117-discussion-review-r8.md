MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] #718 instruction and report-schema outcome don't match
**Section:** Decisions/merge-in-semantic-duplication
**Issue:** The quoted new template instruction is unconditional — "If it already exists elsewhere ... do not re-add it in the hunk; keep only the other side's unrelated edit" — with no branch for uncertainty. But the paired report-schema addition presupposes the opposite outcome for the ambiguous sub-case: the sub-agent "kept both sides" and flags it via `discarded`. As drafted, the instruction never tells the sub-agent to keep both when it can't conclusively tell move-vs-duplicate, so the new `"kept both sides ... ambiguous"` report clause has no instruction path that produces it — it's unreachable as specified, relying on unstated sub-agent improvisation for exactly the judgment call this fix exists to de-risk.
**Fix:** State the fallback explicitly in the instruction: e.g. "if you cannot confidently tell this is the same moved content vs. a legitimate independent duplication, keep both (per step 3's default) and report the ambiguity via `discarded`" — and have the Testing section's required worked example walk through the confident-drop and ambiguous-keep-both sub-cases as two distinct outcomes, not one generic "moved vs duplicated" example.

## Verdict

GAPS_FOUND
The #718 instruction text and its report-schema addition specify contradictory sub-agent behavior for the ambiguous case.
MILL_REVIEW_END
