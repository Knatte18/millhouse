MILL_REVIEW_BEGIN
# Review: millpy-implement.py / _done_gate.py: Windows baseline teardown, truncated failure reason, ignored --start-sha

```yaml
duration_s: 170.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

Verified against source: `_worktree.py` `remove_safe`/`_is_dir_not_empty_error` (current except-order — `PermissionError` short-circuits before `OSError`'s retry loop — matches the rationale exactly); `_done_gate.py` `run_preflight`/`run_gate` (line ranges 42-91/94-153 exact, truncation block text exact); `_implementer_common.py` `_FAILURE_MARKER_PREFIXES`/`_extract_failure_signatures` (lines 745/750 exact) and `_run_verify_gate`'s enrichment block (lines 933-947, marker shape matches described format exactly); `millpy-implement.py` finalize branch (`start_sha = batch_status.get("start_sha")` at line 721 exact) and the `--start-sha`/`--session-id`/`--round` argparse/comment block (lines 500-521, shared-preamble split claim is accurate — comment vs. help= text are distinct, no Scope contradiction); `millpy-fix.py`'s unconditional `start_sha=args.start_sha` at its finalize branch (line 481, inside `if args.stage == "finalize"` at line 415); `mill-go-base/SKILL.md` line 357's dispatch-thread rule and step 5.5's warm-`SendMessage` "bypasses prepare entirely" / "same standard arguments" language (line 375 confirms "same standard arguments" is a narrower term than the "additionally thread ... --start-sha" clause, so the claim that warm-resume's finalize call can omit `--start-sha` is well-founded, not fabricated); no circular-import risk (`_implementer_common.py`'s own imports do not reach `_done_gate`); named unit tests (`test_15_stage_finalize_accepts_session_and_start_sha_flags` line 828, `test_16_stage_finalize_accepts_round_flag` line 741, both asserting `"STATUS_SHA"`) and the cited WinError-145 test set plus the exact-named PermissionError long-path-fallback test in `test-worktree.py` — all line numbers, names, and quoted behavior match the actual files byte-for-byte.

No CONSTRAINTS.md exists in this repo; the Constraints section's "none beyond existing conventions" is accurate, not an omission. All three Decisions carry rationale and rejected alternatives; both Q&A items are resolved (not left TBD) with stated justification. Scope in/out is unambiguous and each Testing subsection is TDD-concrete with existing-test-flip callouts, not non-committal.

No findings.

## Verdict

APPROVE
All Technical Context and Decision claims independently verified against source; scope, testing, and rationale are complete.
MILL_REVIEW_END
