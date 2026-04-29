# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 03-state-on-worktree

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 03-state-on-worktree
date: 2026-04-29
```

## Findings

### [BLOCKING] `resolve_path` test fixture cannot work without git worktree setup
**Step:** Card 12 (and propagates to Card 13 flow tests)
**Issue:** The new `resolve_path` body calls `_paths.resolve_main_worktree_root(Path.cwd())`, which shells out to `git rev-parse --git-common-dir`. The plan's test description says "tempfile fixture that creates `<container>/wts/<slug>/.millhouse/active.slug.md`" — a bare tempdir is not a git repo, so `resolve_main_worktree_root(Path.cwd())` resolves to the source repo's main worktree, not the fixture. Every new `resolve_path` test and every Card 13 flow test would fail immediately. Card 13 explicitly says "use the same tempfile fixture shape as Card 12," so the same gap propagates. Tests as specified cannot pass.
**Fix:** Either (a) add an optional `_cwd: Path | None = None` parameter to `resolve_path` — when provided it replaces `Path.cwd()`, so tests pass the fixture worktree root directly without touching the filesystem's git state; or (b) update the test description to require git worktree initialisation + `os.chdir()` into the fixture, following the pattern already used in `_make_git_repo` in `test-spawn-core.py`.

### [NIT] Smoke-check in batch scope implies false end-to-end correctness
**Step:** Batch Scope, Card 13/14 note
**Issue:** The scope states "manual smoke-check after Card 14 (re-run a discussion review on a fresh slug) confirms end-to-end." After batch 03, `resolve_path` looks for `discussion.md` in the worktree, but mill-start still writes `discussion.md` to the wiki (mill-start is not updated until batch 04). The smoke-check would fail with a file-not-found error on `<worktree>/discussion.md`.
**Fix:** Replace "re-run a discussion review on a fresh slug" with "manually place a `discussion.md` at the worktree root and run review against it — full end-to-end smoke depends on batch 04 (mill-start update)."

### [NIT] Backward-compat description overstates protection
**Step:** Card 12
**Issue:** The plan says `<SLUG>` stripping "protects against half-deployed configs during a re-clone." With old templates like `active/<SLUG>/discussion.md`, substituting the slug gives `active/my-slug/discussion.md`, which joined with `active_worktree` yields `<worktree>/active/my-slug/discussion.md` — a path that doesn't exist. The function still fails; it just doesn't crash on the `<SLUG>` token.
**Fix:** Reword: "the strip prevents a KeyError on the `<SLUG>` token in old templates; paths still fail at file-open time until Card 14 is deployed."

### [NIT] Dry-run status path not explicitly called out
**Step:** Card 11
**Issue:** `millpy-spawn.py`'s `--dry-run` branch prints `wiki_path / 'active' / slug / 'status.md'`. The plan says "adjust the status-path log line" but the dry-run branch is a separate code path that also prints the now-wrong wiki-based path.
**Fix:** Add "update the `--dry-run` status print to `worktree_path / 'status.md'`" to Card 11 requirements.

### [NIT] Git subprocess error handling omitted from new commit step
**Step:** Card 11
**Issue:** The plan specifies `git -C <worktree_path> add status.md` and `git -C <worktree_path> commit -m "spawn: init status for {slug}"` but says nothing about handling non-zero exit codes. The existing `capture_parent_branch` raises `RuntimeError` on non-zero; the same discipline is absent from the new commit steps.
**Fix:** Add "check returncode of both `git add` and `git commit`; raise `RuntimeError` with captured stderr on non-zero exit."

## Verdict

REQUEST_CHANGES — the blocking gap in test fixture design means the Card 12/13 tests cannot pass as specified; an `_cwd` escape-hatch parameter or explicit git-fixture description is required.