MILL_REVIEW_BEGIN
# Review: Batch verify/baseline/completeness gates produce false positives or time out

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [GAP] Undefined gate behavior when `cards_done` is absent
**Section:** Decisions -> completeness-recount-cards-done (#660)
**Issue:** The gate rule "stuck iff `card_ids - set(cards_done)` non-empty" and the resume backstop (`already_complete: true`, itself derived from `cards_done`) both require the field to be present; an absent `cards_done` (non-compliant/forgetful implementer, or pre-upgrade session the decision itself names) yields `set()` -> `card_ids` non-empty -> stuck, and the backstop can never fire -> the exact infinite-loop the fix targets recurs, and complete no-verify batches regress vs. today's count heuristic.
**Fix:** Specify the absent-`cards_done` fallback explicitly (e.g. fall back to the old `content >= card_count` count check, or fail-open) and add a test for the field-entirely-absent case, not just missing entries.

### [NOTE] Drop heuristic can remove a relevant unchanged regression test
**Section:** Decisions -> batch-verify-list-validation (#638)
**Issue:** Dropping files that are both (not in Files-Touched) AND (byte-identical to `main`) also discards a legitimately-relevant regression test that exercises the touched code but wasn't itself modified; byte-identity to `main` proves "unchanged," not "unrelated," so the chosen heuristic still under-includes (less than exact-match-only, but not zero, contrary to the rejected-alternative framing).
**Fix:** Record the accepted coverage trade-off, or narrow the drop to files that also don't reference/import the batch's touched modules.

### [NOTE] #642 trigger is asymmetric (added-tag only)
**Section:** Decisions -> go-build-tag-retiering-check (#642)
**Issue:** The gate fires only on newly-added `//go:build` lines in previously-untagged files; a build tag that is modified or removed (also a re-tiering that can pull a file into or out of the default build and break the Tier-1 compile) does not trigger the untagged compile check.
**Fix:** State this asymmetry as an explicit scope boundary, or broaden the diff trigger to any build-tag change on a `.go` file.

## Verdict

GAPS_FOUND
One correctness gap: the #660 gate/backstop are undefined when `cards_done` is absent.
MILL_REVIEW_END