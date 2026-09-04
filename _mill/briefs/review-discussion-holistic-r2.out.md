MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (Sonnet 5, per harness label)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #906 card-number algorithm can violate its own reused validator
**Section:** Scope #906 / Decision `906-reuse-existing-plan-validate-helper`
**Issue:** `_plan_validate._check_card_numbering` (verified `_plan_validate.py:908-972`) enforces two independent invariants: within-batch numbers must be gap-free/sequential (lines 924-955), AND no number may repeat across batches (957-972). `_parse_cards` scans the whole batch text for any `### Card N:` heading regardless of section, so a card appended anywhere (including under `## Prior failure`) counts. The decision's algorithm — "pick the lowest number absent from every batch" — is a *global* minimum-unused search; batches are not required to occupy contiguous global ranges (e.g. batch A = {1,2,3}, batch B = {10,11} is valid today), so the globally-lowest-absent number (4) would violate the target batch's own gap-free requirement unless it happens to land on that batch's own `max+1`.
**Fix:** Decision text must specify the number is the target batch's own `max(existing)+1`, additionally checked for global uniqueness (bumping past collisions if needed) — not a bare global-minimum search — or the plan-writer will implement an algorithm that fails the very helper it reuses.

### [NIT:consistency] #906 "appending a new card" vs. current bullet-only `## Prior failure` behavior
**Section:** Scope #906
**Issue:** Current text (confirmed `SKILL.md:853-856`, `holistic-review.md:185-189`) only appends a plain bullet (round + verbatim reason) to `## Prior failure` — no card heading involved. The scope text's phrase "before appending a new card to the `## Prior failure` section (or inserting a new numbered card)" reads as two different mechanisms without saying which one is real, or where a newly-created `### Card N:` heading would actually live (inside `## Prior failure`, or in the batch's `## Cards` list).
**Fix:** State explicitly which file/section receives the new `### Card N:` heading when self-resolve decides a new card is warranted (distinct from the existing plain-bullet failure log, which the plan writer should keep as-is).

## Verdict

REQUEST_CHANGES
#906's card-numbering algorithm can violate the validator it claims to reuse; needs a target-batch-relative rule.
MILL_REVIEW_END
