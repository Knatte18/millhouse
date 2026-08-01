MILL_REVIEW_BEGIN
# Review: Add mill-quick: skip-review pipeline for simple tasks

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-01
```

## Findings

### [GAP] `set_blocked` call shape omits required keyword-only `timestamp=`
**Section:** Scope (bullet "On verify failure") and Decisions/failure-handling
**Issue:** Both spots write `_status.set_blocked(status_path, reason, timestamp)`; the actual signature (`plugins/mill/scripts/_status.py`) is `set_blocked(status_path: Path, reason: str, *, timestamp: str)` — `timestamp` is keyword-only, so a positional call raises `TypeError`. Every existing call site in the codebase (`mill-start/SKILL.md` L224, `mill-plan/SKILL.md` L332/334) uses `timestamp=ts`.
**Fix:** Rewrite both mentions as `_status.set_blocked(status_path, reason, timestamp=ts)`.

### [GAP] Slug/wiki_path derivation missing from the path-resolution bullet
**Section:** Technical context ("Path resolution mirrors mill-start's Entry/Path Setup exactly")
**Issue:** The bullet lists only `git_root`, `worktree_root`, `status_path` and claims to mirror mill-start's Entry/Path Setup "exactly," but `slug` is derived in mill-start via a separate Entry step (`_marker.slug_from_branch(git_root, wiki_path, cfg)`, step 3 — distinct from the Path Setup bullets), and `wiki_path` is likewise never introduced. Both are used pervasively elsewhere in this doc (`_client.get_task(wiki_path, slug)`, `millpy-builder-lock.py acquire <slug>`) with no stated derivation.
**Fix:** Add `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)` and `wiki_path = _paths.resolve_wiki_path(git_root)` to the Path resolution bullet.

## Verdict

GAPS_FOUND
Two verified technical-accuracy gaps in Technical context/Scope call shapes; rest of the doc holds up against source.
MILL_REVIEW_END
