MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort self-assessment)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] #980 fix misses a third forward-referenced variable
**Section:** Scope, #980 (and Technical context) **Issue:** `SKILL.md`'s Entry step 1 (line 51) calls `_marker.slug_from_branch(git_root, wiki_path, cfg)`, but `git_root` is a bare identifier never assigned anywhere before step 4.5 (line 77: `git_root = _paths.resolve_git_root()`) — verified by reading lines 51-86; the only other reference to `git_root` before line 51 in the file is nonexistent. The scoped fix ("reorder steps 1-3 so wiki_path and cfg resolve before step 1's call") only removes two of the three forward references in that same call; even after reordering, `git_root` is still undefined when the (now-reordered) `slug_from_branch` call executes, since its resolution stays in step 4.5, after steps 1-3. **Fix:** widen #980's scope to also add a `git_root = _paths.resolve_git_root()` assignment ahead of the `slug_from_branch` call (or otherwise resolve it inline, as line 53 already does for wiki_path), not just reorder wiki_path/cfg.

### [NIT:consistency] Constraints section quotes a rule that isn't verbatim anywhere
**Section:** Constraints **Issue:** `` `Never use fork for role dispatch` `` is presented in backticks as an "already documented" existing constraint, but no file in the repo (checked `SKILL.md`'s "Why not fork?" section, `CLAUDE.md`, `mill-plan/SKILL.md`'s fork guardrail) contains that literal string — it's a paraphrase of the existing "Why not fork?" prose, not a quoted rule. **Fix:** drop the backticks or cite the actual paraphrased source instead of implying a verbatim existing rule.

## Verdict

REQUEST_CHANGES
#980's line-51-86 forward-reference fix is incomplete: it fixes two of three undefined variables, leaving git_root unresolved.
MILL_REVIEW_END
