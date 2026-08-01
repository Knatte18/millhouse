MILL_REVIEW_BEGIN
# Review: Non-interactive pipeline: only mill-start's interview may prompt the operator — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (Sonnet 5 per harness identification)
reviewed_file: plan/
date: 2026-08-01
```

## Findings

### [NIT] Nit-enforcement gate self-resolve lacks explicit audit-trail append
**Location:** Batch 4 (mill-go-handoff-gates), Card 8
**Issue:** Unlike Cards 9, 10, and 12 (each of which appends a `_status.append_phase(status_path, "self-resolved-...", ...)` row before/after its self-resolve action), Card 8's NIT-fix dispatch never explicitly appends a `self-resolved-nits`-style row, even though Shared Decision `audit-trail-via-status-timeline` states "every self-resolve action" does this and explicitly lists `mill-go-handoff-gates` as in scope.
**Fix:** Either add an explicit `_status.append_phase(status_path, "self-resolved-nits", ...)` call to Card 8's requirement text, or note in the card body that the downstream `nits-fixed-<scope>` marker (already written by the NIT-fix pass's `--stage finalize` call, per the existing "Manual recovery note") is the intended audit trail for this site, so the Decision's blanket wording is not silently under-satisfied.

## Verdict

APPROVE
Plan is internally consistent, byte-exact against source, DAG-valid, and faithfully implements every Shared Decision; only a minor audit-trail documentation gap found.
MILL_REVIEW_END
