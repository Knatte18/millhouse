# Batch: treeguard-helper

```yaml
task: "mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md"
batch: treeguard-helper
number: 1
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-treeguard.py"
depends-on: []
```

## Batch Scope

Deliver the reusable `_treeguard.py` module and its unit test — the core, TDD-flagged unit named in `_mill/discussion.md`'s Testing section. This batch has no dependency on `_status.py` and does not touch `status.md` at all: `check_and_restore` takes no `status_path`/`cfg` parameter, is a pure detect-and-restore function operating only on git state under a caller-supplied `worktree: Path`, and never calls into `_status.py`. The external interface the next batches (03/04/05) consume is exactly:

```python
def check_and_restore(worktree: Path, tracked_root: str = "_mill", *, git_root: Path | None = None) -> dict:
    """Returns {"triggered": bool, "restored_paths": list[str], "timestamp": str | None}."""
```

`git_root` is optional and defaults to `None` (flat-layout callers, or any caller that hasn't resolved one, pass nothing); every wiring call site added in batches 3-5 passes its own already-bound `git_root` explicitly. See `00-overview.md`'s "`check_and_restore` takes an optional `git_root`..." Shared Decision for why this parameter exists (round 2 plan-review GAP fix: `_pygit2_util.status_porcelain` returns paths relative to the git repository toplevel, not to `worktree`, so nested-hub layouts need an explicit rebase).

## Cards

### Card 1: Create `_treeguard.py` with `check_and_restore`

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_timestamp.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_treeguard.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Create `_treeguard.py` with a module docstring one line long (mirroring `_cleanliness.py:1`'s style, e.g. `"""Detect and restore deleted tracked files under a subtree (e.g. _mill/)."""`).
  - Import `_pygit2_util`, `_subprocess_util`, and `_timestamp` (for the trigger timestamp) at module level, plus `from pathlib import Path`.
  - Implement `check_and_restore(worktree: Path, tracked_root: str = "_mill", *, git_root: Path | None = None) -> dict`:
    1. Call `lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)`. These paths are always relative to the git repository toplevel, never to `worktree`, regardless of which path was passed in — see `_cleanliness.compute_scope_violations`'s docstring (`_cleanliness.py:62-63`) for this exact behavior, which this function must account for via steps 2-3 below.
    2. Compute `hub_prefix`: if `git_root is None`, `hub_prefix = ""`; otherwise `hub_prefix = worktree.relative_to(git_root).as_posix()`, normalized to `""` when that resolves to `"."` (flat layout). This is the identical technique `_cleanliness.revert_out_of_scope_drift` uses (`_cleanliness.py:365-372`).
    3. For each line, split into `status_code = line[:2]` and `raw_path = line[3:]` (mirrors `_cleanliness.revert_out_of_scope_drift`'s existing line-parsing idiom at `_cleanliness.py:406-407`). Rebase `raw_path` onto the hub: if `hub_prefix` is empty, the hub-relative path equals `raw_path` unchanged; otherwise, drop the line entirely (it belongs to a different subtree of the git root) unless `raw_path == hub_prefix` or `raw_path.startswith(hub_prefix + "/")`, and when kept, the hub-relative path is `raw_path[len(hub_prefix) + 1:]` (or `""` when `raw_path == hub_prefix`) — this exactly mirrors `_cleanliness.py`'s private `_rebase_onto_hub` closure (`_cleanliness.py:374-384`); do not import that closure (it is private to `_cleanliness.py`), reimplement the same logic inline or as a small module-local helper in `_treeguard.py`.
    4. A line is in-scope for this helper only when its hub-relative path (from step 3) equals `tracked_root` or starts with `tracked_root + "/"`.
    5. Among in-scope lines, collect the hub-relative path into `deleted_paths` for every line whose `status_code` is exactly `" D"` or `"D "` (per the Shared Decision "status codes and path-matching mirror `_cleanliness.py`'s existing partition logic" in `00-overview.md`). Every other status code (`"??"`, `" M"`, `"M "`, `"MM"`, or anything else) under `tracked_root` is ignored — never added to `deleted_paths`, never touched.
    6. If `deleted_paths` is empty: return `{"triggered": False, "restored_paths": [], "timestamp": None}` immediately. Make no `_subprocess_util.run` call in this branch (no-deletion case must not invoke git a second time).
    7. Otherwise, restore in one shot: `_subprocess_util.run(["git", "checkout", "HEAD", "--", *deleted_paths], cwd=worktree)` (mirrors `_cleanliness.py:432-435`'s exact argv/cwd shape, extended to accept multiple paths in one call instead of one path per call — note `deleted_paths` here are already hub-relative, matching `cwd=worktree`). Do not trust the subprocess's overall `returncode` alone to mean "every path was restored" — `git checkout HEAD -- <pathspecs>` can report a non-zero exit while still having restored some of the named paths (per-pathspec errors don't necessarily abort the whole invocation). Instead, verify the actual outcome per path: after the subprocess call, check `(worktree / path).exists()` for each entry in `deleted_paths`. Build `restored_paths` from only the paths that now exist on disk.
    8. If `restored_paths` is empty (the checkout restored nothing), print an ASCII-only diagnostic to stderr naming `deleted_paths` and the subprocess's captured stderr, then return `{"triggered": False, "restored_paths": [], "timestamp": None}` — a failed restore must never be reported as `triggered: True`, since callers (`_status.append_recovery_log`) treat that field as "a restore actually happened" and would otherwise log a false success.
    9. Otherwise return `{"triggered": True, "restored_paths": sorted(restored_paths), "timestamp": _timestamp.now_utc_iso()}`.
  - `check_and_restore` must not read `cwd()` for any config lookup — `worktree` is the only path input, taken as an explicit parameter (per `CLAUDE.md`'s "Helpers with path args must not consult cwd for config" invariant, and per `_mill/discussion.md`'s Constraints section).
  - `check_and_restore` must not import or reference `_status`, `status_path`, or `cfg` anywhere — it is a pure detect-and-restore function (per `_mill/discussion.md`'s "Reusable helper over duplicated Bash" Decision, resolving round 4's GAP).
  - Any diagnostic `print()`/log output this module emits must be ASCII-only (`—` → ` -- `) per project convention.
- **Commit:** `feat(mill): add _treeguard.check_and_restore for tracked-file deletion recovery`

### Card 2: Create `plugins/mill/unit_tests/test-treeguard.py`

- **Context:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-treeguard.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Follow `test-status.py`'s existing runner shape: a single `main() -> int` function, `from __future__ import annotations`, imports of `subprocess`, `sys`, `tempfile`, `unittest.mock`, `pathlib.Path`, and `from _treeguard import check_and_restore` (mirroring `test-cleanliness.py`'s `sys.path`-relative import block for `_cleanliness`), one `with tempfile.TemporaryDirectory() as tmp:` block per scenario, `print("PASS: ...")` after each successful assertion, and a single top-level `try/except AssertionError` in `main()` that aborts on the first failure, prints `FAIL: {exc}` to stderr, and returns 1, returning 0 and printing an `All _treeguard unit tests passed.` line when every scenario passes (do not use `unittest`/`pytest` classes). Do not model this file after `test-cleanliness.py`'s own runner shape — that file wraps each scenario in its own try/except, accumulates a `failures` list, and reports every failure at the end without aborting early, which is a materially different (and NOT the one to follow) pattern; `test-cleanliness.py` is cited elsewhere in this card only for its git/mocking *fixture* idioms, not its runner shape.
  - Fixture helper: initialize a real tempfile-based git repo (`git init`, configure a throwaway `user.email`/`user.name` via `git config` so commits succeed non-interactively, matching how other tempfile-based git fixtures in this test suite avoid relying on global git config), create a `_mill/` tree with `status.md`, `discussion.md`, `briefs/x.md`, `reviews/y.md`, and commit it (`git add -A && git commit -m "seed"`).
  - Implement every scenario from `_mill/discussion.md`'s Testing section, each as its own `with tempfile.TemporaryDirectory()` block:
    1. **No deletion:** call `check_and_restore` on the clean seeded tree; assert `result["triggered"] is False`, `result["restored_paths"] == []`, `result["timestamp"] is None`, and that every seeded file is still present and byte-identical to its committed content afterward.
    2. **Single file deleted:** delete `_mill/status.md` from disk with `Path(...).unlink()` (not via `git rm`), call `check_and_restore`, assert the file is restored (exists again, content matches the committed blob), `result["triggered"] is True`, and `result["restored_paths"] == ["_mill/status.md"]`.
    3. **Multiple files deleted across subdirectories:** delete `_mill/status.md` and `_mill/briefs/x.md` simultaneously (both via `unlink()`, no commit), call `check_and_restore` once, assert both files are restored and both paths appear in `result["restored_paths"]` (sorted).
    4. **Staged deletion:** run `git rm _mill/discussion.md` (stages the deletion without committing — status code `"D "`), call `check_and_restore`, assert the file is restored to disk and tracked again as unmodified, and `result["triggered"] is True`.
    5. **Untracked file alongside a real deletion:** create an untracked file at `_mill/scratch-leftover.txt` (never `git add`ed) alongside deleting `_mill/status.md` (`unlink()`), call `check_and_restore`, assert `_mill/status.md` is restored, and assert the untracked file is completely untouched (still present, unchanged, and not mentioned in `result["restored_paths"]`) — proving `"??"` porcelain lines never enter the restore pathspec.
    6. **Legitimate uncommitted modification alongside a real deletion (regression case for round 2's GAP):** append a line to `_mill/status.md` and leave it uncommitted (status code `" M"`), and separately delete `_mill/reviews/y.md` (`unlink()`, status code `" D"`). Capture `_mill/status.md`'s mtime and full content before calling `check_and_restore`. Call `check_and_restore` once and assert: `_mill/reviews/y.md` is restored (present again, matching HEAD content); `_mill/status.md`'s mtime and content are byte-for-byte unchanged from the captured values (proving `check_and_restore` never opens `status.md` for writing at all, let alone reverts its uncommitted append); `result["restored_paths"] == ["_mill/reviews/y.md"]` (never includes `status.md`).
    7. **Failed restore is never reported as triggered (regression case for round 1's GAP):** delete `_mill/status.md` on disk (`unlink()`, status code `" D"`, so the detection query finds a real candidate), then patch `_treeguard._subprocess_util.run` (via `unittest.mock.patch`, matching `test-cleanliness.py`'s existing `unittest.mock.patch("_cleanliness._subprocess_util.run")` pattern) to return a `CompletedProcess` with a non-zero `returncode` and no side effect on disk (the mock must not actually run git, so the file stays deleted). Call `check_and_restore` and assert `result["triggered"] is False`, `result["restored_paths"] == []`, and `_mill/status.md` is still absent from disk afterward — proving a checkout that restores nothing is never reported as a successful trigger.
    8. **Nested-hub layout rebases git-root-relative porcelain paths onto the hub before matching (regression case for round 2's GAP):** does not need a real nested git fixture — mock the boundary the same way `test-cleanliness.py`'s `ROOD-5` scenario does. Patch `_treeguard._pygit2_util.status_porcelain` (via `unittest.mock.patch`) to return `[" D hub/_mill/status.md"]` (a git-root-relative porcelain line, as if the hub were nested one level under the git root as `<git_root>/hub`), and patch `_treeguard._subprocess_util.run` to return `unittest.mock.Mock(returncode=0)` without touching disk. Call `check_and_restore(hub_root, "_mill", git_root=git_root_path)` where `hub_root = git_root_path / "hub"` (both plain, non-existent-on-disk `Path` objects — no tempdir needed since the git call itself is mocked). Assert: the mocked `_subprocess_util.run` was called with hub-relative argv `["git", "checkout", "HEAD", "--", "_mill/status.md"]` (never the git-root-relative `"hub/_mill/status.md"`); `result["restored_paths"] == ["_mill/status.md"]`; `result["triggered"] is True`. This is the literal regression case review round 2 flagged: an unrebased implementation would never match `"hub/_mill/status.md"` against bare `"_mill"` and would silently return `triggered: False`.
    9. **`git_root=None` behaves like a flat layout, not a `TypeError` or a silent no-op:** repeat the single-file-deletion scenario (2) but pass `git_root=None` explicitly (rather than omitting the keyword) and assert the result is identical to scenario 2's — confirming the default/`None` path exercises the empty-`hub_prefix` branch correctly rather than raising on `worktree.relative_to(None)` or some other `None`-handling mistake.
- **Commit:** `test(mill): add test-treeguard.py covering detection and restore scenarios`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-treeguard.py` directly — the single new test file this batch adds, scoped per the project's per-batch verify convention (no cross-cutting helper touched, so no `run-all.py --only` list is needed).
