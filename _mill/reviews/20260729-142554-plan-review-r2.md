MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (claude-sonnet-4-5), self-assessed
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] `_worktree.move()` runs with cwd inside the dir being moved
**Location:** Batch 2, Card 7 (`_worktree.move`) + Card 10 Step 4 (`mill-resume/SKILL.md`)
**Issue:** `move()`'s `_subprocess_util.run([...])` call passes no `cwd=` kwarg, so per `_subprocess_util.run`'s own docstring ("`cwd`: ... None inherits the caller's cwd") the spawned git process's OS-level working directory is whatever the invoking shell's cwd is. Phase 1b's entire premise is that the shell's cwd IS `old_worktree` (the off-canonical worktree being relocated) when Step 4's `"$MILL_PYTHON" -c "..."` snippet runs `relocate_and_scaffold` -> `_worktree.move(old, canonical, cwd=hub_root)`. Renaming a directory that is a live process's cwd is a well-known NTFS lock failure (`_worktree.py`'s own `remove_safe`/`WorktreeLockedError` exists precisely for this class of failure on `remove()`), and Windows is CLAUDE.md's stated primary dev platform.
**Fix:** Pass an explicit `cwd=hub_root` (not just `-C hub_root`) to `_subprocess_util.run` inside `move()`, or have Phase 1b's Step 4 script `os.chdir()` to `hub_root`/`canonical` before invoking `relocate_and_scaffold`, and add lock-pattern detection (mirroring `remove_safe`'s `WorktreeLockedError`) so the failure is diagnosable when it does occur.

### [BLOCKING] New `verify_git_repo()` hard-fails health_check() for non-git test fixtures
**Location:** Batch 1, Card 2 (`_handle_health`)
**Issue:** `_handle_health()` now calls `verify_git_repo(self._wiki_path)` unconditionally, with no `WIKI_DAEMON_SKIP_GIT` exemption. `_test_helpers.py`'s `init_wiki_repo()` under the suite's own default (`WIKI_DAEMON_SKIP_GIT=1`) does not `git init` at all — it just `mkdir`s a plain directory ("the wiki server never invokes git ... Just create the directory and return"). `verify_git_repo` would raise on such a fixture, flipping `health_check()`/`OP_HEALTH` from always-True to always-False. This also fires inside `_ensure_daemon()`'s own internal `OP_HEALTH` reuse-probe (`_client.py:643-649`), used on every dispatched op once a daemon already exists. Batch 1's own verify gate depends on the pre-existing `test-wiki-daemon.py`/`test-wiki-client-retry.py` still passing as a "regression guard against OP_HEALTH dispatch/protocol behavior" — this is very likely to break for any fixture without a real git repo.
**Fix:** Gate the new `verify_git_repo`/debounced-`pull` logic behind `os.environ.get("WIKI_DAEMON_SKIP_GIT") == "1"` (short-circuit to the old `{FIELD_OK: True}`), matching the pattern `_render_and_commit_all` already uses for its own git calls.

### [BLOCKING] Requirements cite files absent from Context (Card 14, and pattern in 12/13/15/16)
**Location:** Batch 3, Card 14 (`millpy-validate-plan.py`)
**Issue:** Card 14's Requirements cite `find_active_slug(...)`'s parameter name "in `_review_common.py:306`" and `_plan_validate.run`'s docstring "at `_plan_validate.py:1455`" — specific line-level claims that could only come from reading those files — yet neither `_review_common.py` nor `_plan_validate.py` is listed in Card 14's `Context:` (only `_paths.py`) or `Edits:`. Same lighter-weight pattern recurs in Cards 12/13/15/16, which quote `_review_common.load_config`'s full signature without `_review_common.py` in Context (mitigated there by the signature being spelled out inline, unlike Card 14's line-number-only citations).
**Fix:** Add `_review_common.py` and `_plan_validate.py` to Card 14's `Context:` list.

### [BLOCKING] Overview's batch-1 verify command includes a file `run-all.py` always skips
**Location:** `00-overview.md`'s `batches:` block (batch 1 `verify:`) vs. `01-wiki-health-check-and-messaging.md`'s own frontmatter `verify:`
**Issue:** The overview (the document explicitly called "the authoritative DAG mill-go reads to schedule batches") lists batch 1's verify as `--only test-wiki-sync.py test-wiki-health-check.py test-wiki-daemon.py test-wiki-client-retry.py`, but the batch file's own frontmatter `verify:` omits `test-wiki-sync.py`. Card 1 itself states `run-all.py` hardcodes `SKIP = frozenset({"test-wiki-sync.py"})`, so it "is never runnable via `run-all.py --only`" — meaning the overview's authoritative command silently no-ops on that file, contradicting its own inclusion.
**Fix:** Drop `test-wiki-sync.py` from the overview's batch-1 `verify:` entry to match the batch file's own frontmatter, or reconcile the two by removing the mismatch entirely.

### [NIT] `_paths.py` docstring/`__all__` not updated for the new function
**Location:** Batch 2, Card 6 (`resolve_canonical_worktree_path`)
**Issue:** Card 6 doesn't require adding the new function to `_paths.py`'s module-docstring "Public API" list or its `__all__` export list, unlike Card 7's explicit parallel requirement for `_worktree.py`'s Public API list — inconsistent with the file's own established convention.
**Fix:** Add a matching Public API docstring entry (and `__all__` entry) for `resolve_canonical_worktree_path`.

### [NIT] "existing clone fixture helper" doesn't exist as a separate function
**Location:** Batch 1, Cards 1 and 4
**Issue:** Both cards ask to "reuse the file's existing clone fixture helper" in `test-wiki-sync.py`, but that file has no such helper — the bare-repo+clone setup is inlined directly in `main()`, not factored into a reusable function.
**Fix:** Reword to "adapt the inline bare-repo+clone setup pattern in `main()`" to avoid implying a callable helper exists.

### [NIT] Debounce spy patch target is ambiguous and only one option actually works
**Location:** Batch 1, Card 4 (test (c), debounce)
**Issue:** Card 4 says to patch "`wiki._server.pull` or `wiki._sync.pull`, whichever the in-process harness resolves against." Since `_server.py` does `from wiki._sync import pull` (binds a local name), only patching `wiki._server.pull` actually intercepts the call inside `_handle_health`/`_render_and_commit_all`; patching `wiki._sync.pull` has no effect on that already-bound reference.
**Fix:** State `wiki._server.pull` as the correct patch target.

## Verdict

REQUEST_CHANGES
Windows worktree-move-cwd lock risk, unconditional git-validity check breaking non-git test fixtures, and Context-completeness gaps need fixing.
MILL_REVIEW_END
