MILL_REVIEW_BEGIN
# Review: Agent-mode dispatch: envelope fields and session/runtime state are unreliable

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [GAP] start_sha source undefined on session_id-reuse path
**Section:** Decisions — "session_id reuse on prepare re-run" + "start_sha in the implement-prepare envelope"
**Issue:** The reuse path skips the `else`-branch `git rev-parse HEAD` (skips capture_snapshot/set_batch_fields/commit), but decision #1 makes the prepare envelope emit `start_sha=start_sha` at the shared call site (`millpy-implement.py:577`) — on reuse `start_sha` is then unbound or a fresh (wrong) value, contradicting the reused session's original baseline.
**Fix:** State that the reuse path reads `start_sha` from the existing batch entry (as `--resume-incomplete` does at line 442) so the envelope carries the original baseline, not a freshly-captured HEAD.

### [GAP] Permission-allowlist settings surface left undecided
**Section:** Scope / Decisions — "Permission allowlist for background implementer/reviewer dispatch"
**Issue:** The location is hedged as `.claude/settings.json` "or the equivalent plugin-shipped settings surface, whichever this repo's convention is" — but the two candidates differ in reach: a millhouse repo-root `.claude/settings.json` won't apply when mill-go orchestrates in an external repo (CLAUDE.md: external repos have no millhouse checkout), so whether the fix actually suppresses the prompt depends on which surface is chosen.
**Fix:** Pin which settings surface actually governs the `mill-implementer`/`mill-reviewer` subagent permission mode (repo-root vs plugin-shipped), so #631's fix reaches background dispatches regardless of the orchestrated repo.

### [NOTE] --actual-model rewrite assumes reviewer echoed the line
**Section:** Decisions — "reviewer_model / audit-trail accuracy"
**Issue:** The fix regex-rewrites the `reviewer_model: <value>` line in `raw_text` before `write_review_file`; if the reviewer omits or malforms that line, the rewrite silently no-ops and the audit value stays wrong/absent.
**Fix:** Note the missing/malformed-echo case — decide whether finalize injects the field when absent or accepts today's behavior for malformed reviews.

## Verdict

GAPS_FOUND
Two concrete unresolved interactions (reuse-path start_sha, allowlist location) block plan writing.
MILL_REVIEW_END
