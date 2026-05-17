I have enough information to write the review. All claims have been verified against source files.

# Review: 61 (A) — Review pipeline fixes (avhenger av 60)

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-17
```

## Findings

### [NOTE] parse_verdict already handles non-leading yaml; part 1 is done
**Section:** Problem (#315), Scope In, Decision parse_verdict-yaml-search-strategy
**Issue:** The discussion says "The scanner expects a leading yaml block" and calls for a "rewrite". The current `parse_verdict` (`_review_common.py:984-989`) already scans all lines for the first `` ```yaml `` fence, and `test-review-common.py:398-401` already asserts a prose preamble + yaml passes. "Part 1" of #315 is already implemented.
**Fix:** Clarify that part 1 only requires adding the missing test cases from the Testing section (multiple yaml blocks, trailing prose, etc.) — not rewriting the scanner. The actual code change is part 2 only (`_review_code.py` and `_review_discussion.py` error envelopes).

### [NOTE] _review_plan.py already has the parse_verdict error envelope
**Section:** Scope In ("and `_review_plan.py` for parity")
**Issue:** `_review_plan.py:607-617` already catches `ReviewError` from `parse_verdict` and writes a well-formed `ReviewResult(verdict="ERROR")`. The "for parity" note suggests this is in-scope to implement, but it's already done.
**Fix:** The plan should mark `_review_plan.py` as verify-only (confirm the existing catch covers all parse paths including the NEED_CONTEXT retry at line 554), not re-implement.

### [NOTE] _review_discussion.py backend scope gap
**Section:** Scope In vs. Decision parse_verdict-error-envelope, Testing
**Issue:** Scope In lists `_review_code.py (and _review_plan.py for parity)` for the error envelope fix, but the Decision explicitly names "`_review_code.run`, `_review_plan.run`, `_review_discussion.run`" and Testing says "Repeat for `_review_plan.run` and `_review_discussion.run`". `_review_discussion.py:122` has the same bare-raise bug. A strict Scope reading could lead to skipping the discussion backend fix.
**Fix:** No change needed — the Decision is the authoritative source and a plan writer following it will correctly include `_review_discussion.py`. Noting the Scope "In" list should mention it explicitly.

## Verdict

APPROVE
All seven bugs are clearly stated, decisions have rationale and rejected alternatives, and no open TBDs exist.