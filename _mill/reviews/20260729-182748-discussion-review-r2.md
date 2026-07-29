MILL_REVIEW_BEGIN
# Review: mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; not independently confirmable)
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] mill-go stuck-type prompt line citations misattribute stuck_type
**Section:** Problem, Gap A, bullet 2 (mill-go verified claims)
**Issue:** Source-verified against `plugins/mill/skills/mill-go/SKILL.md`: lines 495-496 (`1) Skip to cleanliness gate (Recommended)` / `2) Retry from scratch`) are called "the `incomplete` stuck-type prompt", but they actually live under the `transient` (commits_made > 0) branch (line 492); the true `incomplete` prompt is at lines 501-503 with different option text entirely. Likewise lines 500 and 502 are labeled "the `verify`/`logic` stuck-type prompts" but line 500 is `transient`'s "Otherwise" branch and line 502 is `incomplete`'s interactive-resume branch — only line 504 is actually `verify`/`logic`.
**Fix:** Correct the stuck_type attributions for the prompts at lines 495-496, 500, and 502 before this discussion is used as plan-writing source material; re-verify each cited line against its enclosing stuck_type heading.

## Verdict

GAPS_FOUND
mill-go prompt-line stuck_type attributions in Gap A's Problem section are verifiably wrong on 3 of 6 citations.
MILL_REVIEW_END
