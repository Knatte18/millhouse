MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-23
```

## Findings

### [BLOCKING] Nit-gate marker/approve ordering is inverted
**Location:** Batch 2 (nit-enforcement), card 5 (`compute_unfixed_nits`)
**Issue:** Card 5 flags a scope when "no `nits-fixed-<scope>` row exists ... AT OR AFTER the approve row." But mill-go writes the `nits-fixed-<scope>` marker (inside `_forward_output` during the NIT-fix) BEFORE it appends `approved-<batch>` (SKILL.md line 343) and `holistic-approved` (line 638). The marker always precedes the approve row, so an "at or after the approve row" predicate never finds it and FALSELY flags every nitted-then-fixed scope as unfixed — blocking Handoff for every task that had nits. Synthetic card-7 fixtures may mask this.
**Fix:** Drop the positional "at or after the approve row" constraint; require only that a `nits-fixed-<scope>` row exists anywhere in the timeline for an approved, nitted scope.

### [NIT] Card 5 depends on marker strings owned by mill-go without naming the contract
**Location:** Batch 2, card 5
**Issue:** `compute_unfixed_nits` hard-codes the timeline phase tokens `approved-<batch>` / `holistic-approved` and `nits-fixed-<scope>`, which are authored in `mill-go/SKILL.md` (card 6) and `_forward_output` (card 4). Card 5's `Context:` lists none of these as the source of truth, so the string contract is implicit.
**Fix:** Note in card 5 Requirements that these three tokens are the cross-card contract with card 4 and card 6 so a drift in either side is caught.

### [NIT] "Do NOT read reviews/" text lives in tool-rule helper, not templates
**Location:** Batch 4, card 13 + card 15
**Issue:** The code-review templates carry `<TOOL_RULE>`, a token; the literal "Do NOT read `reviews/`" string is produced by `_review_common.build_tool_rule` (`_TOOL_RULE_*`). Card 13 says "keep the `<TOOL_RULE>` ban intact" (fine — token untouched), but card 15 asserts the rendered prompt "still contains the `Do NOT read reviews/` tool-rule text," which only holds because `prepare()` renders a real tool_rule. Harmless but the card 13 wording implies the text is in the template.
**Fix:** Clarify card 13 that it only adds `<PRIOR_NONBLOCKING>` and must not displace the `<TOOL_RULE>` token; the read-ban text is rendered, not literal, in the template.

## Verdict

REQUEST_CHANGES
Card-5 nit-gate predicate is inverted against the actual marker/approve write order; fix before implementation.
MILL_REVIEW_END
