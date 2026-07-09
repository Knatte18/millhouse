All source files check out against the plan. Findings below.

MILL_REVIEW_BEGIN
# Review: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-09
```

## Findings

### [NIT] Duplicated ref-resolves-as-commit check
**Location:** `plugins/codeguide/scripts/resolve_scope.py:127` and `:221`
**Issue:** `_no_arg_scope`'s `--parent` fallback check and `_resolve_ref_token` both run the identical `_git(toplevel, "rev-parse", "--verify", "--quiet", f"{X}^{{commit}}")` pattern independently.
**Fix:** Optional follow-up — factor into a small `_ref_resolves(toplevel, ref) -> bool` helper; not worth blocking on given the two call sites are only ~90 lines apart in the same file.

### [NIT] Empty-candidate edge case for a bare `..HEAD` token
**Location:** `plugins/codeguide/scripts/resolve_scope.py:220-222`
**Issue:** A literal single-token input of exactly `"..HEAD"` strips to an empty `candidate`, producing the malformed git invocation `rev-parse --verify --quiet ^{commit}`; git will simply fail this (returning None, falling through to `_explicit_scope`), so behavior is safe but untested.
**Fix:** No action needed — purely theoretical input no real caller produces; noting for completeness only.

## Verdict

APPROVE
All three batches match their plan cards; cross-batch contracts (`--parent` CLI/kwarg, `resolve_for_codeguide`, `$CHK..HEAD`) are consistent end-to-end.
MILL_REVIEW_END
