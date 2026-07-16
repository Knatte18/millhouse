# Batch: cleanliness-nested-hub-revert

```yaml
task: "Miscellaneous small tooling and doc/template accuracy gaps"
batch: "cleanliness-nested-hub-revert"
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py
depends-on: []
```

## Batch Scope

Closes GitHub #640: `_cleanliness.revert_out_of_scope_drift`'s internal `git checkout HEAD
-- <path>` silently fails in nested-hub layouts (`hub_root != git_root`) because the
porcelain status lines it works from are git-root-relative while the function compares them
against a hub-relative `task_dir` and runs the checkout with `cwd=worktree` (hub root) — a
double-prefix that fails and leaves the file dirty. This batch adds the same `hub_prefix`
rebasing technique `compute_scope_violations` already uses in the same file, applied to
BOTH the porcelain lines and `owned_paths` (the latter needed to avoid a new regression: an
unrebased `owned_paths` would misclassify a genuine task-owned out-of-`task_dir`
modification as out-of-scope and silently revert real work — see `_mill/discussion.md`'s
`cleanliness-revert-hub-prefix-fix (#640)` Decision for the full rationale). External
interface for later batches: none.

## Cards

### Card 6: extend `revert_out_of_scope_drift` with `git_root`-aware hub-prefix rebasing

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `revert_out_of_scope_drift`'s signature from
  `revert_out_of_scope_drift(worktree: Path, task_dir: Path, parent_branch: str) ->
  tuple[list[str], list[str]]` to `revert_out_of_scope_drift(worktree: Path, task_dir: Path,
  parent_branch: str, git_root: Path | None = None) -> tuple[list[str], list[str]]` — the
  new parameter MUST default to `None` so the three existing call sites in
  `plugins/mill/unit_tests/test-cleanliness.py` (`ROOD-1` through `ROOD-4`, which call this
  function with exactly three positional arguments) remain valid without modification.
  Inside the function, after the existing `lines = _pygit2_util.status_porcelain(worktree,
  include_untracked=False)` line, compute `hub_prefix` exactly as `compute_scope_violations`
  already does in this same file (see its `if git_root is None: hub_prefix = "" else:
  hub_prefix = worktree.relative_to(git_root).as_posix(); if hub_prefix == ".": hub_prefix =
  ""` logic) — mirror that logic inline here (a local block, not necessarily a new shared
  helper function). Then, when building the in-scope/out-of-scope partition: rebase each
  porcelain line's path (`line[3:]`) from git-root-relative to hub-relative before comparing
  it against `task_dir_str` — when `hub_prefix` is non-empty and the path is neither equal
  to `hub_prefix` nor starts with `hub_prefix + "/"`, the line belongs to a different subtree
  of the git root and must be skipped entirely (neither reverted nor returned as remaining);
  otherwise strip the `hub_prefix` (+ separator) to get the hub-relative remainder, and use
  THAT remainder for both the `task_dir_str`/`owned_paths` membership check and as the path
  passed to the `git checkout HEAD -- <path>` subprocess call (which continues to run with
  `cwd=worktree`, unchanged). Apply the identical rebasing to every entry of `owned_paths`
  (built from `_parent_diff_names(worktree, parent_branch)`, which is git-root-relative for
  the same reason the porcelain lines are — `git diff --name-only` output is always relative
  to the repository toplevel regardless of `cwd`) BEFORE the `path in owned_paths` check
  runs — drop owned-path entries that fall outside `hub_prefix` using the same rule as
  above. `task_dir_str` itself needs no change — it is already hub-relative (the caller
  passes a hub-relative `task_dir`, unaffected by this fix). Update the function's docstring
  `Args:` section to document the new `git_root` parameter and its `None`-means-flat-layout
  default, matching `compute_scope_violations`'s existing docstring style for its own
  `git_root` parameter.
- **Commit:** `fix(cleanliness): rebase revert_out_of_scope_drift paths for nested-hub layouts`

### Card 7: thread `git_root` through the mill-go call site

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In "### 2b. Cleanliness gate", update the inline Python snippet's call
  from `_cleanliness.revert_out_of_scope_drift(worktree_root, task_dir, parent_branch)` to
  `_cleanliness.revert_out_of_scope_drift(worktree_root, task_dir, parent_branch, git_root)`
  — `git_root` is already resolved earlier in this skill's own Path Setup
  (`git_root = _paths.resolve_git_root()`) and remains in scope for the whole session, so no
  new resolution call is added here, only the extra positional argument. Update the
  `signature:` line immediately below the snippet from `` `signature:
  _cleanliness.revert_out_of_scope_drift(worktree: Path, task_dir: Path, parent_branch: str)
  -> tuple[list[str], list[str]]` `` to `` `signature:
  _cleanliness.revert_out_of_scope_drift(worktree: Path, task_dir: Path, parent_branch: str,
  git_root: Path | None = None) -> tuple[list[str], list[str]]` ``.
- **Commit:** `docs(mill-go): thread git_root into revert_out_of_scope_drift call`

### Card 8: nested-hub-layout regression tests

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add two new test blocks immediately after the existing `ROOD-4` block, in
  the same `try: ... print("PASS: ...") except AssertionError as exc: failures.append(...)
  except Exception as exc: failures.append(...)` style already used throughout this file,
  named in comments `ROOD-5` and `ROOD-6` (matching the file's existing numbered-comment
  convention). `ROOD-5` mirrors the nested-hub mocking pattern already in this file at
  `CV-7` (`git_root = Path(tmp)`, `hub_root = git_root / "hub"`): mock
  `_cleanliness._pygit2_util.status_porcelain` to return a git-root-relative out-of-scope
  tracked modification (e.g. `[" M hub/out_of_scope.txt"]`), mock
  `_cleanliness._parent_diff_names` to return `[]`, mock `_cleanliness._subprocess_util.run`
  to return `unittest.mock.Mock(returncode=0)`, call
  `revert_out_of_scope_drift(hub_root, Path("_mill"), "main", git_root=git_root)`, and
  assert `reverted == ["out_of_scope.txt"]` (the hub-relative form, proving the double-prefix
  bug from #640 is fixed) and that the mocked `git checkout` call's path argument
  (`mock_run.call_args[0][0]` is `["git", "checkout", "HEAD", "--", path]`, so index `4`) is
  `"out_of_scope.txt"`, not the git-root-relative `"hub/out_of_scope.txt"`. `ROOD-6` covers
  the `owned_paths` regression identified during
  discussion review: same nested-hub `git_root`/`hub_root` setup, mock
  `_pygit2_util.status_porcelain` to return a git-root-relative tracked modification outside
  `task_dir` (e.g. `[" M hub/owned.txt"]`), mock `_parent_diff_names` to return the SAME path
  git-root-relative (`["hub/owned.txt"]`, simulating a task-owned file per the parent-diff),
  mock `_subprocess_util.run`, call `revert_out_of_scope_drift(hub_root, Path("_mill"),
  "main", git_root=git_root)`, and assert `reverted == []` and that `remaining` contains the
  modification line (proving the owned file is correctly treated as in-scope and NOT
  reverted — this is the regression guard for the round-1 discussion-review GAP finding).
  Both new tests must pass alongside the unmodified `ROOD-1` through `ROOD-4` blocks (still
  three-positional-argument calls, valid via the new parameter's `None` default).
- **Commit:** `test(cleanliness): cover nested-hub-layout revert_out_of_scope_drift rebasing`

## Batch Tests

`verify:` runs `test-cleanliness.py` — the sole file this batch adds tests to (card 8),
which also imports and exercises the edited `_cleanliness.py` (card 6). Scoped via
`run-all.py --only`.
