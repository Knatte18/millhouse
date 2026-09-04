MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5, per system self-identification)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] card-numbering claim overstates actual enforcement
**Section:** forward-cross-card-creates-exemption Decision, Rationale ("Global card numbering is unique and sequential across batches (enforced by `_check_card_numbering` ...)"). **Issue:** Read `_check_card_numbering` (plugins/mill/scripts/_plan_validate.py:912-978) directly: it enforces (a) no-gap sequential numbering *within* a batch and (b) no card-number reuse *across* batches — it never checks that a later batch's card numbers are all numerically greater than an earlier batch's. Its own doc comment (line 20) scopes it as "Non-sequential or cross-batch-duplicate", not "monotonic across batches." A plan with batch 01 = cards {4,5,6} and batch 02 = cards {1,2,3} passes this check with zero findings, yet batch 02 executes after batch 01. **Fix:** Either add a cross-batch monotonicity check to `_check_card_numbering` (so "declaring card number > referencing card number" is a sound execution-order proxy), or weaken the rationale's claim and add a fallback safeguard (e.g. also require the declaring batch's file-sort position ≥ the referencing batch's) so the forward-creates direction test cannot silently misfire into a false negative on a malformed-but-currently-legal plan.

### [BLOCKING:decision] `_extract_requirements_text`'s truncation risk vs. new fence tracking left unaddressed
**Section:** quoted-material-exemption Decision + Technical context "Fence tracking" / step 1. **Issue:** `_extract_requirements_text` (line 1742, listed in Scope "In" as a touched helper) locates the Requirements: body boundary with `any_field_header_re.match(lines[j])` **unconditionally** — no fence tracking. The sibling helper `_requirements_fence_aware_body` (line 2235) exists specifically to avoid this: its own docstring says it deliberately does NOT call `_extract_requirements_text` because a fenced quote containing a `- **Field:**`-shaped line would be mistaken for the real field boundary and truncate the fence body. `_check_context_completeness`'s step 1 still calls `_extract_requirements_text`, so `requirements_lines` can already be truncated before the new step-4 fence-state tracking ever sees the rest of a quoted block — undermining the #926 fix on exactly the docs-quoting scenario (quoting an example plan card's own field-header-shaped lines) this task targets. The discussion names `_extract_requirements_text` as in-scope but states no disposition for it. **Fix:** State explicitly whether `_check_context_completeness` switches its step-1 extraction to `_requirements_fence_aware_body` (or an equivalent fence-aware boundary scan), and add a test with a field-header-shaped line inside a Requirements: fence to pin the behavior.

## Verdict

REQUEST_CHANGES
Two BLOCKING gaps: an overstated validator-enforcement claim and an unaddressed fence-truncation interaction.
MILL_REVIEW_END
