MILL_REVIEW_BEGIN
# Review: mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet (harness-reported model ID claude-sonnet-5 / "Sonnet 5"; exact version uncertain beyond that)
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Fork alternative (cold Explore agent) not evaluated
**Section:** Decisions > Fork scope guardrail placement and mechanism (#741)
**Issue:** `mill-go/SKILL.md`'s own "Why not fork?" section states a fork inherits the parent's full tool grant and thereby "loses its read-only guarantee," and `mill-start/SKILL.md:127-132` documents a "cold `Explore` agent" as the established mechanism for exactly this task shape (a broad, mechanical, no-inherited-conversation-needed sweep) precisely because it does not carry that disqualifier. The Rejected list only weighs "strengthen wording" vs. "shared doc" — never "don't fork here, dispatch a non-fork read-only agent instead."
**Fix:** Add a Rejected entry evaluating dispatch of a tool-restricted, non-fork agent (e.g. cold `Explore`) for the research-only case, and state explicitly why fork (with its inherited-context benefit) is still preferred if it is.

### [GAP] context-completeness omits Deletes:/Moves: token sets
**Section:** Decisions > `context-completeness` validator check design (#742)
**Issue:** The check cross-references Requirements: tokens only against Context:/Edits:/Creates:, but `plan-batch.md`'s own template models Deletes:/Moves: as first-class card fields, and Requirements: prose routinely names the file being deleted or renamed (e.g. "delete `old/path.py`"). Such a token false-positives as unresolved, and the fix-table's prescribed remedy ("add to Context:") is semantically wrong for a file about to be deleted/moved.
**Fix:** Extend the per-card token set the check cross-references to include Deletes: and Moves:(source-side) tokens, and add a fix-table caveat for this case.

### [GAP] Post-return git-status check doesn't cover concurrent/mid-flight forks
**Section:** Decisions > Fork scope guardrail placement and mechanism (#741)
**Issue:** The guardrail's detection point is "immediately after the fork returns," but the incident itself involved two forks dispatched in parallel and caught mid-session, before either returned, via manual observation. A single post-return `git status --porcelain` snapshot can't attribute writes to one of two concurrently-running forks, and a still-running rogue fork can accumulate unauthorized writes before its own return ever triggers the check.
**Fix:** Specify how the orchestrator handles multiple simultaneously-dispatched research forks (per-fork attribution and/or a bound on how long a fork may run before an interim check), or explicitly note the guardrail narrows but does not fully close the mid-flight detection gap the incident needed.

## Verdict

GAPS_FOUND
Three GAPs: unconsidered fork alternative, a validator false-positive class, and a concurrency gap in the guardrail's detection design.
MILL_REVIEW_END
