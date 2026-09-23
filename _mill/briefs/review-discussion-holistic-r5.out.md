MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [BLOCKING:consistency] Moves-target disposition contradicts itself across 3 passages
**Section:** Scope / Decision `resolution-scope-rework` / Technical context.
**Issue:** Scope and the Decision's own set definition build the plan-wide cited-files union from "Context:/Edits:/Creates:/Deletes:/Moves:-source" — Moves-target tokens explicitly excluded. The same Decision's parenthetical justifies this by "mirroring the existing plan-wide `creates_union`/`deletes_union`/`moves_sources`/`moves_targets` pattern," citing `moves_targets` as precedent for a set the definition itself omits. Technical context then tells the plan-writer to build the union via `_card_own_reference_set`, which (verified against its source) adds both halves of a Moves pair — source and target — via `tokens.add(pair_m.group(1))` / `tokens.add(pair_m.group(2))`, contradicting the Moves-source-only definition.
**Fix:** State explicitly whether a Moves-target token belongs in the plan-wide cited-files set, and reconcile the Scope/Decision wording with the Technical context's `_card_own_reference_set`-reuse suggestion so they agree (also explain why Creates-targets, equally not-yet-existing at validation time, are included while Moves-targets would be excluded, if that asymmetry is intended).

## Verdict

REQUEST_CHANGES
Resolve the Moves-target inclusion/exclusion contradiction in the resolution-scope-rework definition before plan writing.
MILL_REVIEW_END
