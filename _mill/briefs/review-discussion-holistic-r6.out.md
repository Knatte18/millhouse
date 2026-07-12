MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-12
```

## Findings

### [GAP] Group 2 templates' READ-ONLY header forbids Write
**Section:** Authoritative edit set → Group 2; `output-path-in-prepare-envelope`
**Issue:** All five review templates open with static prose — `plugins/mill/templates/review-discussion.md:1-4` (identical at `review-code-batch.md:1-4`, `review-code-holistic.md`, `review-plan-batch.md`, `review-plan-holistic.md`): *"You are a READ-ONLY reviewer. You MUST NOT call Edit, Write, Bash… Your sole output is the review file in the format below."* This is shared prompt text on both channels and directly contradicts `write_brief`'s agent-mode footer ("Write your full report to `&lt;abs path&gt;`"), exactly the `_review_common.py` defect class round 3 caught — but the discussion's only prescribed Group 2 edit is rewording *"your last line of output MUST be a single JSON object"*, a sentence that does not exist in any of the five review templates. The real contradiction is therefore named nowhere, and unlike `&lt;TOOL_RULE&gt;` a static template cannot be made dispatch-aware.
**Fix:** State how the read-only header is handled — e.g. delete the Write/Edit/Bash prohibition from the five templates and let the dispatch-aware `build_tool_rule` own the whole read-only clause (it is the only channel-aware injection point) — and say what replaces "Your sole output is the review file" / "Wrap your entire output in `MILL_REVIEW_BEGIN`…" now that the final message must be the ack.

### [GAP] `build_tool_rule` bulk x agent-mode cell unspecified
**Section:** `output-contract-is-agent-mode-only` → "How the split is enforced"
**Issue:** The decision says `build_tool_rule` takes `mode` (`bulk`/`tool-use`) **plus** the agent flag, but then enumerates only two outputs (agent vs `--stage full`), leaving the 2x2 matrix half-defined. `_TOOL_RULE_BULK` (`_review_common.py:1216-1221`) opens with *"Do NOT request tool calls. All content you need is in this prompt."* — under agent-mode dispatch that coexists with "You MAY use Write", a self-contradiction that would plausibly yield no `.out.md` and an `ERROR` envelope every round. The combination is reachable: `mode` derives from the spec's `tooluse` flag (`_review_discussion.py:81`, `_review_code.py:334`, `_review_plan.py:195,400,489,835`), `tooluse` defaults to `False` (`_reviewers.py:386`), and the shipped registry ships `*_bulk` (`tooluse: false`) Claude variants selectable as any role's `reviewer`. The Testing section's `build_tool_rule` test likewise names only two cases.
**Fix:** Enumerate all four cells — say explicitly what the bulk+agent rule emits (the "no tool calls" clause must become "no tool calls **except** the single Write of your report") — and extend the `build_tool_rule` test to all four.

### [NOTE] Dead `import html` after unescape removal
**Section:** `remove-html-unescape`
**Issue:** Removing `html.unescape()` at the four read sites (`_implementer_common.py:892`, `millpy-review-discussion.py:146`, `millpy-review-plan.py:185`, `millpy-review-code.py:183`) leaves `import html` unused in each file.
**Fix:** Note in the edit set that the import is dropped with the call, so the plan does not leave lint-visible dead imports.

## Verdict

GAPS_FOUND
Two shared-prompt contradictions remain unresolved; otherwise the design is buildable.
MILL_REVIEW_END
