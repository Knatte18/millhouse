MILL_REVIEW_BEGIN
# Review: _plan_validate: context-completeness fires on forbidding/explanatory file mentions

```yaml
duration_s: 153.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] Word-boundary verb regex breaks the "must-not-regress" baseline test
**Section:** Decisions > "Word-boundary matching (not raw substring)" combined with the r1 Q&A gap fix and Testing's baseline list.
**Issue:** `test_check_context_completeness_clean_prohibition_marker` (line 1951) exempts `"This card must forbid touching \`mill-config.yaml\`."` The r1 Q&A justifies adding `forbid` to the negation set "since the existing test sentence already contains a verb" — but the only candidate verb token is "touching", and the r2 decision commits to strict `\bword\b` boundary matching for the verb set with only the bare infinitive `touch` in the list. `\btouch\b` does not match inside "touching" (no boundary between "h" and "i"), so under the finalized combined design the line has a negation match but no verb match, the AND predicate fails, and the baseline test — explicitly listed as "do not regress" in Testing — would flag `mill-config.yaml` as a missing Context entry, contradicting its own asserted `len(check_errors) == 0`.
**Fix:** Either add inflected forms (or a stemming/prefix rule) to the verb-matching regex, or explicitly decide the verb list matches word-initial substrings (`\bword\w*\b`) rather than exact words, and reconcile this with the "false collision" rationale (e.g. `add`⊂"address" would then also collide) — this needs an explicit, stated resolution, not silent inconsistency between the r1 and r2 fixes.

## Verdict

REQUEST_CHANGES
Word-boundary verb matching, as specified, breaks the explicitly-protected `forbid`-marker regression test.
MILL_REVIEW_END
