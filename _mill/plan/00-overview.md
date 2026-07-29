# Plan: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout

```yaml
task: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout
slug: mill-merge-topology-and-squash-restore-gaps
approved: false
started: 20260729-065338
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: is-inplace-topology-fix
    file: 01-is-inplace-topology-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-inplace.py test-paths.py test-review-common.py test-cleanup.py
  - number: 2
    name: step5-checkout-guard
    file: 02-step5-checkout-guard.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
```

## Shared Decisions

### Decision: is-inplace-topology-check

- **Decision:** Replace `_inplace.is_inplace`'s body with a git-topology comparison: in-place iff `git_root` is the same directory as `_paths.resolve_main_worktree_root(git_root)`. Use `git_root.samefile(main_root)`, falling back to `git_root.resolve() == main_root.resolve()` on `OSError` — the same fallback pattern already used in `_paths.resolve_git_root` (`_paths.py:145-150`). `slug` and `cfg` stay in the function signature — for API compatibility with all three existing call sites (`_paths.py:433`, `millpy-cleanup.py:434`, `mill-merge/SKILL.md:21`) and the structural signature test in `test-inplace.py` — but no longer participate in the check; the docstring must say so explicitly.
- **Rationale:** `_paths.resolve_main_worktree_root(git_root)` already exists and does exactly the git-verifiable check issue #735 asks for. No circular-import risk: `_paths.py` only imports `_inplace` lazily inside a function body (`_paths.py:418`), so `_inplace.py` importing `resolve_main_worktree_root` from `_paths` at module level is safe. All three existing call sites only ever invoke `is_inplace` after already confirming the checkout's current branch matches the slug in question — combined with git's own invariant that a branch cannot be checked out in two worktrees simultaneously, "is `git_root` the main worktree" is unambiguous and equivalent to "is this task's branch checked out in-place" for all three.
- **Applies to:** batch is-inplace-topology-fix

### Decision: step5-checkout-guard

- **Decision:** Change `mill-merge/SKILL.md`'s Step 5 restore sequence's `git -C <parent-path> checkout -- "$TASK_DIR_REL"` line to `git -C <parent-path> checkout -- "$TASK_DIR_REL" 2>/dev/null || true`, and correct the adjoining `Why:` prose (currently asserts a false "clean no-op" claim) to describe the guard explicitly.
- **Rationale:** matches issue #736's primary suggested fix, and the existing swallow-idiom already used in `mill-merge-in/SKILL.md:37` (`OLD_CHK_SHA=$(git rev-parse --verify --quiet "$CHK" || true)`). Verified live in this repo: `git reset -q HEAD -- <pathspec>` against a pathspec absent from `HEAD`'s tree is a no-op (exit 0), but bare `git checkout -- <pathspec>` in the same situation exits 1 with `error: pathspec '...' did not match any file(s) known to git`; `2>/dev/null || true` swallows exactly that narrow failure.
- **Applies to:** batch step5-checkout-guard

## All Files Touched

- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/scripts/_inplace.py`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-inplace.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-review-common.py`
