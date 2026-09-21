MILL_REVIEW_BEGIN
# Review: _plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps

```yaml
duration_s: 292.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-21
```

## Findings

### [NIT:consistency] cs-member-regex-tightening's own regression example can't match cs_member_re
**Demoted-from:** BLOCKING
**Section:** Testing > cs-member-regex-tightening. **Issue:** the positive/regression example
`public InvalidOperationException Custom { get; }` cannot match `cs_member_re`
(`_plan_validate.py:2149-2151`, tightened form still requires `\bInvalidOperationException\b\s*[({;=]`)
because `InvalidOperationException` here is a return type, not immediately followed by `({;=` — the next
non-whitespace char is `Custom`. Verified against source: this line fails to match under both the old
and the new regex, so the described test would not actually exercise the "no `new`" fix at all.
**Fix:** replace the example with a case where the symbol itself is the declared member name directly
before punctuation, e.g. `public int InvalidOperationException { get; set; }` (no `new` between modifier
and symbol, symbol immediately precedes `{`).

### [NIT:decision] requirements-quote-indent-drift fix-table row content left unspecified
**Section:** Scope (In) / Technical context, fix-table row 391. **Issue:** unlike
`verify-tags-package-scoping`, which fully dictates the rewritten row's wording, this item only says the
row must be "updated to describe the new message shape" — no guidance on the actual remedy text (e.g.
whether to instruct computing `|sibling_indent - anchor_indent|` and strip/add that many spaces, mirroring
the existing strip/add rows). **Fix:** add one sentence to the Scope/Decision stating the intended
remedy phrasing (or explicitly note it's left to plan-writing discretion), so the planner isn't
improvising fixer guidance for a check message with no prior fix-table precedent.

## Verdict
APPROVE
One BLOCKING: the cs-member-regex-tightening Testing example doesn't actually exercise the regex fix.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
