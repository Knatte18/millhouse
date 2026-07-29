MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] Batch 1's verify: command can never pass
**Location:** 00-overview.md batch 1 entry / 01-wiki-health-check-and-messaging.md `verify:`
**Issue:** `plugins/mill/unit_tests/run-all.py` hardcodes `SKIP = frozenset({"test-wiki-sync.py"})` and filters it out of `discovered` *before* `--only` is resolved (`by_name = {p.name: p for p in discovered}`); `--only test-wiki-sync.py ...` therefore always hits `unknown = [n for n in args.only if n not in by_name]` and exits 1 with "unknown test file(s)" — the test never even runs.
**Fix:** Drop `test-wiki-sync.py` from the `--only` list (Card 1's extension is exercised some other way, or run-all.py's SKIP/--only interaction is fixed as its own card).

### [BLOCKING] Phase 1b Step 1 snippet uses `_paths` without importing it
**Location:** 02-mill-resume-repair.md, Card 10, Phase 1b Step 1
**Issue:** The literal code block is `import sys` / `import _resume_repair` / `lines = _resume_repair.check_uncommitted_changes(_paths.resolve_git_root())` — `_paths` is never imported in this `-c` invocation (each Step is a fresh subprocess). This raises `NameError: name '_paths' is not defined` every time Phase 1b Step 1 runs.
**Fix:** Add `import _paths` to Step 1's snippet.

### [BLOCKING] Card 9's test file needs `_pygit2_util.py`, not in Context
**Location:** 02-mill-resume-repair.md, Card 9
**Issue:** Requirements say assertions must distinguish tracked-modified vs. untracked-added porcelain lines "against `_pygit2_util.status_porcelain`'s real output," but Card 9's `Context:` is only `_resume_repair.py`, `_worktree.py`, `_junction.py`, `test-worktree.py` — `_pygit2_util.py` (which documents the `"XY path"` format needed to write these distinct assertions) is absent.
**Fix:** Add `plugins/mill/scripts/_pygit2_util.py` to Card 9's `Context:`.

### [BLOCKING] `_handle_health`'s pull skips the store close/reopen dance
**Location:** 01-wiki-health-check-and-messaging.md, Card 2
**Issue:** `_render_and_commit_all` explicitly closes `self._store` before calling `pull()` and reopens after, with a comment explaining TinyDB's open `tasks.json` handle blocks git's working-tree checkout on Windows. Card 2's new debounced `pull(self._wiki_path)` call inside `_handle_health` does not close/reopen `self._store` around it, so a health-check-triggered pull that actually updates `tasks.json` can hit the same documented Windows failure mode.
**Fix:** Wrap the health-check's `pull()` call in the same `self._store.close()` / `finally: self._store.reload()` pattern.

### [BLOCKING] `hub_root` can resolve to the broken worktree itself
**Location:** 02-mill-resume-repair.md, Card 10 Phase 1b Step 4 / Card 8
**Issue:** Phase 1 branches into Phase 1b when *either* `.millhouse/config.local.yaml` *or* `.wiki` is missing. If only `.wiki` is missing, `.millhouse/config.local.yaml` exists at cwd, so `_paths.resolve_hub_path()` (called with no cwd arg, i.e. `Path.cwd()` = the broken worktree) returns the broken worktree itself as `hub_root` via its cwd-walk fast path — not the true main-worktree hub. `relocate_and_scaffold` then calls `_worktree.move(old, canonical, cwd=hub_root)` with `cwd == old`, exactly the situation Card 7/8 explicitly warn against.
**Fix:** Resolve `hub_root` via `_paths.resolve_main_worktree_root(git_root)` (or an equivalent that doesn't consult cwd's own `.millhouse/`) rather than `resolve_hub_path()` in Phase 1b.

## Verdict

REQUEST_CHANGES
Five BLOCKING issues: a verify command that cannot pass, a NameError-producing snippet, a missing Context file, a Windows lock regression, and a self-referential cwd bug.
MILL_REVIEW_END
