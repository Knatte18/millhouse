MILL_REVIEW_BEGIN
# Review: millpy-implement.py / _done_gate.py: Windows baseline teardown, truncated failure reason, ignored --start-sha

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:design] finalize-honors-start-sha cites a nonexistent millpy-fix.py precedent
**Section:** Decisions > finalize-honors-start-sha **Issue:** Rationale claims `args.start_sha if args.start_sha else batch_status.get("start_sha")` is "the same precedence millpy-fix.py's finalize branch already uses" — but `millpy-fix.py` line 481 passes `start_sha=args.start_sha` directly with no status.md fallback anywhere in the file (confirmed via grep: only two `start_sha` assignments exist, neither implements this fallback). **Fix:** Correct the rationale to state this fallback is a new pattern for `millpy-implement.py` (justified on its own safety/consistency merits), not a copy of an existing `millpy-fix.py` mechanism.

### [BLOCKING:scope] Shared "ignored" comment (lines 500-502) covers --session-id too, not just --start-sha
**Section:** Technical context, millpy-implement.py bullet **Issue:** The comment block at lines 500-502 ("These flags are accepted... millpy-implement.py ignores them...") documents both `--start-sha` (503-507) and `--session-id` (508-512) together; the technical context labels 500-507 as "the --start-sha-specific text," which obscures that editing this shared comment also touches --session-id's documented behavior — risking a violation of Scope/Out's "do not touch [--session-id's] ... 'ignored' help text." **Fix:** Clarify that lines 500-502 must be split or reworded so --session-id's "ignored" description is explicitly preserved verbatim while only --start-sha's status changes.

## Verdict

REQUEST_CHANGES
Two BLOCKING findings: a false precedent claim and an under-specified shared-comment edit boundary.
MILL_REVIEW_END
