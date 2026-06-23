MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-23
```

## Findings

### [NIT] "single success-emit point" wording in card 4 is inaccurate
**Location:** Batch 2 / Card 4 (requirement 3)
**Issue:** `_forward_output` has several success-emit points (parsed-success at the line-370 region, plus inferred-success emits in the no-JSON fallback); calling it "the single point" risks the implementer wiring the marker only into one branch or all of them.
**Fix:** Reword to "the parsed-success emit path (where a fixer's reported `status == "success"` JSON is about to be printed)" — that is the path a `--nits-only` fixer success actually takes; inferred-success paths need no marker.

### [NIT] Card 5 review-file location mechanism left implicit
**Location:** Batch 2 / Card 5 (and Card 7)
**Issue:** "Locate that scope's FINAL (latest-timestamp) code-review file" does not name the filename convention used to match per-batch (`RE_BATCH`: `*-code-review-<batch>-rN.md`) vs holistic (`RE_SIMPLE`: `*-code-review-rN.md`) files; both regexes are in-context via `_review_common` but unnamed.
**Fix:** Name `_review_common.RE_BATCH` / `RE_SIMPLE` (already importable) as the matchers for per-batch vs holistic review filenames, so the implementer does not hand-roll a fragile glob.

## Verdict

APPROVE
Plan is well-grounded, DAG-valid, sequentially numbered, with accurate cross-card contracts; only two non-blocking wording nits.
MILL_REVIEW_END
