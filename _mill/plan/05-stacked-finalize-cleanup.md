# Batch: stacked-finalize-cleanup

```yaml
task: "Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize"
batch: "stacked-finalize-cleanup"
number: 5
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-finalize-cleanup.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #482: mill-finalize's PR cleanup runs `git rm -r <task_dir>`
unconditionally; on a stacked task-branch whose base tracks `_mill/`, this
deletes the base's own state and pollutes the PR diff with unrelated deletions.
Add a helper that detects whether the PR base tracks `task_dir`, make the
mill-finalize Step 3 cleanup conditional (restore vs. remove), and fix git-pr's
Step 1.5 guard to resolve `task_dir` via config (so it catches nested-hub
layouts) instead of a literal git-root-relative `_mill/status.md`.

Cards 12 (mill-finalize sets `MILL_FINALIZE_PR_CLEANUP=1`) and 13 (git-pr reads
it to skip its guard) are interdependent and ship together as one atomic batch —
the batch's `verify:` and code review run after all four cards are implemented,
so the env-flag setter and reader land as a unit with no broken intermediate
state in normal mill-go batch execution.

## Cards

### Card 11: base_tracks_task_dir helper

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
- **Deletes:** none
- **Requirements:** Create `_finalize_cleanup.py` exposing
  `base_tracks_task_dir(worktree: Path, base_branch: str, task_dir: Path) ->
  bool`. It returns True when `base_branch` tracks the task state directory —
  implement via `git -C <worktree> cat-file -e <base_branch>:<task_dir
  -relative>/status.md` (or `git ls-tree <base_branch> -- <task_dir-relative>`).
  Compute the worktree-relative form of `task_dir` and render it with
  `.as_posix()` before building the `<rev>:<path>` pathspec — git requires
  forward slashes, so a raw `str(task_dir.relative_to(worktree))` would emit
  backslashes on Windows and the check would always return False. Return False on
  a non-zero/empty result. Use `_subprocess_util.run`; any runtime output must be
  ASCII. Include a module-level docstring and a file-level comment per repo
  convention.
- **Commit:** `feat(finalize): add base_tracks_task_dir helper (#482)`

### Card 12: conditional PR cleanup in mill-finalize

- **Context:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-finalize/SKILL.md` PR Steps Step 3, replace the
  unconditional `git -C <worktree> rm -r <task_dir>` with a conditional: call
  `_finalize_cleanup.base_tracks_task_dir(<worktree>, <base_branch>, <task_dir>)`
  (`base_branch` is resolved in Dispatch). If it returns True, run `git -C
  <worktree> checkout <base_branch> -- <task_dir>` then commit (net `_mill/`
  diff vs base becomes empty); note that in this branch `task_dir` remains
  PRESENT in the worktree (restored to base's version), unlike the rm branch.
  If False, keep the current `git rm -r <task_dir>` path. Preserve the existing
  idempotency notes for re-runs (absent task_dir / nothing to commit). State the
  exact helper signature inline so the implementer needs no exploration. ALSO
  update Step 5: invoke `/git-pr <base_branch>` with the environment variable
  `MILL_FINALIZE_PR_CLEANUP=1` set, and replace the existing "it will not halt
  on its step 1.5 guard because `<task_dir>` is absent" note with: cleanup has
  already run (task_dir is either absent on the rm path or restored-to-base on
  the restore path), and `MILL_FINALIZE_PR_CLEANUP=1` tells git-pr's guard to
  skip its task-branch halt so PR creation proceeds in both cases.
- **Commit:** `fix(finalize): restore task_dir from base on stacked branches (#482)`

### Card 13: git-pr guard resolves task_dir via config

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/skills/git-pr/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `git-pr/SKILL.md` Step 1.5, make two changes. (1) When
  the environment variable `MILL_FINALIZE_PR_CLEANUP` is set (non-empty), skip
  the task-branch guard entirely and proceed — mill-finalize sets this after it
  has already handled `_mill/` cleanup (removed or restored-to-base), so the
  guard must not block PR creation on the stacked-branch restore case. (2)
  Otherwise (standalone invocation), resolve the task state path via
  `_config.load_config` + `_paths.resolve_task_path(worktree,
  cfg['paths']['status_md'])` (catching nested-hub `_mill/` locations) and fall
  back to the literal `$GIT_ROOT/_mill/status.md` check only when config
  resolution is unavailable (git-pr can run standalone outside mill). Keep the
  existing halt/redirect message unchanged. Document that the env-flag skip is
  the mill-finalize integration point. Since git-pr/SKILL.md is a bash skill,
  specify the config resolution as a guarded cache-form Python invocation that
  runs only when both `$MILL_PYTHON` and `$CLAUDE_PLUGIN_ROOT` are set — e.g.
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c '<resolve and
  print the status.md path via _config.load_config + _paths.resolve_task_path>'`
  — and if either env var is unset or the invocation errors (standalone
  git-pr outside mill), fall through to the literal `$GIT_ROOT/_mill/status.md`
  check.
- **Commit:** `fix(git-pr): resolve task_dir for the task-branch guard (#482)`

### Card 14: base_tracks_task_dir tests

- **Context:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
  - `plugins/mill/unit_tests/test-wiki-sync.py`
- **Edits:**
  - `plugins/mill/unit_tests/run-all.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-finalize-cleanup.py`
- **Deletes:** none
- **Requirements:** Create `test-finalize-cleanup.py` testing
  `base_tracks_task_dir` with a real tempfile git repo (use the bare-repo/clone
  setup style from `test-wiki-sync.py` as a reference): (1) a base branch that
  tracks `<task_dir>/status.md` -> returns True; (2) a base branch with no
  tracked `_mill/` -> returns False. Use the repo's pass/fail harness style with
  `if __name__ == "__main__": sys.exit(main())`. Because this test uses real git,
  add `"test-finalize-cleanup.py"` to the `SKIP` frozenset in `run-all.py`
  (matching the `test-wiki-sync.py` precedent) so the default parallel suite does
  not run it; the batch `verify:` invokes it directly instead.
- **Commit:** `test(finalize): cover base_tracks_task_dir detection (#482)`

## Batch Tests

`verify:` runs `test-finalize-cleanup.py` only (new file covering the
`base_tracks_task_dir` helper). The two SKILL.md edits are prose wiring with no
separate runnable surface; their correctness is reviewed and backed by the
helper's tests.
