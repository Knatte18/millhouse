# Batch: stacked-finalize-cleanup

```yaml
task: "Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize"
batch: "stacked-finalize-cleanup"
number: 5
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-finalize-cleanup.py
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
  -relative>/status.md` (or `git ls-tree <base_branch> -- <task_dir-relative>`),
  computing the worktree-relative form of `task_dir`. Return False on a
  non-zero/empty result. Use `_subprocess_util.run`; any runtime output must be
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
  diff vs base becomes empty). If False, keep the current `git rm -r <task_dir>`
  path. Preserve the existing idempotency notes for re-runs (absent task_dir /
  nothing to commit). State the exact helper signature inline so the implementer
  needs no exploration.
- **Commit:** `fix(finalize): restore task_dir from base on stacked branches (#482)`

### Card 13: git-pr guard resolves task_dir via config

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/skills/git-pr/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `git-pr/SKILL.md` Step 1.5, change the task-branch guard
  so that when the worktree is inside a mill container it resolves the task
  state path via `_config.load_config` + `_paths.resolve_task_path(worktree,
  cfg['paths']['status_md'])` (catching nested-hub `_mill/` locations) and falls
  back to the literal `$GIT_ROOT/_mill/status.md` check only when config
  resolution is unavailable (git-pr can run standalone outside mill). Keep the
  existing halt/redirect message unchanged.
- **Commit:** `fix(git-pr): resolve task_dir for the task-branch guard (#482)`

### Card 14: base_tracks_task_dir tests

- **Context:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
  - `plugins/mill/unit_tests/test-wiki-sync.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-finalize-cleanup.py`
- **Deletes:** none
- **Requirements:** Create `test-finalize-cleanup.py` testing
  `base_tracks_task_dir` with a real tempfile git repo (use the bare-repo/clone
  setup style from `test-wiki-sync.py` as a reference): (1) a base branch that
  tracks `<task_dir>/status.md` -> returns True; (2) a base branch with no
  tracked `_mill/` -> returns False. Use the repo's pass/fail harness style with
  `if __name__ == "__main__": sys.exit(main())` so `run-all.py --only
  test-finalize-cleanup.py` picks it up.
- **Commit:** `test(finalize): cover base_tracks_task_dir detection (#482)`

## Batch Tests

`verify:` runs `test-finalize-cleanup.py` only (new file covering the
`base_tracks_task_dir` helper). The two SKILL.md edits are prose wiring with no
separate runnable surface; their correctness is reviewed and backed by the
helper's tests.
