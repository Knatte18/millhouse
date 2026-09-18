MILL_REVIEW_BEGIN
# Review: _plan_validate.py _resolve_symbol_files: naive whole-file text search, no declaration-form check

```yaml
duration_s: 124.0
verdict: APPROVE
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: /home/knatte/Code/millhouse/wts/plan-validate-context-completeness-symbol-branch-bugs/_mill/discussion.md
date: 2026-09-18
```

## Findings

### [NIT:consistency] Go grouped `type (...)` blocks not covered, unlike the documented Python gap
**Section:** Decision `declaration-form-regex`, Go bullet. **Issue:** The Go regex set handles grouped `const (...)`/`var (...)` blocks via the open-group counter but omits Go's equally-valid grouped `type (...)` block form (`type (\n\tFoo struct{}\n)`), so a symbol declared only that way yields zero matches (false negative) — an accepted-residual-gap class the discussion explicitly documents for Python's class-body-attribute case but leaves silent here. **Fix:** Either extend the open-group counter to also track `type (`, or add one sentence naming this as an accepted residual gap, matching the Python precedent.

## Verdict

APPROVE
Claims cross-checked against source (lines 1823-2037, 2190-2500, test fixtures) are all accurate; only a minor documentation-symmetry gap found.
MILL_REVIEW_END
