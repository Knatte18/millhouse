MILL_REVIEW_BEGIN
# Review: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Fix 1: Requirements:/Commit: legend fate left ambiguous
**Section:** Decisions — Fix 1
**Issue:** The decision names only the Context/Edits/Creates/Deletes/Moves bullets as moving into the HTML comment, but cites line range 61-72; in the actual `plan-batch.md`, lines 67-68 are the Requirements:/Commit: legend bullets, not named in the enumerated list. Whether these two bullets also move (verified: `_RE_REFS_HEADER` doesn't match them, so leaving them visible wouldn't reproduce the false-positive bug either way) is undecided, yet the Testing section requires an exact "corrected (legend-in-comment) template shape" for its regression fixture.
**Fix:** State explicitly whether Requirements:/Commit: legend bullets move into the comment too, or give the precise line span if they stay visible.

### [GAP] Fix 2: new fix-table wording drops halt fallback
**Section:** Decisions — Fix 2
**Issue:** Decision frames the change as replacing the row's "second sentence," but the current `non-existent-path` row (verified at SKILL.md:130) has three sentences, and the given "New wording" replaces all of them while dropping the third ("If neither applies... halt; this is not mechanically fixable"). This leaves the mechanically-applied fix table with no defined action when a finding is neither a typo nor an intended new Creates: target.
**Fix:** Retain an explicit halt instruction in the new row text for the case where neither correction applies.

### [GAP] Fix 3: //go:build detection misses files with leading comments
**Section:** Decisions — Fix 3, step 3
**Issue:** Detection checks only the file's first non-blank line for `^//go:build`. Per Go's build-constraint spec, a `//go:build` line may legally be preceded by other line comments (e.g. a copyright/license header) — a common real-world pattern — so a tagged file with a header comment is silently missed, a false negative in the exact check meant to catch a missing `-tags integration`. None of Testing scenarios (a)-(f) cover a header-comment-preceded file.
**Fix:** Scan the leading comment block (lines before the package clause), not just line 1, for the `^//go:build` line; add a Testing scenario for a tagged file preceded by a header comment.

### [NOTE] resolve_ref_paths call-site count is wrong in two places
**Section:** Technical context / Scope — Out
**Issue:** Both sections state `resolve_ref_paths` is called from "three places"/"three...call sites," then "all four calls"/"three untouched call sites" — internally inconsistent. Grep confirms 5 real call sites: `_review_code.py:283` (1) plus `_review_plan.py:172,383,479,833` (4).
**Fix:** Correct to "five call sites across two files... four untouched in `_review_plan.py`" — the enumerated line numbers themselves are already correct, so this doesn't change what a plan writer would implement.

## Verdict

GAPS_FOUND
Three GAPs (Fix 1 legend scope, Fix 2 dropped halt clause, Fix 3 detection false-negative) need resolution before plan writing.
MILL_REVIEW_END
