MILL_REVIEW_BEGIN
# Review: Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (self-assessed)
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [NIT] Card 2 mischaracterizes existing SKILL.md style
**Location:** Batch 01 / Card 2
**Issue:** Card claims `.get()` reads "match the existing script's defensive style," but the current Step 6 snippet uses direct subscript (`result["action"]`, `result['moved_aside_to']`) everywhere, not `.get()` — the rationale is inaccurate even though the `.get()` instruction itself is correct and harmless.
**Fix:** Rephrase the rationale to note this introduces `.get()` usage rather than claiming it matches existing style.

### [NIT] Card 8 insertion point isn't actually grouped with other test_load_* entries
**Location:** Batch 03 / Card 8
**Issue:** The card says the new registration is "grouped with the other test_load_* entries," but the insertion point (immediately after `test_load_falls_back_to_reviewers_yaml` at ~line 1172) sits between `test_validate_role_refs_missing_raises` and `test_validate_role_refs_catches_bad_implementer_model` — not near the main `test_load_*` cluster (lines 1151-1162).
**Fix:** Drop the "grouped with" claim or pick an insertion point actually adjacent to the main `test_load_*` cluster; functionally harmless either way.

## Verdict

APPROVE
Plan is thoroughly source-grounded (line refs, call-site counts all verified accurate); only cosmetic rationale nits found.
MILL_REVIEW_END
