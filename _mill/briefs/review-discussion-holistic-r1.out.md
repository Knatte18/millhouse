MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based fixer (NIT-fix) dispatch

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (best-effort self-assessment)
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] record-the-fallback breaks crash-resume via an unregistered phase literal
**Section:** Decision `record-the-fallback`. **Issue:** `_status.append_phase(status_path, f"fork-fallback-fix-{scope}-r{N}", ...)` overwrites the top-level `phase:` field (confirmed: `_status.append_phase` docstring, `## Board discipline` "Phase transitions via `_status.append_phase`"), which drives the "Mid-execution phase-gate widening" table (`mill-go-base/SKILL.md:127-131`) via `re.fullmatch` against a fixed exact-set/regex list. `fork-fallback-fix-<scope>-r<N>` matches neither the exact set nor `^fixing-.*-r\d+$` (wrong prefix), so a session crash between this commit and the cold retry's own next phase write lands on the phase table's "any other -> surface + halt" row (line 121) on resume. **Fix:** either register the new literal in the widening table (requires a `mill-go-base` edit, conflicting with Decision `no-base-edits`) or record the fallback through a channel that doesn't overwrite `phase:` (e.g. a batch-state field or a non-`phase:`-touching audit mechanism), and state the choice as a decision.
**Note:** the decision's own rationale cites `self-resolved-verify-logic` as precedent, but that literal *was* added to the widening exact-set (`mill-go-base/SKILL.md:130`) when introduced; `self-resolved-terminal-dirt` (the other cited precedent) is a terminal/Handoff-phase write with no resume exposure, so it isn't actually analogous to a mid-fix fallback.

### [NIT:design] role-detection-via-envelope may duplicate Override point A's own role-identification
**Section:** Decision `role-detection-via-envelope`. **Issue:** Override point A's own quoted text (`mill-go-base/SKILL.md:238-242`) already resolves "which role is this dispatch" structurally — "the role for the current dispatch is the one named by the calling subsection" — independent of any envelope field, and per-role subsections (`### fixer` etc., per Decision `per-role-subsections-for-sibling-disjointness`) make this free. The Decision's three considered alternatives (envelope `role` field, CLI-name string, `subagent_type`) never include "no detection needed — the calling subsection already tells you," so it's unclear whether this decision is load-bearing prose or inert rationale. **Fix:** either drop the decision as unnecessary or clarify what SKILL.md prose (if any) actually depends on the envelope's `role` field rather than structural subsection placement.

## Verdict

REQUEST_CHANGES
The fork-fallback status write breaks the phase-gate resume table without a stated fix compatible with no-base-edits.
MILL_REVIEW_END
