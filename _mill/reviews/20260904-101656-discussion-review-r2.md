MILL_REVIEW_BEGIN
# Review: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps

```yaml
duration_s: 297.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 4.5 (best-effort self-assessment; environment metadata asserts "Sonnet 5"/claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] "session-fresh-mint" phase-append collides with orchestrator resume routing
**Section:** Decision `956-fresh-session-after-self-resolve` (compounding-retry fix). **Issue:** `_status.append_phase` (verified `_status.py:429-460`) mutates *two* things: the `## Timeline` row AND the top-level `phase:` YAML field consumed by `mill-go-base/SKILL.md`'s crash-recovery phase-gate table (`SKILL.md:107-158`), whose widened matcher (`SKILL.md:129-133`) is a closed set + fixed regex list that does not include `"session-fresh-mint"`; an interruption right after this commit leaves `phase: session-fresh-mint` on disk, which lands on the table's `any other -> surface + halt` row instead of resuming. The Rejected bullet's "harmless" claim only evaluates effect on `_prepare_reuse_entry`, never on this shared field. **Fix:** either use a mechanism that doesn't overwrite the task-level `phase:` (e.g. a status.md marker outside `append_phase`, or extend the SKILL.md phase-gate widened set/table to route `session-fresh-mint`) — but "Out" scope currently forbids touching SKILL.md's escalation paths, so this needs an explicit decision, not silence.

### [BLOCKING:design] Timeline reader decision rests on a false "no reader exists" premise
**Section:** Decision `956-timeline-reader-needed`. **Issue:** `_status.py` already exposes `read_full(status_path) -> {"yaml": dict, "timeline": list[str]}` (verified `_status.py:746-788`, listed in the module's own Public API docstring) and `phase_entry_timestamp` (`_status.py:818-870`) already demonstrates parsing timeline rows by `row.split(None, 1)[0]` phase-token — directly contradicting the Technical Context's claim "consumed nowhere currently — no reader exists" and this Decision's premise that a new `_status.read_phases` helper must be added. **Fix:** correct the Technical Context/Decision to note the most-recent-phase check is `read_full(status_path)["timeline"][-1]`'s token (or a one-line helper reusing `read_full`), removing the unnecessary new-helper work item before it reaches mill-plan.

## Verdict

REQUEST_CHANGES
Two false/incomplete premises in the #956 decisions must be corrected before plan writing.
MILL_REVIEW_END
