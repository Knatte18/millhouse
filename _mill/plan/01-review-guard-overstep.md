# Batch: review-guard-overstep

```yaml
task: "mill-go / mill-plan loop hardening"
batch: review-guard-overstep
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-pygit2-util.py test-review-guard.py
depends-on: []
```

## Batch Scope

Fixes #374: `worktree_snapshot_guard` raises `ReviewerOverstepError` on any HEAD-SHA
change during a review, so a concurrent operator commit aborts the run. This batch adds
a git-ancestry helper and reworks the guard so a benign fast-forward commit is tolerated
while genuine reviewer overstep (new working-tree dirt, or a non-descendant HEAD
rewrite/reset) is still caught. Card 1 adds the `is_ancestor` primitive; card 2 consumes
it in the guard. Both live in the review backend and have existing test files.

External interface consumed downstream: none (the guard is internal to the review
engine). No SKILL changes — mill-go does not describe the overstep guard in prose.

## Cards

### Card 1: add is_ancestor to _pygit2_util

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/unit_tests/test-pygit2-util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `is_ancestor(path: Path, ancestor_sha: str, descendant_sha: str) -> bool` to `_pygit2_util.py`. Open the repo with the existing `open_repo(path)`; return `True` when `descendant_sha` is a descendant of (or equal to) `ancestor_sha`, else `False`. Implement via pygit2's `repo.descendant_of(descendant_sha, ancestor_sha)`, and special-case `ancestor_sha == descendant_sha` to return `True` (pygit2 returns `False` for equal commits). Catch `pygit2.GitError` / `KeyError` / `ValueError` and re-raise as `GitOpsError`, mirroring `head_sha`'s ASCII-safe error formatting. Add `"is_ancestor"` to `__all__`. Add tests to `test-pygit2-util.py` covering: a real ancestor→descendant chain returns `True`; an unrelated/sibling commit returns `False`; identical SHAs return `True`; an invalid SHA raises `GitOpsError`.
- **Commit:** `feat(pygit2): add is_ancestor ancestry helper`

### Card 2: tolerate fast-forward HEAD advance in overstep guard

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-guard.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rework the exit condition of `worktree_snapshot_guard` in `_review_common.py` (currently `if before_sha != after_sha or set(before_filtered) != set(after_filtered): raise ReviewerOverstepError(...)`). Compute `added = set(after_filtered) - set(before_filtered)` and `removed = set(before_filtered) - set(after_filtered)`, and `head_changed = before_sha != after_sha`, and `fast_forward = head_changed and _pygit2_util.is_ancestor(project_root, before_sha, after_sha)`. Raise `ReviewerOverstepError(before_sha, after_sha, diff)` when ANY of: (a) `added` is non-empty (reviewer introduced new working-tree dirt — always overstep, regardless of HEAD); (b) `head_changed and not fast_forward` (HEAD moved to a non-descendant — a rewrite/reset); (c) `removed` is non-empty AND `not fast_forward` (dirt disappeared with no commit to explain it). When `fast_forward` is true and neither (a) nor (b) fires, do NOT raise; emit a one-line stderr warning `[_review_common] HEAD advanced {before_sha[:8]} -> {after_sha[:8]} during review window (fast-forward; allowed)`. Preserve the existing inner-exception semantics exactly: if an overstep is raised, chain via `from inner_exc`; if no overstep and `inner_exc is not None`, re-raise `inner_exc`; the post-snapshot-capture-failure path (`_capture_head_sha` raising) is unchanged. Import `_pygit2_util` at module top if not already imported. Build the diff string with the existing `_porcelain_diff(before_filtered, after_filtered)` helper. Add tests to `test-review-guard.py`: clean window passes; a new untracked/modified file (no HEAD change) raises; a fast-forward commit that only removes prior dirt passes (no raise); a `git reset --hard` to a non-descendant commit raises; a fast-forward commit PLUS a new untracked file still raises. **Update the two existing legacy cases that contradict the new tolerance:** `test-review-guard.py` Case B ("git commit inside with raises, HEAD differs") and Case F ("commit inside expected_paths raises, HEAD changed") both currently assert `ReviewerOverstepError` for a clean-before/clean-after fast-forward commit — exactly the scenario now allowed. Update Case B to assert NO raise (the guard returns normally) and add a stderr-capture assertion for the fast-forward warning; apply the same update to Case F. Do NOT remove them — the new "fast-forward commit that only removes prior dirt passes" test does not duplicate the commit-inside-`expected_paths` scenario Case F covers. After this card, every case in `test-review-guard.py` must pass under the new logic so the batch `verify:` is green.
- **Commit:** `fix(review): tolerate fast-forward HEAD advance in overstep guard (#374)`

## Batch Tests

`verify:` runs `test-pygit2-util.py` (the `is_ancestor` helper) and `test-review-guard.py`
(the `worktree_snapshot_guard` behaviour matrix). Both use real temp-repo git via
subprocess, so the ancestry / fast-forward / reset scenarios are exercised end-to-end.
`test-review-common-guard.py` also touches the guard but is not in scope for new
assertions; the `--only` list is the two files whose behaviour this batch changes.
