MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3

```yaml
duration_s: 372.7
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [BLOCKING:design] literal-enumeration-majority: self-token's own tally membership unspecified
**Section:** Decision `literal-enumeration-majority`
**Issue:** The new rule ("non-shaped tokens are a majority... of the line's backtick tokens") doesn't say whether the token currently being tested counts toward its own shaped/non-shaped denominator. The superseded rule explicitly scanned "other than this occurrence itself" (`_is_literal_enumeration_exempt`, current code). On an even-total-token line, including vs. excluding self can flip a tie into a majority or vice versa — both cited repro lines have odd totals (3), so this gap isn't exercised by either verification example.
**Fix:** State explicitly whether the tally counting is over all backtick tokens on the line (including the tested occurrence) or over siblings only (excluding it), and how an exact tie is meant to resolve beyond "more non-shaped than shaped."

### [BLOCKING:design] line-join-refactor widens clause-scoped helpers with no line/bullet boundary
**Section:** Decision `line-join-refactor`
**Issue:** `_RE_CLAUSE_BOUNDARY = re.compile(r"[,;:.]")` (line 138) has no newline or bullet-boundary member. Extending `_is_non_dependency_negation_exempt`/`_is_contrast_citation_exempt` (via `_clause_bounds`) onto the whole joined Requirements body means a "clause" can span two physical lines/bullets that carry no comma/semicolon/colon/period between them — e.g. one bullet ending "...`x.py`" with the next starting "without needing it" — reproducing, at clause scope, the exact new cross-line false-negative class this same decision explicitly rejects for the three unconditional exemptions ("a new false-negative class... does not want").
**Fix:** Either add a physical-line/bullet-boundary marker to the boundary set used when computing joined-text clause bounds, or cap `_clause_bounds` from crossing the offset table's line breaks, before widening it to joined text.

### [BLOCKING:design] Rejected clause-scoping rationale misstates #1122 line 99's punctuation
**Section:** Decision `literal-enumeration-majority`, Rejected
**Issue:** Claims line 99 ("`millpy-merge-in-subagent.py`'s `verify-fix` mode never calls `finalize_from_output`/") "has no comma/semicolon/colon/period to split it into separate clauses" so "clause-scoping alone leaves all 3 tokens in one clause." The first quoted token itself contains a period (the `.py` extension), and `_RE_CLAUSE_BOUNDARY`'s `[,;:.]` match operates on the raw line text regardless of backtick delimiters — `_clause_bounds` would in fact split there, putting only `verify-fix`/`finalize_from_output` (2 tokens) in the shared clause, not all 3.
**Fix:** Correct the rationale to state clause-scoping fails because `verify-fix` and `finalize_from_output` share one clause with each other (no boundary punctuation *between those two specifically*), not because the line has zero boundary punctuation anywhere — the current wording could mislead re-verification during implementation.

## Verdict

REQUEST_CHANGES
Three design gaps in the two newest decisions need resolving before plan writing.
MILL_REVIEW_END
