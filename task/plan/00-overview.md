# Plan: Drop active.slug.md marker

```yaml
task: Drop active.slug.md marker
slug: drop-active-marker
approved: true
started: 20260509-161652
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches. Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-marker.py
  - number: 2
    name: migration
    file: 02-migration.md
    depends-on: [1]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: integration-tests
    file: 03-integration-tests.md
    depends-on: [2]
    verify: null
  - number: 4
    name: skill-docs
    file: 04-skill-docs.md
    depends-on: [2]
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits._

### Decision: import-style stays flat

- **Decision:** New module `_marker.py` follows the existing flat-Python convention in `plugins/mill/scripts/`. Top-level functions, leading-underscore filenames for non-CLI helpers, no smoke-test `if __name__ == "__main__":` blocks (those are reserved for `millpy-*.py`).
- **Rationale:** Matches the convention every other helper in this directory follows. Drift from convention forces readers to special-case mental models.
- **Applies to:** all batches.

### Decision: branch-prefix strip uses `removeprefix`

- **Decision:** When `cfg["spawn"]["branch_prefix"]` is non-empty, derive slug as `branch.removeprefix(prefix)`. Validate that `branch.startswith(prefix)` BEFORE the strip and raise `MarkerError` when it does not. When `branch_prefix` is empty, slug equals branch.
- **Rationale:** `str.removeprefix` is the canonical Python 3.9+ stdlib helper; explicit prefix-validation surfaces operator drift loudly. Greedy fallback (try-without-prefix-then-with) is rejected per discussion.md.
- **Applies to:** Batch 1 (`_marker.slug_from_branch` implementation), Batch 2 (every consumer that uses `_marker`).

### Decision: `_marker.task_data` returns exactly three keys

- **Decision:** `task_data` returns `{"slug": str, "branch": str, "task_title": str}`. No `parent`, no `spawned_at`, no extra keys.
- **Rationale:** Exact replacement for the consumed subset of the old `_active.read_all`. Adding fields invites speculation about which keys are stable.
- **Applies to:** Batch 1 (implementation), Batch 2 (consumers — every `_active.read_all(mill_dir)["task_title"]` becomes `_marker.task_data(...)["task_title"]`).

### Decision: `MarkerError` semantics

- **Decision:** `_marker.MarkerError(RuntimeError)` raised when (a) `git branch --show-current` returns empty (detached HEAD), or (b) the branch does not start with non-empty `cfg["spawn"]["branch_prefix"]`, or (c) the stripped slug is not present in Home.md, or (d) the slug is present in Home.md but its phase marker is not `"active"` (per-slug strict-active reads only — `discover_active_worktrees` accepts any phase).
- **Rationale:** Single typed exception per discussion.md. Callers that need to catch "is this a mill task worktree?" import `_marker.MarkerError`. Pre-rewrite callers caught `_active.ActiveError`; the rename is mechanical.
- **Applies to:** all batches.

### Decision: `_paths.ActiveWorktreeSlugMismatch` and `ActiveWorktreeNotFound` retained

- **Decision:** Both exception classes survive in `_paths.py.__all__`. `resolve_active_worktree` keeps raising them on the same conditions; only the *triggering check* changes (branch-derived slug vs marker-derived slug).
- **Rationale:** Per discussion.md — the semantic "the worktree dir at `<container>/wts/<slug>/` is on a different task than the requested slug" is a real condition that should remain a typed exception. Callers and tests already depend on these types.
- **Applies to:** Batch 2.

### Decision: helper signature `(git_root, wiki_path, cfg)` argument order

- **Decision:** All new `_marker` callsites pass `(git_root, wiki_path, cfg)` in that order. `_review_common.find_active_slug(git_root, wiki_path, cfg)` and `load_task_title(git_root, wiki_path, cfg, slug)` follow the same order; the `slug` fallback argument trails on `load_task_title`.
- **Rationale:** Matches the existing `_paths.resolve_active_worktree(container_path, slug, *, cfg, git_root)` argument order convention (path-first, config-last). `load_task_title`'s trailing `slug` argument preserves the caller's existing positional-arg pattern.
- **Applies to:** Batch 1 (signatures), Batch 2 (callers).

### Decision: `home_tasks` parameter for `discover_active_worktrees`

- **Decision:** New signature `discover_active_worktrees(worktrees_dir: Path, home_tasks: list[_tasks_md.Task]) -> list[tuple[Path, str, str]]`. Caller pre-loads and parses Home.md.
- **Rationale:** Decouples the helper from layout assumptions about where `wiki_path` lives relative to `worktrees_dir`. mill-cleanup already had `home_tasks` parsed at line 484; the call must be reordered to put the parse before the discover call. mill-vscode, mill-terminal, mill-status, mill-inspect, mill-migrate-layout each load Home.md once before invoking discover.
- **Applies to:** Batch 2.

### Decision: leftover marker files left as cruft

- **Decision:** Existing `.millhouse/active.slug.md` files in the user's worktrees are not deleted by this task. No migration script.
- **Rationale:** Per discussion.md — they're gitignored, never read by the new code, and removed when their worktree is removed by mill-merge / mill-cleanup. Adding a migration helper exceeds the cost of dead bytes.
- **Applies to:** all batches (negative scope marker).

### Decision: integration tests updated alongside production

- **Decision:** Integration tests under `plugins/mill/integration_tests/` that reference the marker file (line 200-205 of `test-spawn.py`, lines 187/212/222 of `test-merge.py`, line 103 of `test-abandon.py`) are updated in Batch 3.
- **Rationale:** They are excluded from `run-all.py`'s discovery (which globs `unit_tests/test-*.py`), so they don't break Batch 2's verify. But they DO reference symbols that vanish in Batch 2; updating them in Batch 3 keeps them runnable.
- **Applies to:** Batch 3.

### Decision: SKILL.md updates are pure prose edits

- **Decision:** SKILL.md updates in Batch 4 only edit prose; no fenced-code-block API examples need new mechanics beyond replacing `_active.read_slug(Path(".millhouse"))` with the `_marker` equivalent.
- **Rationale:** SKILL.md prose is read by the agent at skill-load time, not executed. Updates land in Batch 4 to keep the code-vs-docs split clean.
- **Applies to:** Batch 4.

## All Files Touched

- `plugins/mill/scripts/_active.py`
- `plugins/mill/scripts/_inplace.py`
- `plugins/mill/scripts/_marker.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-abandon.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-color.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-inspect.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-migrate-layout.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-status.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/scripts/millpy-validate-plan.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/skills/mill-autofix/SKILL.md`
- `plugins/mill/skills/mill-claim/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/mill-terminal/SKILL.md`
- `plugins/mill/integration_tests/test-abandon.py`
- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/integration_tests/test-spawn.py`
- `plugins/mill/unit_tests/_test_helpers.py`
- `plugins/mill/unit_tests/test-abandon.py`
- `plugins/mill/unit_tests/test-active.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-inplace.py`
- `plugins/mill/unit_tests/test-marker.py`
- `plugins/mill/unit_tests/test-mill-merge-inplace.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-millpy-color.py`
- `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-millpy-terminal.py`
- `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- `plugins/mill/unit_tests/test-millpy-vscode.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
