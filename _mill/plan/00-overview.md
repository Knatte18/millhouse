# Plan: _verify_baseline.py transient worktrees can be orphaned when the task worktree is force-removed mid-computation

```yaml
task: _verify_baseline.py transient worktrees can be orphaned when the task worktree is force-removed mid-computation
slug: verify-baseline-nested-worktree-orphan-risk
approved: false
started: 2026-08-09T06:00:29Z
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: worktree-remove-safe-prune
    file: 01-worktree-remove-safe-prune.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: centralize-fix-in-remove-safe

- **Decision:** Fix `_worktree.remove_safe` itself rather than adding registry/tracking machinery to `_verify_baseline.py`.
- **Rationale:** `git worktree prune` only removes administrative entries whose linked working directory is verifiably missing, so it is safe to call unconditionally and idempotently, including under concurrency (a sibling task's still-live nested worktree has a directory that still exists, so prune never touches it). Fixing `remove_safe` covers every current and future caller uniformly, including the independently-confirmed second call site in `millpy-implement.py`'s shared per-batch baseline checkout, which uses the identical `_verify_baseline._checkout_parent_branch` + `remove_safe`-in-`finally` pattern.
- **Applies to:** all batches

### Decision: prune-runs-once-unconditionally

- **Decision:** Restructure `remove_safe` so `git worktree prune` is called exactly once, after either the success branch (`git worktree remove --force` returns 0) or the fallback branch (`_safe_rmtree.safe_rmtree` fallback) completes successfully — not duplicated as separate calls in each branch. Exception-raising paths (`WorktreeLockedError`, base `WorktreeError`) do not call prune; only a path that actually finishes removing the worktree runs it.
- **Rationale:** DRY. The prune call's semantics (cwd, warn-on-failure, message text) are identical regardless of which branch removed the worktree; a single shared tail call is simpler to maintain than two copies that could drift.
- **Applies to:** worktree-remove-safe-prune

### Decision: prune-failure-is-non-fatal

- **Decision:** If the new unconditional `git worktree prune` call itself fails, print a warning to stderr and continue — do not raise.
- **Rationale:** Matches the existing fallback-path behavior. Prune failure is a hygiene/best-effort step, not correctness-critical — the worktree removal itself already succeeded by the time prune runs. Raising here would regress currently-working teardown paths over a secondary cleanup step.
- **Applies to:** worktree-remove-safe-prune

## All Files Touched

- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/unit_tests/test-worktree.py`
