MILL_REVIEW_BEGIN
# Review: Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-reported; unverified)
reviewed_file: plan/
date: 2026-08-08
```

## Findings

### [BLOCKING:consistency] Card 2's dedup rule contradicts itself on same-mechanism YAML duplicates
**Location:** Batch 1 / Card 2 (`extract_findings`), `_mill/plan/01-core-taxonomy.md` line 54 vs. lines 55 and 57.
**Issue:** Line 54 states the dedup drops "a title produced by the yaml scan ... when an earlier yaml entry already produced it" — that is same-mechanism (YAML-vs-YAML) dedup. The very next lines directly contradict this: line 55 says "Two findings from the **same** mechanism that share a title are both kept," and line 57 says "The cross-mechanism collapse is the only one the `dual-mechanism-scan-preserved` Shared Decision calls for." An implementer cannot satisfy both the second half of line 54 and lines 55/57 simultaneously — for two same-titled findings both expressed only via the fenced `findings:` YAML block, one clause says drop the second, the other says keep both.
**Fix:** Delete the second clause of line 54 ("and a title produced by the yaml scan is dropped when an earlier yaml entry already produced it"). The dedup rule should read only: a yaml-scan title is dropped when the heading scan already produced that title (cross-mechanism only); same-mechanism duplicates (heading-vs-heading, or yaml-vs-yaml) are never deduped, per lines 55–57 and per the Shared Decision itself.
**Note:** Card 8's test list only exercises the same-mechanism-duplicate case for headings ("two same-mechanism headings sharing one title"), not for the YAML mechanism, so this contradiction could ship un-caught by the batch's own `verify:` gate — an implementer resolving it the wrong way (same-mechanism YAML dedup) would silently drop a genuine second YAML finding from `findings`, `nit_count`/`blocking_count`, and leave an un-rewritten `BLOCKING` entry on disk if it were later demoted only once.

## Verdict

REQUEST_CHANGES
Card 2's dedup requirement is internally self-contradictory for same-titled YAML-only findings.
MILL_REVIEW_END
