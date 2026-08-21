Fixer directive complete: applied the single BLOCKING finding (updated `00-overview.md`'s stale single-file-scope Decision and file list to include the documented test-scope-extension), committed as `d36455cd`. Verify (`run-all.py`) shows only the 3 pre-existing, unrelated failures already recorded in the batch's baseline.

`{"status":"success","commit_sha":"d36455cde0feab437c6ee3fcd1ea904ee7aec789","session_id":"3b98becf-e831-4d37-ad58-c126aacd5456"}`

---

Builder note: `millpy-fix.py --stage finalize --scope holistic` initially misclassified this round as
`stuck_type: verify` because it never forwards `batch_verify_baseline`/`module_verify_baseline` to
`finalize_from_output` for holistic scope (confirmed by reading `millpy-fix.py`'s finalize-stage
branch -- a real gap, documented in `_mill/plan/00-overview.md`'s `## Prior failure` section and
flagged for mill-self-report). A self-resolve retry (fresh cold fixer dispatch, session
`26bc56a5-...`) correctly found the fix already applied and no actionable diff, confirming the round
was genuinely done. Re-invoking `_implementer_common.finalize_from_output` directly with the correct
`batch_verify_baseline` (the same corrected 3-failure baseline recorded on the batch) against this
original output confirms `status: success`, `commit_sha: d36455cde0feab437c6ee3fcd1ea904ee7aec789`.
