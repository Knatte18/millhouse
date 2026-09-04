MILL_REVIEW_BEGIN
# Review: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] mill-merge's own cleanup commit (Step 4) never got #930's citation scan
**Location:** `plugins/mill/skills/mill-merge/SKILL.md:279-292` (`### 4. Cleanup commit`)
**Issue:** Batch 2 (Card 5) adds the non-blocking `_mill/discussion.md` citation scan only to `mill-finalize/SKILL.md`'s `### Step 3: Cleanup commit`, which lives under `## PR Steps` and only runs when `require_pr_to_base: true`. In Direct mode — `require_pr_to_base` default `false`, i.e. the common case — `mill-finalize`'s Dispatch immediately invokes `/mill-merge` and never reaches its own Step 3; the actual, first-time `git -C <worktree> rm -r <task_dir>` deletion happens in `mill-merge`'s own Step 4, and identically in the `merged` PR-state route (`## Entry`, which also runs Step 4). Neither of these call sites received the scan, so the exact bug class #930 describes (a surviving citation of `_mill/discussion.md` silently going dead) is unprotected on the more common path. `mill-merge/SKILL.md` contains no reference to the scan or to #930 at all.
**Fix:** Add the same two-part (`git -C <worktree> grep` / `git -C <wiki_path> grep`) non-blocking scan immediately before `mill-merge/SKILL.md`'s Step 4 `git rm -r <task_dir>`, worded for its single (no-restore) branch, or explicitly document in both files why Step 4's deletion is considered out of scope for #930.

### [NIT:consistency] Stale "mill-merge's auto-merge path" caveat now describes unreachable code
**Location:** `plugins/mill/skills/mill-merge-in/SKILL.md:23`
**Issue:** Entry step 3's "if not supplied" branch still says "If `mill-merge-in` is being called from `mill-merge`'s auto-merge path, pass `interactive=False`...". After Card 1, `mill-merge`'s Step 2 unconditionally passes `<parent_branch>` explicitly on both routes that reach it, so `mill-merge` can never invoke `mill-merge-in` bare anymore — this caveat now documents a caller scenario that cannot occur post-fix (the file's actual bare-invocation caller is `mill-finalize`'s PR Step 1, never described as "mill-merge's auto-merge path").
**Fix:** Reword or remove the caveat to reflect the new caller contract (e.g. attribute the `interactive=False` guidance to whichever non-interactive caller genuinely still invokes bare, if any), so a future reader does not assume `mill-merge` can still skip the argument.

## Verdict

REQUEST_CHANGES
Batch 2's #930 fix leaves mill-merge's own (more common) cleanup path with the exact same unprotected bug.
MILL_REVIEW_END
