MILL_REVIEW_BEGIN
# Review: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] #758 annotation target/format unspecified for non-card failures
**Section:** Decisions › 758-mandatory-reason-annotation
**Issue:** Confirmed in `_implementer_common.py` that many `verify`/`logic` stuck reasons are not card-attributable (e.g. "success reported but no content commit", "untracked files outside scope", "inferred success but working tree dirty") — the decision mandates "annotating the plan card" but never specifies which card to annotate, or the section/format to use, when the failure traces to no specific card at all.
**Fix:** State explicitly whether the mandatory annotation goes on a specific card, a batch-level note, or a new section, and how it's chosen when the reason has no natural single-card target.

### [NOTE] #758 Testing section names only plan review as the gate
**Section:** Testing › #758 (mandatory reason annotation)
**Issue:** Says "Plan review (mill-plan's self-review / mill-review-plan) is the correctness gate" for a mill-go/SKILL.md behavior change; the actual diff to `mill-go/SKILL.md` is verified by this task's own batch code review (mill-review-code) when mill-go executes the plan, not by plan review, which only reviews how the future plan describes the edit.
**Fix:** Either add "and code review of the actual SKILL.md diff" (matching the #755 Testing entry's phrasing) or explain why plan review alone suffices here.

## Verdict

GAPS_FOUND
One GAP: #758's mandatory plan-card annotation lacks a target/format rule for non-card-attributable failures.
MILL_REVIEW_END
