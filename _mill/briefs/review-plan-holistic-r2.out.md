MILL_REVIEW_BEGIN
# Review: mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (best-effort guess; harness metadata for this session reports "Sonnet 5" / claude-sonnet-5)
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [NIT] `_check_context_completeness` resolvability omits `moves_targets`
**Location:** Batch 01, Card 1
**Issue:** Resolvability is `resolve_existing_paths(...)` OR `stripped_token in creates_union` only; `_check_non_existent_path` (the established sibling check, `_plan_validate.py:701-705`) also OR's in `deletes_union`/`moves_targets`. A Requirements: token naming a plan-wide Move *target* not yet on disk will be silently treated as unresolvable and never flagged, an untested blind spot (no Card 2 test covers this path).
**Fix:** Thread `moves_targets` (and ideally `deletes_union`) into `_check_context_completeness`'s resolvability OR-chain for consistency with `_check_non_existent_path`, or explicitly document the narrower scope as intentional.

### [NIT] No specified fallback when a card lacks a `Requirements:` header
**Location:** Batch 01, Card 1
**Issue:** The spec says "locate this card's `Requirements:` field" but never states what `_check_context_completeness` should do when the header is entirely absent (a malformed card already caught separately by `card-missing-field`). Without an explicit "skip this card" instruction, an implementer could plausibly write code that raises on `None.group(...)`.
**Fix:** Add one sentence: if no `Requirements:` header line is found in `card_text`, skip the card (zero findings), mirroring `_card_field_is_none`'s "no header found → treat as none" precedent.

### [NIT] Anti-pause text cites an unloaded skill's rule
**Location:** Batch 02, Cards 4 and 5
**Issue:** Both inserted sentences reference "`mill:conversation`'s numbered-options rule" for how a legitimate escape-hatch prompt must be formatted, but neither `mill-plan/SKILL.md` nor `mill-go/SKILL.md` loads `mill:conversation` anywhere (confirmed by grep) — unlike `mill-start/SKILL.md`, which explicitly loads it at Step 0 "because prompts depend on [it] being active." The AskUserQuestion ban itself is self-contained and unaffected, but the numbered-list formatting guidance for the narrow allowed escape hatches (max-rounds prompt, non-progress halt) may not actually be active in the executing LLM's context.
**Fix:** Out of this task's stated scope (#741/#742/#743) to fix now; flag as a follow-up to add a `mill:conversation` load step to mill-plan/mill-go's Entry, or drop the parenthetical citation if it isn't meant to be runtime-binding.

## Verdict

APPROVE
Line-number/identifier citations verified accurate throughout; only minor NIT-level gaps in the new validator's edge-case coverage remain.
MILL_REVIEW_END
