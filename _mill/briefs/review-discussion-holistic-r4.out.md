MILL_REVIEW_BEGIN
# Review: mill-go: done-gate halt path and cleanliness-gate recovery are under-documented

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] Dead-parent auto-rebind commit skips the file's own audit-trail convention
**Section:** Decision `cleanliness-gate-dead-parent-recovery`, item 3 `outcome: "resolved"` branch.
**Issue:** The auto-rebind commit is only `_status.update_field(...parent...)` + `git commit` — no `_status.append_phase(status_path, "self-resolved-...", ...)` call. Every other self-resolve action in this same file family (handoff.md's `self-resolved-terminal-dirt`, `self-resolved-scope-violation`; SKILL.md's `self-resolved-verify-logic`) writes an `append_phase` marker into the same commit, per the discussion's own Constraints line citing Shared Decision `audit-trail-via-status-timeline` ("no separate `_status.append_phase` audit row **where an existing marker already covers it**") — no existing marker covers a dead-parent rebind, so by that same clause one is required here.
**Fix:** Add `_status.append_phase(status_path, "self-resolved-dead-parent", _timestamp.now_utc_iso())` (or equivalent) to the rebind commit at both call sites (SKILL.md step 2b and handoff.md's terminal gate), folded into the same commit as the `parent:` field update, matching the pattern used by every sibling self-resolve action in this file.

### [NIT:consistency] Fixer-dispatch halt text drops "notify" from the paired lock-release decision
**Section:** Decision `done-gate-fixer-conditional-dispatch`, both re-halt sentences ("halt immediately as today (with the lock-release fix from the decision above)" / "halt ... now including a note that the fixer was already attempted").
**Issue:** Both sentences name only "the lock-release fix," but the decision they point to (`builder-lock-release-all-handoff-halts`) is explicit that its parity fix is `_notify.notify(...)` **and** lock-release together, not lock-release alone — the wording here could be misread as scoping only the lock-release half to this site.
**Fix:** Say "the lock-release/notify fix from the decision above" (or otherwise name both calls) at both sentences for unambiguous parity with the paired decision.

## Verdict

REQUEST_CHANGES
One BLOCKING: dead-parent auto-rebind commit needs its own audit-trail marker per this file's established self-resolve convention.
MILL_REVIEW_END
