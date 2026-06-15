MILL_REVIEW_BEGIN
# Review: Fix millpy-implement.py finalize to accept (or not require) --session-id/--start-sha

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-15
```

The discussion is precise and fully source-grounded. Every code claim verified against the tree: implement's argparse has only `batch_name`/`--stage`/`--agent-output` (millpy-implement.py:71-84); finalize reads `start_sha`/`implementer_session` from status.md (lines 174,177); prepare calls `emit_prepare` without `start_sha` (line 262), which drops the field when None (_implementer_common.py:125-126); fix.py declares both flags with `default=None` (millpy-fix.py:95-104) and its finalize uses `args.start_sha`/`args.session_id` (lines 201,203); SKILL.md line 129 threads `--session-id`/`--start-sha (when not null)` to fix and implementer CLIs; the test-fix-finalize.py mock + `call_args[1].get(...)` passthrough pattern (lines 167-172) is exactly the proposed model. The finalize-stage fixture and patch points already exist in test-millpy-implement.py (test_14, lines 348-370), so the proposed unit test is feasible as written.

Scope is unambiguous (accept-but-ignore both flags; no behavior change; no fix.py/SKILL/prepare edits). Both decisions carry rationale plus concrete rejected alternatives. Constraints (ASCII help text, repo test harness, no-regression) are acknowledged. The single failure mode -- the actual bug -- is well characterized, and the vestigial-session_id concern is explicitly scoped out with justification.

## Verdict

APPROVE
Complete, accurate, source-verified; ready for plan writing with no gaps.
MILL_REVIEW_END
