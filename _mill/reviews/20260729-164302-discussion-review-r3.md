MILL_REVIEW_BEGIN
# Review: mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] `isolation: "worktree"` fallback semantics are ungrounded
**Section:** Decisions → Fork scope guardrail placement and mechanism (#741), item (e)
**Issue:** The parallel-dispatch fallback ("each fork must instead use `isolation: "worktree"`... checks out committed HEAD rather than the live working tree") is asserted with zero source citation, unlike every other technical claim in this discussion (all of which cite exact file:line evidence, verified accurate on read-through). Grep of the whole repo shows exactly one mention of an `isolation` parameter on the Agent tool (`mill-go/SKILL.md:123`, "optionally isolation") and it documents only that the parameter exists, not its accepted values or the "checks out committed HEAD" behavior this decision relies on.
**Fix:** Verify the Agent tool's `isolation` parameter's accepted values and exact semantics (e.g. via a source/doc citation or a quick experiment) before the plan encodes this as the prescribed parallel-dispatch fallback; if unverifiable, drop clause (e)'s worktree-isolation branch and keep serial dispatch as the only sanctioned path for concurrent research.

### [NOTE] "Narration point" is new terminology despite rationale claiming reuse
**Section:** Decisions → Anti-pause rule placement (#743)
**Issue:** The rationale says the exact wording should "reuse the existing repo-wide phrasing pattern... rather than inventing new phrasing," citing `conversation/SKILL.md:33` and `mill-self-report/SKILL.md:65` — but the proposed sentence coins a new term, "narration point," which appears nowhere else in `plugins/mill/skills/` (confirmed by grep for "narrat").
**Fix:** Either drop "narration point" for plain prose (e.g. "state in one sentence what you're waiting for; do not ask") or acknowledge in the rationale that this one term is new, not reused, so a future reader doesn't go hunting for a prior "narration point" convention that doesn't exist.

## Verdict

GAPS_FOUND
One technical claim underpinning the parallel-fork fallback lacks any source grounding; fix before plan writing.
MILL_REVIEW_END
