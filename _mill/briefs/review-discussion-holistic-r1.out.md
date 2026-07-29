MILL_REVIEW_BEGIN
# Review: Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] push_failed has no defined value for the no-push "noop" action
**Section:** Decision "push_failed reporting shape" / mill-merge Step 6
**Issue:** `create_or_resolve`'s `noop` branch (existing_sha == target_sha, verified in `_archive_tag.py` lines 84-90) attempts no push and is explicitly excluded from "every push it attempts" — its returned dict would have no `push_failed` key at all. mill-merge Step 6 is specified to "read the new `push_failed` field" and warn "when set", with no mention of a missing-key case; a literal `result["push_failed"]` read (matching the existing unconditional `result["action"]`/`result["tag"]` reads in SKILL.md) will KeyError on the common re-run-with-nothing-changed path.
**Fix:** specify that `push_failed: False` (and `push_error: None`) is also returned on the `noop` path, or explicitly instruct Step 6 to use `.get("push_failed", False)`.

### [GAP] moved_aside performs two independent pushes but the decision only defines one push_failed/push_error pair
**Section:** Decision "push_failed reporting shape"
**Issue:** the `moved_aside` action issues two separate `git push` calls (moved-aside-tag push, then primary-tag push — `_archive_tag.py` lines 154-161), but the decision defines a single scalar `push_failed`/`push_error` on the return dict "computed uniformly across all four push call sites." It doesn't say how two independent results combine (OR? last-wins? first-wins?), so the operator warning may report failure without indicating which of the two tags actually failed to push, or silently swallow one failure if only one field is written per push.
**Fix:** specify the combination rule for the two pushes in `moved_aside` (e.g., `push_failed = OR of both`, `push_error` labels which push(es) failed), or state that per-push results are tracked separately.

### [NOTE] Call-site count for the untouched write_to(wiki_root) sites is internally inconsistent
**Section:** Out / Technical context (`_test_registry`)
**Issue:** Out section says "~7 existing test call sites"; Technical context's own breakdown (`test-agent-mode-dispatch.py` x1, `test-review-code-flow.py` x6, `test-review-plan-flow.py` x2, `test-review-discussion-flow.py` x1) sums to 10, and the actual repo count is `test-review-code-flow.py` x7 (not x6) — 11 total across the 4 files. Verified all sites still use `"test_stub"` or a real-template-resolvable reviewer, so the "harmless no-op" conclusion itself still holds.
**Fix:** correct the count in a future pass; doesn't change the "leave untouched" scope decision.

### [NOTE] Hardcoded 40-char SHA validation assumes SHA-1 object format
**Section:** Decision "commit_sha: brief wording + one finalize gap" (b)
**Issue:** the proposed guard rejects anything that isn't a well-formed 40-char hex SHA; a repo using git's newer SHA-256 object format would produce a valid 64-char `git rev-parse HEAD` output that this check would then wrongly treat as bad. No evidence this repo/task uses SHA-256, so low real risk.
**Fix:** either accept as-is (SHA-1 assumed throughout this codebase already) or note the check should accept 40-or-64 hex chars for future-proofing.

## Verdict

GAPS_FOUND
push_failed's shape is underspecified for the noop and double-push moved_aside cases.
MILL_REVIEW_END
