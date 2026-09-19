MILL_REVIEW_BEGIN
# Review: Audit mill-start/mill-plan/mill-go for turn reduction

```yaml
duration_s: 167.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: /home/knatte/Code/millhouse/wts/turn-reduction-audit/_mill/discussion.md
date: 2026-09-19
```

## Findings

### [NIT:consistency] mill-go-base/SKILL.md line count off by one
**Section:** Technical context ("Files to walk") **Issue:** Discussion cites `mill-go-base/SKILL.md` as 995 lines; the worktree file actually ends at line 996 (its own "## History" note even says "Pre-strip version (1483 lines)" for a *different* commit, not this count). **Fix:** Re-verify and correct to 996 when writing the audit doc, per the "First-pass findings are a starting point" Decision already governing this kind of drift.

### [NIT:consistency] mill-start line-range citation points to frontmatter, not Entry steps
**Section:** Decisions → "First-pass findings are a starting point, not ground truth" **Issue:** "candidate #2 ... mirrored in `mill-start/SKILL.md:1-3`" cites the YAML frontmatter (`name:`/`description:`/`argument-hint:`), not mill-start's actual Entry steps 1-3 (which sit at roughly lines 85-95); the parallel `mill-plan/SKILL.md:33-45` citation is correct and does point at that file's Entry steps 1-3. **Fix:** Correct the mill-start citation to its real Entry-step line range when the audit doc restates this candidate.

## Verdict

APPROVE
All claims checked against worktree source hold; only two trivial line-citation drifts found, already covered by the doc's own re-verification mandate.
MILL_REVIEW_END
