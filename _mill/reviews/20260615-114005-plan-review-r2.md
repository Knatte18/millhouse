MILL_REVIEW_BEGIN
# Review: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [NIT] Card 3(b) regression claim mismatches current resolve_ref_paths
**Location:** Batch 1 / Card 3
**Issue:** Card 3(b) frames the #471 doubling test as a regression for `resolve_ref_paths`, but that function already tries `git_root/root/raw` as a fallback (`_review_common.py:656`), so it does not currently double — only `resolve_existing_paths` (no `git_root/root/raw` candidate, `:723`) genuinely regresses.
**Fix:** Re-scope the 3(b) note so the doubling-regression value attaches to `resolve_existing_paths`; for `resolve_ref_paths` the change is the documented reorder-to-primary, not a doubling fix.

### [NIT] Card 7 prose names args.skip_check; actual dest is skip_checks
**Location:** Batch 3 / Card 7
**Issue:** The prose says "Honor `args.skip_validate` and `args.skip_check`", but the parser dest is `skip_checks` (millpy-review-plan.py:69); only the embedded code snippet uses `frozenset(args.skip_checks)` correctly.
**Fix:** Change the prose to `args.skip_checks` so the implementer does not introduce an AttributeError from the prose.

## Verdict

APPROVE
Line numbers, function refs, and decisions verified against source; only two cosmetic prose nits.
MILL_REVIEW_END