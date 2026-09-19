MILL_REVIEW_BEGIN
# Review: _config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-19
```

## Findings

### [BLOCKING:consistency] Card 1 "with:" replacement snippet is mis-indented by 2 spaces
**Location:** Batch 1 / Card 1, Requirements, the `Replace: ... with: ...` code fences.
**Issue:** The unchanged line `unknown = walk_unknown_keys(actual, template)` sits at 4-space indent in the "Replace:" quote (matches `_config.py`'s real `warn_unknown_keys` body, verified against the source file), but the identical line in the "with:" quote sits at 6-space indent, and every subsequent line in "with:" (`for`/`if`/`hint`/`else`/`print`) is likewise 2 spaces deeper than the function's real indentation. Pasting "with:" verbatim over "Replace:" produces an `IndentationError`.
**Fix:** Re-indent the "with:" block by 2 spaces so `unknown =`/`for` sit at 4, `if`/`hint =`/`if hint`/`else` sit at 8, and `continue`/`print` sit at 12 — matching the surrounding function body.

### [BLOCKING:consistency] Card 2 isinstance-guard snippet is mis-indented by 2 spaces
**Location:** Batch 1 / Card 2, Requirements, the two-line `isinstance` guard code fence.
**Issue:** `check_and_restore`'s real body statements sit at 4-space indent (verified against `_treeguard.py`: `lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)` is at column 4), but the plan's `if not isinstance(...)` lines are shown at 6-space indent with `raise TypeError(...)` at 10-space — 2 spaces deeper than the function they are inserted into as its first statements. Pasted as written, this raises an `IndentationError` immediately before the existing `lines = ...` line.
**Fix:** Re-indent to 4 spaces for both `if` lines and 8 spaces for both `raise TypeError` lines.

## Verdict

REQUEST_CHANGES
Both cards' literal replacement code fences are indented 2 spaces too deep and would break Python syntax if copied verbatim.
MILL_REVIEW_END
