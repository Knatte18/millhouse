MILL_REVIEW_BEGIN
# Review: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Resume brief has no start_sha wiring
**Section:** Scope (resume-after-incomplete) / `start-sha-preserving-resume`
**Issue:** The resume directive instructs the implementer to run `git log <start_sha>..HEAD` and the decision says the resume-prepare "passes the original `start_sha`" into the re-rendered brief, but the implementer brief template exposes only `<PROJECT_ROOT>` and `<SESSION_ID>` (no `<START_SHA>` token), and the discussion never states how the concrete start_sha reaches the rendered brief — leaving the load-bearing skip-committed-cards range undefined.
**Fix:** Decide and state the mechanism: either add a `<START_SHA>` render token wired through the resume-prepare `_render.render` call, or have the brief instruct the implementer to self-derive the range from the most-recent `"mill-go: start batch"` housekeeping commit (which the design already keys on).

### [NOTE] commit_sha omitted on completeness-gate incomplete envelopes
**Section:** `incomplete-carries-commit-sha` / `reclassify-rename-all-callers`
**Issue:** The decision states "all `incomplete` envelopes carry `commit_sha`," but the primary #574 detection path — `_batch_completeness_stuck` results printed at `_implementer_common.py` ~946/1059/1136/1220 — attaches no `commit_sha` today (only the reclassify paths do, via the membership guards), and the discussion's parity rule ("same paths that attach it for `transient` today") leaves those completeness-gate envelopes without it; the test plan (line 154) only asserts commit_sha for the reclassify path.
**Fix:** Narrow the blanket claim to the reclassify-after-verify-failure paths, or explicitly require the completeness-gate callers to attach `commit_sha` too, so a plan writer isn't pulled between the universal statement and the implied implementation.

## Verdict

GAPS_FOUND
One load-bearing wiring detail (start_sha into the resume brief) is unspecified; one minor envelope-parity inconsistency.
MILL_REVIEW_END
