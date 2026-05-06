# Review: 12 (C) — Restructure hub junction layout — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-05-06
```

## Findings

### [BLOCKING] Hardlink gitignore management silently dropped
**Location:** Batch 4, Card 14 (mill-setup SKILL.md Phase 4.5b)
**Issue:** The old Phase 4.5b wrote `ANCHORED_ENTRIES + hardlink_names` to the hub gitignore, which added `/tasks.md` (and any future hardlinks from `wiki/config.yaml`) as root-anchored gitignore entries. The new snippet calls `_gitignore.upsert(hub_gi, _gitignore.GLOB_ENTRIES)` only. No entry covers `tasks.md`; it will appear as an untracked file after the next mill-setup run. The plan's note "covered by git's normal ignore rules" is asserted without identifying what rule would cover it.
**Fix:** Either add hardlink names back as additional entries passed to `upsert`, or add `**/<hardlink-name>` patterns to the new `GLOB_ENTRIES`.

### [BLOCKING] Dangling `.active` cleanup condition wrong on Windows
**Location:** Batch 3, Card 10 (millpy-cleanup.py req 3)
**Issue:** The guard `(active_link.exists() or active_link.is_symlink()) and not active_link.is_dir()` evaluates to `False` for a broken NTFS junction on Windows. When the portal entry is removed, the target of `.active` is gone; Python's `Path.exists()` follows the junction and returns `False`, and `Path.is_symlink()` returns `False` for junctions (they are not symlinks). The condition short-circuits to `False`; the dangling junction is never removed. Card 12 req 3's test patches `Path.exists` to `True`, giving false confidence in a code path that never fires in production.
**Fix:** Replace `active_link.exists() or active_link.is_symlink()` with `os.path.lexists(str(active_link))`, which returns `True` for broken junctions without following the reparse point.

### [BLOCKING] `test_main_dry_run_prints_worktree_status_path` not updated after Card 5 path change
**Location:** Batch 2, Card 9 (test-millpy-spawn.py)
**Issue:** Card 5 req 5 changes the dry-run status print from `worktree_path / 'status.md'` to `worktree_path / 'task' / 'status.md'`. Card 9 updates only the smoke-import stub (`write_wiki_active_task_md`). The test `test_main_dry_run_prints_worktree_status_path` still asserts `expected_path = str(Path("/fake/worktrees") / "my-task" / "status.md")`, which won't match the new output. The batch verify (`run-all.py`) will fail on this test.
**Fix:** Card 9 must also update `test_main_dry_run_prints_worktree_status_path` to assert `Path("/fake/worktrees") / "my-task" / "task" / "status.md"`.

### [NIT] Card 13 req 1 references a string absent from the current CLAUDE.md diagram
**Location:** Batch 4, Card 13 (CLAUDE.md req 1)
**Issue:** The requirement says "remove the `.others -> ../wts/millhouse` entry" from the container layout diagram. That exact string does not appear there; the portals section shows `portals/<slug> -> ../wts/<slug>`. The portals section also needs updating to show the new target (`wiki/active/<slug>/`), but this is not mentioned. The implementer may be confused about what to remove and may miss the portals-section update.
**Fix:** Clarify the requirement to reference the correct existing text and add an explicit instruction to update the portals-section target paths.

### [NIT] Card 11 req 4e `git mv` + `git commit` lacks a commit message
**Location:** Batch 3, Card 11 (millpy-migrate-layout.py req 4e)
**Issue:** The requirement says "git mv src → dst, then git commit" for moving working state to `task/`. No commit message is specified, leaving the implementer to invent one that will become permanent git history on every migrated worktree.
**Fix:** Add a prescribed commit message, e.g. `"migrate: move working state to task/ for {slug}"`.

## Verdict

REQUEST_CHANGES
Three blocking defects: missing gitignore coverage for hardlinks, wrong Windows junction predicate in cleanup, and an untouched test that will fail the batch verify.
