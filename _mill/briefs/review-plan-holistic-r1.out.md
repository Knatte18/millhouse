MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable from within the session)
reviewed_file: plan/
date: 2026-08-10
```

## Findings

### [NIT:scope] Card 1's Context omits `_notify.py` despite Requirements naming `_notify.notify`
**Location:** Batch 1 / Card 1 (#810) **Issue:** Requirements prescribes three `_notify.notify("mill-go.blocked", ...)` calls, but `_notify.py` is not in Card 1's `Context:` (only `_status.py` and `_mill/discussion.md` are listed). **Fix:** Add `plugins/mill/scripts/_notify.py` to Card 1's `Context:`, or note explicitly (as is already done for `set_blocked`) that the call shape is copied verbatim from the file's own `### Blocked` precedent (lines 853-862, implicitly readable via `Edits:`) — risk is low since the text is fully verbatim already, not independently authored.

## Verdict

APPROVE
Verified all line numbers, signatures, verify-command quoting/counts, and Shared-Decision fidelity against source; only a trivial Context-completeness nit found.
MILL_REVIEW_END
