MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] `_serialise_batches` hardcoded key order will silently drop `verify_baseline_failures`
**Section:** Decision `gap2-per-batch-baseline-storage`; Technical context `_status.py` bullet
**Issue:** `_status._serialise_batches` (`_status.py:601-636`) is NOT `yaml.safe_dump` (confirmed: `_status.py` never calls `yaml.safe_dump`, only `yaml.safe_load`) — it is a hand-rolled writer that iterates a fixed, hardcoded `order = ["name", "state", "implementer_session", "start_sha", "commit_sha", "review_round", "review_file", "blocked_reason"]` list; any key not in that list is silently omitted from the written yaml even if `set_batch_field` sets it on the in-memory entry dict first.
**Fix:** Add `verify_baseline_failures` to `_serialise_batches`'s `order` list (and correct the Decision's rationale, which currently mis-describes the mechanism as "round-trips via `yaml.safe_dump`") — without this, the new field persists in memory for one call but is silently dropped on every write to `status.md`, making baseline storage a no-op.

### [NOTE] Duration-unit citation slightly overstates source content
**Section:** Decision `gap2-signature-normalization-strips-duration`
**Issue:** The decision cites `_implementer_common.py:542-546` as documenting `<unit>` = `s`/`ms`, but that docstring/comment block only illustrates the `s` (seconds) form (`"(0.00s)"`, `"0.1s"`); it never mentions `ms` anywhere in that span.
**Fix:** Either drop the `_implementer_common.py:542-546` citation for the `ms` half of the unit set, or note that `ms` is a defensive addition not actually attested in the cited source.

## Verdict

GAPS_FOUND
The per-batch baseline field would be silently dropped by `_serialise_batches`'s hardcoded key-order list.
MILL_REVIEW_END
