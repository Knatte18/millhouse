Now I have enough grounding to write the review.

# Review: 19 (A) — mill-go + scripts infra fixes

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: discussion.md (discussion round 1)
date: 2026-05-06
```

## Findings

### [NOTE] builder-lock CLI mill_dir resolution unspecified
**Section:** Technical context → `millpy-builder-lock.py`
**Issue:** The CLI interface (`acquire <slug>`, `release`, `read`) does not state how `mill_dir` is resolved — the invocation in SKILL.md uses no `--mill-dir` flag, implying cwd-relative `Path(".millhouse")`, but this is not stated.
**Fix:** Add one sentence: "The CLI derives `mill_dir = Path.cwd() / '.millhouse'`; it must be invoked from the worktree root, consistent with every other millpy script."

### [NOTE] implementer-brief.md warning placement ambiguous
**Section:** Technical context → `implementer-brief.md` Report section
**Issue:** "After the block, add a bold note" is singular, but the Report section has two fenced JSON blocks (success and stuck); the warning should apply to both.
**Fix:** Clarify as "after the success block" and "add the same note after the stuck block," or position the warning after both blocks with a single sentence covering both cases.

## Verdict

APPROVE  
Discussion is complete and well-grounded; two minor clarifications needed but no blocking gaps.