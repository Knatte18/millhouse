MILL_REVIEW_BEGIN
# Review: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-25
```

## Findings

### [GAP] Picker root-cause left unidentified
**Section:** Decisions § picker-over-claim (#543b)
**Issue:** The decision defers the actual root cause to the implementer ("trace where the chain diverges", candidate suspects listed) rather than naming a fix; I verified `_prompt_numbered_multi` (line 377) and `multi_select_groom_then_claim` (477-482) are correct in isolation, so the divergence is real but unlocated — a plan writer cannot write a concrete fix card.
**Fix:** Have the implementer's first card be an explicit reproduce-and-locate step with a stated acceptance criterion (regression test red), and state that atomicity+reconciliation are the guaranteed-shipping deliverables even if the race proves environmental, so the batch is plannable regardless.

### [NOTE] merge-in brief already says "preserve both sides"
**Section:** Decisions § merge-in-combine (#540)
**Issue:** The brief at `merge-in-conflict-brief.md:27` already reads "Write a resolution that preserves the intent of both sides" and line 36 forbids `checkout --ours/--theirs`; the discussion frames the bug as the brief steering toward a wholesale pick, which the current text does not literally do — the failure is model non-compliance, not missing instruction.
**Fix:** Reframe the #540 instruction change as a concrete worked example (non-overlapping table-columns / object-keys) sharpening the existing line 27, so the plan does not "add" guidance that is already present and instead strengthens enforcement plus the `discarded` reporting net.

### [NOTE] Reconciliation portal-detection seam unspecified
**Section:** Decisions § orphan-reconciliation (#543b)
**Issue:** "no worktree, no local branch, and no portal junction" — the discussion cites cleanup's existing orphan plan (~219-264) but does not say which of these three signals already exists in `build_plan` vs. needs adding, nor how a junction's existence is probed cross-platform.
**Fix:** Note which detection inputs cleanup already enumerates and that portal-presence reuses the same junction check used elsewhere, so the plan does not reinvent probing.

## Verdict
GAPS_FOUND
One unlocated root cause (#543b picker) blocks a concrete plan card; rest is sound.
MILL_REVIEW_END
