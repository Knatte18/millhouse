# Plan: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md

```yaml
task: "mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md"
slug: mill-start-tracked-files-vanish-mid-review
approved: false
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

- **Decision:** `_treeguard.check_and_restore` detects deletions by calling `_pygit2_util.status_porcelain(worktree, include_untracked=False)` (whole-repo porcelain lines) and filtering, in Python, to lines whose path starts with `tracked_root + "/"` or equals `tracked_root`. It restores by shelling out via `_subprocess_util.run(["git", "checkout", "HEAD", "--", *paths], cwd=worktree)` for the exact list of deleted paths found.
- **Rationale:** `_cleanliness.revert_out_of_scope_drift` (`plugins/mill/scripts/_cleanliness.py:324-445`) is the nearest existing analog named in `_mill/discussion.md`'s Technical context and already establishes this exact pair of primitives for git-based drift detection/reversion: `_pygit2_util.status_porcelain` for the read side (matching the project's pygit2-over-raw-subprocess convention for status reads — see `_cleanliness.capture_snapshot`/`compute_new_dirt`), and a direct `_subprocess_util.run(["git", "checkout", "HEAD", "--", path], cwd=worktree)` call for the write side (pygit2 has no equivalently simple "restore this path to HEAD" call in this codebase's existing usage). `_treeguard.py` follows the same pairing rather than introducing a third git-invocation style. `pygit2`'s `status()` has no pathspec-limiting parameter, so the `tracked_root` scoping happens as a plain Python string-prefix filter over the full-repo result, not a `git status -- <pathspec>` CLI argument — behaviorally identical to the discussion's `git -C <worktree> status --porcelain -- <tracked_root>` framing, implemented via the codebase's existing pygit2 wrapper instead of a raw CLI invocation.
- **Applies to:** batch `treeguard-helper` only (this is `_treeguard.py`'s sole implementation, not referenced elsewhere).

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
