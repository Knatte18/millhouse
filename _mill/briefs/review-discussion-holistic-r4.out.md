I have verified the key claims. All cited line references, function signatures, template lines, and current wording check out accurately against source. Now I'll assess for gaps.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [GAP] Merge-in recompute contradicts eager-before-manifest rule
**Section:** Decisions § baseline-aware verify gate; Q&A #6
**Issue:** The design makes eager pre-batch-1 computation "the load-bearing correctness requirement" (recomputing lazily inside finalize is "the wrong side of that boundary" because an implementer may have touched a manifest), yet the merge-in path resets the baseline to null "forcing recomputation on the next module-wide gate call" — i.e. lazily inside a mid-task finalize, after that batch's implementer already ran against a now-changed parent tip; the reused-dependency junctions may no longer match the merged parent's needs.
**Fix:** Specify that mill-merge-in eagerly recomputes the baseline at its own clean post-sync boundary (or state why lazy post-merge-in recompute is safe, e.g. merge-in already resyncs dependencies), instead of only "reset to null."

### [GAP] Merge-in edit absent from Scope "In"; mechanism undecided
**Section:** Scope § In
**Issue:** Baseline invalidation on merge-in is a required behavior (Decision + Q&A #6), but no mill-merge-in file appears in the Scope "In" bullets; Technical Context leaves the target as "mill-merge-in's SKILL.md and/or its underlying script" — an unresolved either/or. `mill-merge-in/SKILL.md` and `millpy-merge-in-subagent.py` both exist, so the writer cannot tell which to edit.
**Fix:** Add the concrete mill-merge-in file(s) to Scope "In" and pick SKILL prose vs. script for the clear/recompute call.

### [NOTE] Pre-flight baseline computation has no named CLI surface
**Section:** Scope § In; Decisions § baseline gate
**Issue:** mill-go's new pre-flight step "eagerly computes and caches" the baseline before batch 1, but no CLI stage/command is named for the SKILL to invoke; Scope lists only `millpy-implement.py`/`_implementer_common.py` as edited.
**Fix:** Name the invocation surface (e.g. a new `millpy-implement.py --stage baseline` or dedicated CLI) so mill-go's pre-flight step and any merge-in recompute both have a concrete call.

## Verdict

GAPS_FOUND
Merge-in invalidation reintroduces the manifest-boundary hazard the eager design forbids, and its edit is unscoped.
MILL_REVIEW_END