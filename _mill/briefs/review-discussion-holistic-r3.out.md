Final verification done. All major technical claims cross-checked against source. Producing the review.

MILL_REVIEW_BEGIN
# Review: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: C:\Code\millhouse\wts\mill-review-and-finalize-gaps\_mill\discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Dirty-tree "safety net" claimed for nits-only path is currently a no-op
**Section:** Decisions > "Nits-only no-op success" (rationale) and Scope > Out, Testing item (b)
**Issue:** The decision's rationale and scope-out justification both claim `_in_scope_dirty_stuck()` "still runs, unchanged, after the nits_only reordering" and is "the safety net" for the secondary #582 stray-uncommitted-edit case. Confirmed by direct read: `_in_scope_dirty_stuck()` (`_implementer_common.py:265-292`) returns `None` immediately when `task_dir`/`parent_branch` are `None`, and `millpy-fix.py` never passes either argument at its only two `finalize_from_output`/`_forward_output` call sites (`--stage finalize` at line ~242, synchronous full-stage at line ~466) -- the gate is always a no-op on the fixer's code path, independent of this task's change. Separately, mill-go's SKILL-level "2b Cleanliness gate" (the actual functioning dirty-tree check, `mill-go/SKILL.md:262-287`) runs once after the implementer's initial success report, *before* code review -- it does not re-run after the nits-only fixer dispatch in step 4's APPROVE branch (`SKILL.md:368` goes straight from "NIT-fix completes successfully" to setting batch state `approved` + per-batch cleanup, with no gate in between). The only thing that would eventually catch a stray uncommitted edit is the Handoff-time Terminal cleanliness gate (`mill-go/SKILL.md:709-720`), much later in the run and with a different ("dirty working tree at task completion") message than "stuck."
**Fix:** Either bring threading `task_dir`/`parent_branch` through `millpy-fix.py`'s `finalize_from_output`/`_forward_output` calls into this task's scope so the in-process gate actually fires on the nits-only path, or correct the Decision rationale / Scope-out text / Testing item (b) to stop claiming the in-process gate is the safety net -- state that the Handoff-time terminal cleanliness gate is the real (delayed) backstop, and adjust the planned `test-implementer-common.py` case (b) so it does not assert behavior (`finalize_from_output` itself returning stuck/dirty) that the real CLI never exercises.

## Verdict

GAPS_FOUND
One gap: the claimed in-process dirty-tree safety net for the nits-only no-op fix is unreachable via the actual `millpy-fix.py` call sites.
MILL_REVIEW_END
