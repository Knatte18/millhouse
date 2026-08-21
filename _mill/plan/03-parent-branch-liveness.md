# Batch: parent-branch-liveness

```yaml
task: 'mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs'
batch: parent-branch-liveness
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
depends-on: []
```

## Batch Scope

Fixes `#879`: `_parent_branch.check_liveness` only checks `git ls-remote --exit-code origin <branch>`, so a live, local-only (never-pushed) parent branch is misclassified as dead, triggering an unnecessary `resolve_dead_parent` archive-chain walk. Widen `check_liveness` to also accept a live local branch ref as "alive", and add unit test coverage for the function (none exists today — `plugins/mill/unit_tests/test-parent-branch.py` currently only tests `resolve`/`resolve_for_codeguide`). One code card + one test card, same file pair, same batch. Every fenced block below reproduces the source file's own byte-exact indentation (flush left, no extra indent from this card's own list nesting) — copy fence contents literally.

## Cards

### Card 5: check_liveness — widen to accept a live local branch ref

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edits in this file.

  **Edit A — module docstring.** Find this exact text:

```
    check_liveness(branch, git_root) -> bool Return True if branch currently exists on origin
    (``git ls-remote --exit-code``).
```

  Replace it with:

```
    check_liveness(branch, git_root) -> bool Return True if branch currently exists on origin
    (``git ls-remote --exit-code``) or as a live local branch ref (``git rev-parse --verify``).
```

  **Edit B — the `check_liveness` function.** Find this exact text:

```
def check_liveness(branch: str, git_root: Path) -> bool:
    """
    Return True if `branch` currently exists on `origin` (`git ls-remote --exit-code`).

    `git branch -a` / local remote-tracking refs are deliberately not used as the liveness
    signal, because `mill-cleanup`'s remote-branch deletion never prunes them -- a torn-down
    parent's stale local `origin/<branch>` ref would otherwise report as alive.
    """
    result = _subprocess_util.run(
        ["git", "-C", str(git_root), "ls-remote", "--exit-code", "origin", branch],
        check=False,
    )
    return result.returncode == 0
```

  Replace it with:

```
def check_liveness(branch: str, git_root: Path) -> bool:
    """
    Return True if `branch` currently exists on `origin`, OR exists as a local branch ref.

    Checks `git ls-remote --exit-code origin <branch>` first; if that fails, falls back to
    `git rev-parse --verify --quiet refs/heads/<branch>` against `git_root` -- a live, local-only
    (never-pushed) parent branch is not dead (#879).

    `git branch -a` / local *remote-tracking* refs (`refs/remotes/origin/<branch>`) are
    deliberately not used as the liveness signal, because `mill-cleanup`'s remote-branch
    deletion never prunes them -- a torn-down parent's stale local `origin/<branch>` ref would
    otherwise report as alive. This is a distinct signal from the local *branch* ref
    (`refs/heads/<branch>`) checked below, which mill-cleanup DOES delete when a task is torn
    down, so it carries no equivalent staleness risk.
    """
    result = _subprocess_util.run(
        ["git", "-C", str(git_root), "ls-remote", "--exit-code", "origin", branch],
        check=False,
    )
    if result.returncode == 0:
        return True
    local_result = _subprocess_util.run(
        ["git", "-C", str(git_root), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        check=False,
    )
    return local_result.returncode == 0
```

  Do not modify `resolve_dead_parent`, `resolve`, `resolve_for_codeguide`, or any other function in this file — both call sites of `check_liveness` (`mill-merge/SKILL.md` Entry Step 4, `mill-merge-in/SKILL.md` Entry step 2) already branch on a single `alive` boolean and need no changes.
- **Commit:** `fix(_parent_branch): check_liveness accepts a live local branch ref, not just origin (#879)`

### Card 6: check_liveness — add unit test coverage

- **Context:**
  - `plugins/mill/unit_tests/test-pr-state.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-parent-branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** No unit test for `check_liveness` exists today. Add coverage to `plugins/mill/unit_tests/test-parent-branch.py`, mocking `_subprocess_util.run` exactly the way `test-pr-state.py`'s `_make_run_mock`/`patch.object(_pr_state._subprocess_util, "run", ...)` pattern does (read `test-pr-state.py` in full for the exact mock shape — a `MagicMock` with `.returncode` set, patched via `unittest.mock.patch.object`).

  1. Add `from unittest.mock import MagicMock, patch` to the imports.
  2. Add `import _parent_branch` (the whole module, alongside the existing `from _parent_branch import ParentBranchError, resolve, resolve_for_codeguide`) — patching `_subprocess_util.run` as an attribute of the `_parent_branch` module (i.e. `patch.object(_parent_branch._subprocess_util, "run", ...)`) requires the module object, not just the imported names.
  3. Add a `_make_run_mock(returncode: int) -> MagicMock` helper mirroring `test-pr-state.py`'s `_make_run_mock` (only `returncode` is needed — `check_liveness` never parses stdout/stderr).
  4. Add four new assertions inside `main()`'s existing `try:` block (this file uses a single sequential `main()` with asserts+prints, not a `tests = [...]` registration list — follow that existing structure, do not introduce a new pattern):
     - Remote alive (`ls-remote` returns 0): patch with `return_value=_make_run_mock(0)`; assert `_parent_branch.check_liveness("main", Path(tmp)) is True`. Also assert the mock was called exactly once (`mock_run.call_count == 1`) — confirms the local-ref fallback is skipped when the remote check already succeeds.
     - Remote dead, local alive: patch with `side_effect=[_make_run_mock(1), _make_run_mock(0)]` (first call = `ls-remote` returns 1, second call = `rev-parse --verify` returns 0); assert `check_liveness(...) is True`.
     - Both dead: patch with `side_effect=[_make_run_mock(2), _make_run_mock(1)]`; assert `check_liveness(...) is False`.
     - Print a `PASS:` line after each assertion, matching this file's existing style (see the four `print("PASS: ...")` calls already in `main()`).
  5. Use a fresh `tempfile.TemporaryDirectory()` (or reuse the existing one already open in `main()`) as the `git_root` argument — `check_liveness` never touches the filesystem itself (all git calls are mocked), so the directory need not be a real git repo for these three new assertions.
- **Commit:** `test(_parent_branch): add check_liveness coverage for remote-alive, local-only-alive, and dead cases (#879)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py` — runs the single test file covering both this batch's code change (Card 5) and its new test coverage (Card 6). Scoped to the one file this batch touches, per the "Verify command scope" convention.
