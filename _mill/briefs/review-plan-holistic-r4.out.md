MILL_REVIEW_BEGIN
# Review: Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-reported, unverified)
reviewed_file: plan/
date: 2026-08-08
```

## Findings

### [BLOCKING:consistency] Title-based dedup can silently drop a distinct finding, breaking the file/envelope invariant
**Location:** batch 1, cards 2 and 4 (`extract_findings`, `rewrite_demoted_findings`).
**Issue:** Card 2 dedups the concatenated heading+yaml scan "by title, keeping the first occurrence" with no scoping to cross-mechanism duplicates. If two genuinely distinct findings from the SAME mechanism happen to share an identical heading title (plausible for a reviewer emitting formulaic titles like "Missing test coverage" twice), one is silently dropped from `findings`/`blocking_count`. Worse, Card 4's rewrite requires matching "each heading exactly once" — if the dropped title was a duplicate `### [BLOCKING:<cls>]` heading, the un-extracted occurrence is never rewritten to `[NIT:<cls>]`, leaving a `BLOCKING` heading on disk that the envelope no longer counts. This is precisely the file/envelope divergence the `demotion-rewritten-into-review-file` Decision exists to prevent.
**Fix:** Scope the dedup explicitly to "same title present in both mechanisms" (join key = title, but only collapse across heading vs. yaml, not within a single mechanism), or note in Card 2/8 that within-mechanism title collisions are an accepted, tested risk and specify the intended behavior (drop vs. keep both) explicitly, with a Card 8 test for it.

## Verdict

REQUEST_CHANGES
Title-based dedup can drop a duplicate-titled finding and desync the file from the envelope in an edge case central to the task's core guarantee.
MILL_REVIEW_END
