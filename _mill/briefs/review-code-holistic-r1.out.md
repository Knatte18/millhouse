MILL_REVIEW_BEGIN
# Review: mill-implementer: commit_sha transcription/truncation and final-status-line reliability — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-04
```

## Findings

None. All three batches' cards are realised exactly as specified:

- Batch 1 (`implementer-brief.md`): both new paragraphs — the "Never restate `commit_sha` in prose" rule and the "Nothing follows the JSON line" rule — are inserted verbatim at the exact locations specified (after the Card-count self-check paragraph / before the JSON-object paragraph; after the Long-session reminder / before `## On review resume`). No other section touched.
- Batch 2 (`git-commit/SKILL.md`): the "Verify the stage before committing" bullet is inserted verbatim between the "Stage files individually" and "Commit with title..." bullets, using `git diff --quiet -- <paths>` per the batch's stated rationale (not `--cached --quiet`).
- Batch 3: `_forward_output`/`finalize_from_output` both gain `commit_sha_field_name: str = "commit_sha"` as the new last keyword parameter, correctly threaded through the `_forward_output(...)` call inside `finalize_from_output`. The pop/rename logic at `_implementer_common.py:1895-1897` matches the plan's two-line replacement exactly, gated on `commit_sha_field_name != "commit_sha"`. Verified via grep that every other `commit_sha`-writing site in the file (`_attach_commit_sha`, verify/transient/incomplete gate-result sites, the two no-JSON-inference-path sites, `emit_prepare_no_dispatch`) is untouched and still hardcoded to `"commit_sha"`.
- `millpy-merge-in-subagent.py`: both conflicts-mode call sites (`--stage finalize`'s `finalize_from_output(...)` and `_run_conflicts`'s `_forward_output(...)` return) pass `commit_sha_field_name="pre_merge_head"`. `_run_verify_fix`'s two `commit_sha` literals are confirmed untouched, as required.
- Test coverage: Case 78/79 in `test-implementer-common.py` and `test_2x_conflicts_finalize_emits_pre_merge_head`/`test_2x_conflicts_full_mode_emits_pre_merge_head` in `test-millpy-merge-in-subagent.py` are present, modeled on their stated exemplars (Case 21, `test_15`, `test_17`), and assert the exact contract described in the plan (field rename, stale-key absence, truncated-SHA discard-and-replace via `#932`).

No out-of-plan files present — the 10-file manifest matches the overview's "All Files Touched" list plus plan/overview files exactly. No cross-batch contract issues, no duplicated helpers, no language pitfalls observed.

## Verdict

APPROVE
All three batches match their plan cards exactly; no BLOCKING or NIT findings.
MILL_REVIEW_END
