# Plan: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md

```yaml
task: "mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md"
slug: mill-start-tracked-files-vanish-mid-review
approved: true
started: "20260729-072604"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: treeguard-helper
    file: 01-treeguard-helper.md
    depends-on: []
    verify: null
  - number: 2
    name: status-recovery-log
    file: 02-status-recovery-log.md
    depends-on: []
    verify: null
  - number: 3
    name: mill-start-wiring
    file: 03-mill-start-wiring.md
    depends-on: [1, 2]
    verify: null
  - number: 4
    name: mill-plan-wiring
    file: 04-mill-plan-wiring.md
    depends-on: [1, 2]
    verify: null
  - number: 5
    name: mill-go-wiring
    file: 05-mill-go-wiring.md
    depends-on: [1, 2]
    verify: null
```

## Shared Decisions

### Decision: git-status detection reuses `_pygit2_util.status_porcelain`, restore uses `_subprocess_util.run` git-checkout

- **Decision:** `_treeguard.check_and_restore` detects deletions by calling `_pygit2_util.status_porcelain(worktree, include_untracked=False)` (whole-repo porcelain lines, always git-repository-toplevel-relative regardless of the `path` argument passed to it — see the next Decision for why this requires an explicit rebase step) and filtering, in Python, to lines whose *hub-rebased* path starts with `tracked_root + "/"` or equals `tracked_root`. It restores by shelling out via `_subprocess_util.run(["git", "checkout", "HEAD", "--", *paths], cwd=worktree)` for the exact list of deleted paths found, using the hub-relative form of each path (matching `cwd=worktree`).
- **Rationale:** `_cleanliness.revert_out_of_scope_drift` (`plugins/mill/scripts/_cleanliness.py:324-451`) is the nearest existing analog named in `_mill/discussion.md`'s Technical context and already establishes this exact pair of primitives for git-based drift detection/reversion: `_pygit2_util.status_porcelain` for the read side (matching the project's pygit2-over-raw-subprocess convention for status reads — see `_cleanliness.capture_snapshot`/`compute_new_dirt`), and a direct `_subprocess_util.run(["git", "checkout", "HEAD", "--", path], cwd=worktree)` call for the write side (pygit2 has no equivalently simple "restore this path to HEAD" call in this codebase's existing usage). `_treeguard.py` follows the same pairing rather than introducing a third git-invocation style. `pygit2`'s `status()` has no pathspec-limiting parameter, so the `tracked_root` scoping happens as a plain Python string-prefix filter over the full-repo result, not a `git status -- <pathspec>` CLI argument — behaviorally identical to the discussion's `git -C <worktree> status --porcelain -- <tracked_root>` framing, implemented via the codebase's existing pygit2 wrapper instead of a raw CLI invocation.
- **Applies to:** batch `treeguard-helper` only (this is `_treeguard.py`'s sole implementation, not referenced elsewhere).

### Decision: `check_and_restore` takes an optional `git_root` and rebases git-root-relative porcelain paths onto the hub (round 2 plan-review GAP fix)

- **Decision:** `check_and_restore`'s signature is `check_and_restore(worktree: Path, tracked_root: str = "_mill", *, git_root: Path | None = None) -> dict`. When `git_root` is not `None`, every porcelain path (which `_pygit2_util.status_porcelain` always returns relative to the git repository toplevel, never relative to `worktree`) is rebased onto `worktree` before the `tracked_root` in-scope check, using the identical technique `_cleanliness.revert_out_of_scope_drift`/`compute_scope_violations` already use: `hub_prefix = worktree.relative_to(git_root).as_posix()` (empty string when it resolves to `"."`, i.e. flat layout); a path is dropped (belongs to a different subtree entirely) unless it equals `hub_prefix` or starts with `hub_prefix + "/"`; the hub-relative remainder is `path[len(hub_prefix) + 1:]` (or `""` when `path == hub_prefix`). When `git_root` is `None`, this rebase is a no-op (`hub_prefix = ""`, every path passes through unchanged) — identical to a flat layout where `worktree == git_root`.
- **Rationale:** Round 2 plan review confirmed this was a correctness gap serious enough to defeat the entire task: `_pygit2_util.status_porcelain(worktree, ...)` opens the repository and calls `repo.status()`, which pygit2 always reports relative to the discovered repository's root — not relative to whatever `path` argument was passed in (`_cleanliness.compute_scope_violations`'s own docstring states this explicitly: "`_pygit2_util.status_porcelain` always returns paths relative to the git repository toplevel, regardless of which path is passed to it"). `_paths.resolve_hub_path`/`resolve_active_hub` (which produce the `worktree_root` every call site passes to `check_and_restore`) explicitly support a hub root nested under the git root — the exact layout `_mill/discussion.md`'s Problem section names as where the original #726 incident occurred. In that layout, porcelain lines read `"<hub-relative-prefix>/_mill/status.md"`, never bare `"_mill/status.md"` — so an unrebased `check_and_restore` would silently never match any line under `tracked_root`, meaning `triggered` would always be `False` regardless of what actually got deleted. Every call site already has `git_root` bound locally (`_paths.resolve_git_root()`, resolved in each skill's own Entry/Path Setup section) — see the "Config/path resolution" passage in `_mill/discussion.md`'s Technical context, which already establishes `worktree_root` and `git_root` as two distinct, both-already-bound locals at every one of these call sites.
- **Applies to:** batch `treeguard-helper` (the implementation), and every call site added in batches `mill-start-wiring`, `mill-plan-wiring`, and `mill-go-wiring` (all must now pass `git_root=git_root`).
- **Rejected:** Leaving `check_and_restore` worktree-relative-only and documenting nested-hub layouts as an accepted gap — rejected outright: this is not a residual-risk-worthy edge case, it is the literal layout the task's own motivating incident occurred in, and leaving it unhandled would silently defeat the entire task's purpose in exactly the environment that matters most.

### Decision: status codes and path-matching mirror `_cleanliness.py`'s existing partition logic

- **Decision:** A porcelain line is a "deletion" for `check_and_restore`'s purposes when its two-character status code (the line's first two characters, per `_pygit2_util.status_porcelain`'s `"{x}{y} {filepath}"` format) is exactly `" D"` (worktree-deleted) or `"D "` (staged-deleted). Any other code — including `"??"` (untracked), `" M"`/`"M "`/`"MM"` (modified), or any other combination — is left untouched and excluded from the restore pathspec.
- **Rationale:** Directly implements the discussion's "Detection query and restore granularity" Decision and its regression-tested scenarios (round 2's GAP: a legitimate uncommitted `" M"` modification must never be swept into the restore). `_cleanliness.py:429` already partitions on an analogous two-character-code check (`status_code in (" M", "M ", "MM")`) for its own (different) purpose, confirming this is the established idiom for this codebase rather than a new convention.
- **Applies to:** batch `treeguard-helper`.

## All Files Touched

- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_treeguard.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-status.py`
- `plugins/mill/unit_tests/test-treeguard.py`
