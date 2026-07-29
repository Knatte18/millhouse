MILL_REVIEW_BEGIN
# Review: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Sibling unguarded walk in `_junction.strip_all_in_worktree` not addressed
**Section:** Decisions > Fix location; Scope > Out
**Issue:** `_worktree.remove_safe` (lines 180-276) runs `_junction.strip_all_in_worktree` unconditionally as step 1, *before* attempting `git worktree remove` — its inner `_walk` (`_junction.py` lines 314-336) does the identical list-then-recurse `os.scandir` pattern as `_walk_strip_reparse_points` but only catches `PermissionError`, not `FileNotFoundError`; a vanished entry there raises the same uncaught WinError out of `remove_safe`, bypassing the git fast-path entirely and reproducing this exact bug through a code path the discussion never analyzes. Its own docstring confirms it walks arbitrarily deep, including hub-relative subdirs like `src/csharp/NORCE.Models/.wiki` — the same subtree where issue #738's vanishing file lived — and it runs on every `remove_safe` call (all four listed callers), not just the long-path fallback.
**Fix:** Either extend scope to add the same `FileNotFoundError`-skip-and-log guard to `_junction.strip_all_in_worktree`'s `_walk`, or add an explicit Decision/rejected-alternative explaining why it's excluded (e.g. if the real crash traceback can be confirmed to originate specifically in the fallback path and not step 1).

### [NOTE] "mill-merge" listed as a `safe_rmtree` beneficiary without source support
**Section:** Decisions > Fix location (rationale)
**Issue:** The rationale lists `mill-merge` alongside mill-cleanup/mill-spawn as a caller that "goes through" `_worktree.remove_safe`/`_safe_rmtree` and benefits from the fix "without any changes of their own"; grep of `millpy-merge-in-subagent.py` and `plugins/mill/skills/mill-merge/SKILL.md` shows no reference to `remove_safe`, `safe_rmtree`, or worktree teardown at all.
**Fix:** Verify which script actually performs mill-merge's worktree cleanup (if any) and correct or drop the mill-merge attribution.

## Verdict

GAPS_FOUND
Chosen fix location leaves a structurally identical, unguarded TOCTOU race live in `_junction.strip_all_in_worktree`.
MILL_REVIEW_END
