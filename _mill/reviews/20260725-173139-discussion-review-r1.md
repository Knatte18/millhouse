MILL_REVIEW_BEGIN
# Review: Agent-tool dispatch discards the effort tier already encoded in mill-agents.yaml (opushigh/opusmedium/opusmax)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] Merge-in envelope never resolves `effort` in Agent-mode prepare stage
**Section:** Scope ("Out") / Technical context (five envelope locations)
**Issue:** Scope claims `effort` is "already correctly resolved into every review/implement/fix/merge-in envelope," and Technical context lists exactly five script locations resolving it — `_review_discussion.py:123`, `_review_plan.py:453/545`, `_review_code.py:382`, `_implementer_common.py:1187`. `plugins/mill/scripts/millpy-merge-in-subagent.py` is not among them: its three `--stage prepare` calls (lines 356, 402, 437) call `emit_prepare`/`emit_prepare_no_dispatch` without passing `effort=impl_effort`, even though `impl_effort = impl_spec.get("effort")` is computed at line 328 and IS correctly forwarded to the non-agent-mode subprocess path (`_implementer_claude.run(..., effort=impl_effort, ...)` at lines 363/444). By contrast, `millpy-fix.py`'s prepare-stage call at line 656 does pass `effort=fixer_effort` into `emit_prepare`. So if `merge.model` in `mill-config.yaml` is ever set to an effort-bearing alias (e.g. `opushigh`), Agent-mode merge-in dispatch will silently drop that tier — reproducing this exact task's bug, unfixed, for the merge-in role.
**Fix:** Correct the Scope/Technical-context claim, and add merge-in's two `effort=impl_effort` kwargs to the `emit_prepare` calls in `millpy-merge-in-subagent.py` (or explicitly scope merge-in out with an accurate rationale, e.g. "merge.model is haiku-only by convention" rather than "already correctly resolved").

### [NOTE] Technical-context grep string doesn't match SKILL.md text
**Section:** Technical context, first bullet
**Issue:** Discussion says to search SKILL.md for `"has no corresponding Agent-tool call parameter to forward it to"`; the actual text (line ~123 of `mill-go/SKILL.md`) reads `"has no corresponding Agent-tool parameter to forward it to"` — no "call" between "Agent-tool" and "parameter." A literal grep with the discussion's quoted string returns zero matches.
**Fix:** Correct the quoted search string to match the file verbatim.

## Verdict

GAPS_FOUND
Scope's merge-in "already correctly resolved" claim is factually wrong per source; the plan writer needs an accurate premise.
MILL_REVIEW_END
