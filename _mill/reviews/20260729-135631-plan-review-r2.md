MILL_REVIEW_BEGIN
# Review: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetxhigh
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] Blanket `Context: none` conflicts with SKILL.md's own rule
**Location:** overview Shared Decision "Context: is none on every card" (all 12 cards, batches 1-3)
**Issue:** `plugins/mill/skills/mill-plan/SKILL.md` states unconditionally "An empty or terse `Context:` is a review-blocker," yet every card in this plan sets `Context: none`, relying instead on verbatim signature transcription inside `Requirements:` for every cross-file helper it cites (e.g. `_test_helpers.*` for Cards 9/10, `_plan_dag.parse_verify_field` for Card 4) — a targeted audit of each such reference found no case where the narrower "Context completeness" BLOCKING rule actually fires, so this is a conflict with SKILL.md's documented wording rather than a demonstrated cold-start defect.
**Fix:** either list the specific same-file/verbatim-transcription precedent per card in `Context:`, or add a line to the Shared Decision explicitly marking this as a reviewed, intentional exception to the SKILL.md Principle so it doesn't read as an oversight to a future planner.

### [NIT] `_run_verify_gate` docstring goes stale after Card 11's enrichment
**Location:** Batch 3, Card 11 (`_implementer_common.py::_run_verify_gate`)
**Issue:** the function's docstring still says "reason set to the last 2000 characters of stdout+stderr," which becomes inaccurate once the marker + up-to-20-extracted-lines enrichment ships, and Card 11 never asks for a docstring update.
**Fix:** add a docstring-update requirement to Card 11, mirroring Card 4's explicit instruction to update `_plan_validate.py`'s own docstring.

### [NIT] Card 4's rationale for the Creates:-only exclusion is imprecise
**Location:** Batch 1, Card 4 (step 2) / Card 6 scenario (h)
**Issue:** the card attributes scenario (h)'s zero-findings result to `resolve_existing_paths` "silently dropping" a not-yet-existing `Creates:` path, but step 2 already excludes `Creates:` tokens from the collected `_test.go` token set entirely, so `resolve_existing_paths` is never even called on such a token.
**Fix:** reword the parenthetical to attribute the exclusion to step 2's Edits:-only token collection, not to `resolve_existing_paths`'s drop behavior.

## Verdict

REQUEST_CHANGES
Well-grounded plan (all cross-file claims verified against source); one BLOCKING policy conflict plus two documentation NITs.
MILL_REVIEW_END
