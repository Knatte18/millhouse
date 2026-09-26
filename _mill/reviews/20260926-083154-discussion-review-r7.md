MILL_REVIEW_BEGIN
# Review: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
duration_s: 269.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] TaskStop invoked as a new, unverified capability
**Section:** Decisions > Reply protocol: message first, file as attachment and safety net
**Issue:** The mid-wait message-arrival branch calls `TaskStop` to cancel the recorded `Monitor` `task_id` on an id match. Every existing reference to `TaskStop` in this repo (`mill-go-base/SKILL.md`, `mill-plan/SKILL.md`) treats it as an external/operator-initiated stop a skill only reacts to; no skill has ever invoked it as a tool, and `harness-tool-contracts.md`'s Monitor section documents no way to cancel a live poll early. No fallback is stated if the call errors or the tool doesn't exist in the build.
**Fix:** State the behavior when `TaskStop` fails or is absent (e.g. proceed to `consume` anyway and accept an orphaned, later-expiring Monitor task), or drop the call and let the poll simply find the file already written.

### [NIT:consistency] "no target" has two different terminal behaviours
**Demoted-from:** BLOCKING
**Section:** Decisions > Two entry modes, one mechanism > Direct mode
**Issue:** "neither [thread-name nor parent_thread] -> tell the user direct mode cannot start and stop" reads as aborting activation outright. The separate "Direct-mode fallback" bullet lists "no target" as one of the triggers that instead "ask[s] the operator directly with the same numbered questions" — a different outcome for what reads as the same condition.
**Fix:** Clarify whether "no target" at `/ask-thread` invocation is the same event as "no target" in the fallback list; pick one terminal behaviour (abort-and-stop vs. fall through to asking the operator).

## Verdict

REQUEST_CHANGES
Two unresolved design points: an unverified TaskStop call with no failure path, and a contradictory "no target" outcome.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
