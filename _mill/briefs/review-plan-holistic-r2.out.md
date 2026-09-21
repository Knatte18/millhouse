MILL_REVIEW_BEGIN
# Review: mill-plan/mill-start planning-process gaps, round 2 — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-21
```

## Findings

### [NIT:design] cross-batch-build-break regex over-matches file-deletion prose
**Location:** batch 4 / card 13 (`_check_cross_batch_build_break`, `_plan_validate.py`)
**Issue:** `_RE_REMOVE_SYMBOL`/`_RE_DELETE_SYMBOL` match any backtick token after "remove"/"delete" with no distinction between a code symbol and an ordinary file-path removal (e.g. a future card's `` Remove `plugins/mill/scripts/foo.py` `` — a common plan idiom for deleting a file), which would be treated as a stale-symbol candidate. Card 14's three test scenarios don't cover this false-positive shape.
**Fix:** Add a fourth fixture scenario (or an exclusion for tokens containing `/` or a file extension) asserting the check does not fire on ordinary file-removal prose.

### [NIT:consistency] Card 4's citation doesn't support its own deletion claim
**Location:** batch 1 / card 4 (new "Finalize advances the round" paragraph, `mill-plan/SKILL.md`)
**Issue:** The sentence "skipping it silently re-issues the same round number next time, deleting the just-produced `.out.md` in the process" cites "## Agent-mode dispatch" step 4 in `mill-go-base/SKILL.md` — verified against that file, step 4 ("Capture output — reviewer-skipped") only states that reviewer dispatches write their own `.out.md` and the orchestrator doesn't re-write it; it says nothing about round re-issue or deletion. The actual mechanism (`discover_round` counting only finalized files; `write_brief` unconditionally unlinking a stale `.out.md`) lives in `_review_common.py`/`_agent_dispatch.py`, not that step.
**Fix:** Point the citation at `_agent_dispatch.write_brief`'s docstring/behavior (the file this same plan's batch 3 touches) instead of step 4, or drop the parenthetical.

## Verdict

APPROVE
Plan is thorough, internally consistent, and every mechanism claim checked against source verified correctly; only minor doc/test-coverage nits found.
MILL_REVIEW_END
