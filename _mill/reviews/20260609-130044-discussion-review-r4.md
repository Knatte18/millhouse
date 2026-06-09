`resolve_path` is exported from `_review_common` and importable. The discussion's prescribed approach is feasible.

I have verified all material claims. Summary of findings:

- Gaps A, B, C, D all confirmed against source.
- The `_forward_output` contract, `emit_prepare` signature, `resolve_path` helper, `discover_round` semantics, discussion-review signature differences, and ordering invariant all match source.
- **One genuine gap**: the SKILL-edit instructions are inaccurate. The actual Agent-mode dispatch pattern has 6 steps (not 5), finalize is step 5 (not 4), and critically, step 2 (prepare-parse) currently extracts only `brief_path`/`subagent_type`/`model` — NOT `session_id` or `round`. The discussion's "amend step 5" instruction omits the required step-2 amendment to capture those fields before they can be threaded into finalize.
- Two minor imprecisions (step count/numbering; mill-start has no own copy of the pattern).

MILL_REVIEW_BEGIN
# Review: agent-pipeline-reliability

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-09
```

## Findings

### [GAP] SKILL step 2 must also parse session_id/round
**Section:** Scope (mill-go/SKILL.md item); Technical context "Critical step 4 gap"
**Issue:** The live Agent-mode dispatch pattern's step 2 (mill-go/SKILL.md:111-114) parses only `brief_path`, `subagent_type`, `model` — it does NOT capture `session_id` or `round` from the prepare envelope, so "amend step 5 to thread them into finalize" is impossible as written: there is nothing captured to thread.
**Fix:** Add a scope item to also amend step 2 of the pattern to extract `session_id` and `round` (and `start_sha` for fix) from the prepare envelope, so step 5 can reference them.

### [NOTE] Pattern is 6 steps, finalize is step 5 not 4
**Section:** Technical context "Prepare->Agent->finalize pattern"
**Issue:** The discussion says "The SKILL describes five steps" with finalize as step 4 and parse-envelope as step 5; the live SKILL (mill-go/SKILL.md:107-127) has six steps — finalize+parse is a single step 5, and "step 4" in the discussion is "Capture output."
**Fix:** Correct the step inventory (six steps; finalize = step 5) so the implementer edits the right step.

### [NOTE] mill-start has no own dispatch pattern to amend
**Section:** Scope (mill-start/SKILL.md item)
**Issue:** mill-start/SKILL.md (lines 124, 150) only references mill-go's "## Agent-mode dispatch" pattern; it has no local copy of "step 5" to amend. The concrete mill-start change is threading `--round` at its two discussion-review finalize call sites.
**Fix:** Reword the mill-start scope item to specify the `--round` threading at lines 124/150, not "amend step 5 of the pattern."

## Verdict

GAPS_FOUND
SKILL edit plan omits the required step-2 amendment to capture session_id/round before threading them.
MILL_REVIEW_END
