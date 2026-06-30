Confirmed. Now compiling the review.

MILL_REVIEW_BEGIN
# Review: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: C:\Code\millhouse\wts\mill-review-and-finalize-gaps\_mill\discussion.md
date: 2026-06-30
```

## Findings

### [GAP] millpy-bg.py's MarkerError handler will misreport exhausted-retry cold-daemon failures
**Section:** Decisions > "WikiStartupError retry lives in `_marker.slug_from_branch()`"
**Issue:** `millpy-bg.py:159-169` already catches `_marker.MarkerError` separately from `WikiError` and prints a hardcoded "cwd appears to be a non-task worktree... Switch to the task-worktree terminal" message; `mill-start/SKILL.md` (lines 145, 169) tells the operator to act on that exact text. After the chokepoint fix, an exhausted-retry cold-daemon failure surfaces as `MarkerError` too (verified: `slug_from_branch` wraps the unrecovered `WikiStartupError` as `MarkerError`), so it lands in this same handler and tells the operator to switch worktrees instead of indicating a wiki/daemon problem -- in exactly the scenario (cold daemon after sleep) this task targets, whenever the retry budget still isn't enough.
**Fix:** Either make the millpy-bg.py handler/SKILL.md text distinguish a wiki-startup-origin `MarkerError` from a real branch/slug mismatch (e.g. a distinct message prefix or exception subtype), or explicitly scope/acknowledge this residual gap and add a test asserting the message content for this call site.

### [NOTE] "separate import" claim for `wiki.WikiStartupError` is incorrect
**Section:** Technical context -- Gap 2 files
**Issue:** Claims `wiki.WikiStartupError` "needs a separate import" in `_marker.py`; verified `wiki/_client.py:13-42` already imports `WikiStartupError` into its own module namespace, and since `_marker.py` does `from wiki import _client as wiki`, `wiki.WikiStartupError` already resolves via that re-export without any new import.
**Fix:** Correct the technical-context note so the plan doesn't add an unnecessary import (harmless either way, but the rationale as written is factually wrong).

### [NOTE] Gap 1 testing language is hedgy where coverage is already confirmed
**Section:** Testing -- Gap 1
**Issue:** "verify it does, and add a case if needed" is left open-ended; directly checked `test-review-discussion-flow.py:164-232` and confirmed it already exercises `prepare(..., max_rounds=...)` end-to-end at the script level.
**Fix:** State definitively that no new unit test is required for Gap 1 (manual/integration verification only), removing the conditional language.

## Verdict
GAPS_FOUND
One GAP: cold-daemon retry exhaustion is misreported by millpy-bg.py's existing MarkerError handler.
MILL_REVIEW_END
