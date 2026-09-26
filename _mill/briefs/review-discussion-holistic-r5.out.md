MILL_REVIEW_BEGIN
# Review: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] Disable gate silently overrides an explicit `--to` target
**Section:** Decisions - "Script and CLI shape" / Constraint comment on `parent_escalation_timeout_minutes`
**Issue:** `prepare()` checks `minutes <= 0 -> escalate:false, reason:"disabled"` before resolving the target (confirmed in `_ask_thread.py`'s current `_ask_parent.prepare`, order unchanged by the discussion's decision). Direct mode reuses this same gate, so an operator running `/ask-thread <name>` with an explicit `--to` still gets silently downgraded to "ask the operator directly" whenever the hub has escalation disabled (`timeout: 0`) — even though the operator explicitly named a target. The config-comment decision says the value "bounds both modes" (a duration), but the actual behaviour at 0 is an on/off kill switch, which is a different semantic reused without discussion.
**Fix:** State whether an explicit `--to` target should bypass the `disabled` gate (direct mode is operator-invoked, not autonomous escalation), or explicitly accept the current silent-downgrade behaviour and say so in the config comment instead of "bounds both modes".

## Verdict

REQUEST_CHANGES
One BLOCKING: the disable-timeout gate's interaction with an explicit direct-mode target is undecided.
MILL_REVIEW_END
