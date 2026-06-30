MILL_REVIEW_BEGIN
# Review: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] subprocess/agent resume cannot reuse original start_sha
**Section:** Decisions > subprocess-incomplete-resume, warm-session-resume-recovery; Q&A (review-r2)
**Issue:** The design's safety property — preserve committed cards by reusing the original `start_sha` and skipping already-committed cards via `git log <start_sha>..HEAD` — rests on a false premise about existing mechanics. `millpy-implement.py` has **no `--resume` flag** (args are only `batch_name`/`--stage`/`--agent-output`/`--start-sha`(ignored)/`--session-id`(ignored)/`--round`(ignored)), and the existing `running`-state re-fire (SKILL line 433-446) is a **fresh batch start**: prepare unconditionally captures a NEW `start_sha = HEAD` (millpy-implement.py line 289) and overwrites status.md's `start_sha` (line 300). So "the existing `running`-state resume re-invokes `millpy-implement.py <batch_name> --resume`" is doubly incorrect, and the agent-mode "fresh re-dispatch reusing the existing start_sha" goes through the same prepare path that re-captures it.
**Fix:** Specify the actual mechanism that preserves the original `start_sha` across a resume (a real new flag/path that skips the prepare re-capture and reads the prior `start_sha`), and reconcile it with the "Out" item "No change to subprocess/psmux dispatch mechanics beyond adding an `incomplete` route" — building a start_sha-preserving resume is such a change.

### [NOTE] Fresh start_sha causes a false re-incomplete loop
**Section:** Decisions > false-positive-incomplete-is-safe
**Issue:** Consequence of the GAP above: if a resume re-captures `start_sha` at current HEAD (which already contains Card 15's commit), `_content_commit_count` counts only the newly-added cards, so a genuinely-completed 3-card batch reports 2 < 3 and re-emits `incomplete` — looping (or blocking as "incomplete after resume" in autonomous mode) on complete work.
**Fix:** State that the completeness recount on resume must measure against the original `start_sha`, not a re-captured one, so a finished batch counts all its content commits.

## Verdict

GAPS_FOUND
The start_sha-reuse safety property is unimplementable via the existing resume mechanics the discussion cites.
MILL_REVIEW_END
