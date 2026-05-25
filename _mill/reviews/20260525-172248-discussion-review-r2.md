# Review: Green the unit test suite on wiki-v3-adoption so it can merge to main

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-25
```

## Findings

### [GAP] upsert_task fails on non-git wiki_path in RC1-seed and RC2
**Section:** RC1-seed Decision; RC2 Decision
**Issue:** Both RC1-seed and RC2 prescribe `wiki.upsert_task(wiki_path, slug, ...)` for fixture seeding, but the wiki_path produced by `_make_task_worktree` (test-marker.py and the shared `_test_helpers._make_task_worktree`) and by `_make_container_form_worktree` (test-bg-launcher.py) is a plain directory — no `git init`, no remote. `upsert_task` triggers `_render_and_commit_all` → `commit_push` → `git add` on a non-git dir, which fails with `WikiPushError` (verified: `_render_and_commit_all` re-raises, `_client.upsert_task` re-raises, fixture fails before any assertion runs). The TinyDB write *does* precede the push attempt, so the task lands in `tasks.json` even when git fails — but the client raises unconditionally on `ERR_PUSH_FAILED`. The discussion does not say whether the fixture should swallow `WikiPushError` (relying on the already-committed TinyDB row), add `git init` + `git config` to the wiki setup, or use a different seeding path.
**Fix:** State explicitly: either (a) wrap the `upsert_task` call in `try/except WikiPushError: pass` (TinyDB write is atomic and precedes the git step, so the task is present for subsequent `list_tasks_brief`), or (b) extend the fixture setup to `git init` the wiki directory and add a minimal git identity — whichever approach the author intends. Without this, a planner following the text literally produces fixtures that abort on setup.

### [NOTE] RC3 Technical Context says "both" shutil.rmtree calls; only one exists
**Section:** Technical Context → Test files modified → test-fold.py entry
**Issue:** The Technical Context says "replace both `shutil.rmtree(td.name, ignore_errors=True)` calls" but the RC3 Decision section correctly states "one `shutil.rmtree` call exists in the file." Grep of `test-fold.py` confirms one call at line 97; line 95 is a comment (`# Daemon may still hold file locks...`).
**Fix:** Change "both" → "the" in the Technical Context entry to match the Decision section and the actual file.

## Verdict

GAPS_FOUND
RC1-seed and RC2 prescribe `upsert_task` on fixtures whose wiki path is not a git repo; the resulting `WikiPushError` will abort fixtures before any assertion runs, and the discussion does not say how to handle it.