MILL_REVIEW_BEGIN
# Review: Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; unverified)
reviewed_file: _mill/discussion.md
date: 2026-08-08
```

## Findings

### [GAP] Known-severity + unrecognized-class findings double-count
**Section:** Technical context (four severity-parsing call sites) vs. Decision `unclassified-or-unknown-class-folds-into-blocking`
**Issue:** The widened `parse_blocking_count()` regex `^###\s+\[<severity>(?::(?P<cls>[a-z-]+))?\]\s+` matches `[NIT:badclass]` (or bare `[NIT]`) as a valid NIT heading purely on the severity token, so it lands in `nit_count`. The same finding also gets folded into `blocking_count` by the class-unrecognized check ("counted into the blocking bucket regardless of its stated severity"). Verified in source: today's `count_unrecognized_severity_findings()` only fires when the *severity* token itself is unrecognized, mutually exclusive with the primary count — the class extension breaks that invariant and isn't reconciled anywhere.
**Fix:** State explicitly whether a recognized-severity/unrecognized-class finding is moved out of the primary bucket (not merely added to blocking), and confirm the verdict-derivation Decision accounts for this so a single malformed `[NIT:x]` heading can't silently flip a round to `REQUEST_CHANGES`.

### [GAP] `gaps-found-back-compat` rationale cites paths that never read discussion-review data
**Section:** Decisions / `gaps-found-back-compat`
**Issue:** The rationale for retaining `GAPS_FOUND`/`[GAP]`/`[NOTE]` back-compat cites `_review_plan.py:100-123` (recovery), `:770-793` (resume), and `_nit_gate.py:89` as paths that would throw `ReviewError` on old GAPS_FOUND files. Verified in source: all three filter strictly on `type == "plan"` batch files or code-review files (the Technical Context itself calls `_nit_gate.py` "code-review only"). GAP/NOTE/GAPS_FOUND was always discussion-review-only vocabulary, so none of these three sites can ever encounter it — the cited evidence does not support the decision.
**Fix:** Replace the citation with an actual discussion-review re-read path if one exists (none is identified elsewhere in the discussion), or drop this justification and re-ground the back-compat requirement in whatever real risk motivates it.

## Verdict

GAPS_FOUND
Two GAPs: a class/severity double-counting risk and a factually unsupported back-compat citation.
MILL_REVIEW_END
