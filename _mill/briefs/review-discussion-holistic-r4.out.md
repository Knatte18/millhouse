MILL_REVIEW_BEGIN
# Review: Add mill-quick: skip-review pipeline for simple tasks

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-01
```

## Findings

### [GAP] Reused builder lock does not exclude concurrent same-slug invocation
**Section:** Decisions/concurrency-guard
**Issue:** `_builder_lock.acquire(mill_dir, slug)` (`plugins/mill/scripts/_builder_lock.py`) only raises `LockBusy` when `existing.slug != slug` — i.e. it protects cross-slug contention in one worktree, and is deliberately idempotent (silent refresh, no error) when the SAME slug re-acquires, specifically to support self-resume after a crash. Since a worktree hosts exactly one slug for its lifetime, two concurrent `mill-quick` (or `mill-go`) invocations against the same task always pass the same slug, so the second invocation's `acquire()` call succeeds silently rather than raising — the exact double-invocation race the Decision's rejected-alternative section says the lock closes ("preventing two concurrent sessions from mutating status.md/committing on the same task branch") does not actually get closed by this mechanism.
**Fix:** Either document this as an accepted limitation (the lock only guards cross-slug/worktree contention plus crash-restart bookkeeping, not same-slug double-invocation) or specify a different exclusion check (e.g. compare a session-scoped token, not just slug) before relying on it as the concurrency guard.

### [NOTE] Lock release undocumented for precondition-check-failure halt path
**Section:** Decisions/concurrency-guard
**Issue:** The Decision states the lock "Releases the lock at both terminal paths (done and blocked)" but the Scope's "Precondition checks before any edit" (wiki `status == active`, `plan: null`) is a third halt path whose ordering relative to lock acquisition is unspecified — if it runs after acquisition and fails, no release is documented. Given `_builder_lock`'s same-slug idempotent-reacquire (see the GAP above), a self-leaked lock would self-heal on the same task's next invocation, so impact is low, but the ordering/release-completeness gap is still worth stating explicitly for the plan writer.
**Fix:** State explicitly that the lock is acquired only after all pre-lock precondition checks pass, or that every halt path (not just done/blocked) releases the lock.

## Verdict

GAPS_FOUND
Builder-lock reuse for concurrency-guard does not deliver the same-slug double-invocation protection the Decision claims.
MILL_REVIEW_END
