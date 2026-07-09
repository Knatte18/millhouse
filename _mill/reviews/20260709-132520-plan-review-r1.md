MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-09
```

## Findings

### [BLOCKING] Card 11 test never runs — not added to test list
**Location:** batch 3 / card 11
**Issue:** test-config.py executes only functions listed in `main()`'s `tests = [...]` array (line 1305-1352); the card defines `test_real_template_implementer_model_not_weak_tier` but its 5 numbered steps never add it to that list, so the function is dormant and the batch verify's claimed coverage is false.
**Fix:** Add a step requiring the new function be appended to the `tests` list in `main()`.

### [NIT] Card 11 duplicates an existing, stricter guard
**Location:** batch 3 / card 11
**Issue:** `test_implementer_model_default_is_sonnethigh` (test-config.py line 1201) already loads the real template directly and asserts `roles.implementer.model == "sonnethigh"` (stricter than the proposed `in allowed_tiers`), so the new test adds no regression coverage the file lacks.
**Fix:** Drop card 11, or have it extend/reference the existing test rather than add a weaker near-duplicate.

### [NIT] Card 2 case placement/number is contradictory
**Location:** batch 1 / card 2
**Issue:** The card says place the new case "immediately after [Case 12]" yet "renumber as Case 64, following the current highest case 63" — physically inserting a Case 64 between Case 12 and Case 13 is inconsistent.
**Fix:** State one location unambiguously (append after Case 63 as Case 64, or place near Case 12 and pick a non-conflicting label).

## Verdict

REQUEST_CHANGES
Card 11's test is dormant (unregistered) and redundant with an existing stricter guard; batches 1-2 verify clean.
MILL_REVIEW_END