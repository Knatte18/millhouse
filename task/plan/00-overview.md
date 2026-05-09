# Plan: "35 (A) — Centralize path resolution across all three modes"

```yaml
task: "35 (A) — Centralize path resolution across all three modes"
slug: mill-path-resolution-audit
approved: true
started: "20260509-103144"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: paths-helpers
    file: 01-paths-helpers.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-paths.py
  - number: 2
    name: review-common-switch
    file: 02-review-common-switch.md
    depends-on: [1]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
  - number: 3
    name: abandon-fix
    file: 03-abandon-fix.md
    depends-on: [1]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-abandon.py
  - number: 4
    name: cleanup-inline-refactor
    file: 04-cleanup-inline-refactor.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanup.py
  - number: 5
    name: docs
    file: 05-docs.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

### Decision: TDD-first ordering within batch 1

- **Decision:** In Batch 1, the test-update card (Card 1) is committed before the implementation card (Card 2). Tests fail in the intermediate commit; this is expected and accepted. Other batches that touch tests follow the same order.
- **Rationale:** Locks the helper contract before implementation. Matches the discussion's TDD ordering decision.
- **Applies to:** all batches that include test changes alongside source changes (1, 2, 3).

### Decision: New helper signatures are keyword-only after positional `(container, slug)`

- **Decision:** Both `resolve_active_worktree` and `resolve_active_hub` use `(container, slug, *, cfg, git_root) -> Path`. Callers must pass `cfg` and `git_root` by name.
- **Rationale:** Symmetric with `_inplace.is_inplace(active_data, git_root, cfg)`. Forbids positional misuse and signals the API change at every call site.
- **Applies to:** all batches.

### Decision: `resolve_active_hub` resolves `hub_relative_path` two-tier (caller's cfg as default, worktree-root stub as override)

- **Decision:** The helper resolves `hub_relative_path` in this order: (1) `cfg.get("hub_relative_path", ".")` from the caller's cfg as the default, (2) worktree-root stub at `<wt>/.millhouse/config.local.yaml` overrides when present and declaring `hub_relative_path:`.
- **Rationale:** Two consumer profiles need both sources. (a) Cross-worktree consumers (cleanup, status) that have no useful cfg about the target rely on mill-spawn's bootstrap stub at the worktree root. (b) Same-cwd consumers (`_review_common.resolve_path` for in-place M2+sub) already have authoritative cfg from the hub but need a path to the hub from the worktree root — and mill-claim does not bootstrap a stub at the worktree root for sub-dir hub configs. Single-source designs break one or the other; two-tier supports both.
- **Applies to:** Batch 1 (the helper) and any future caller of `resolve_active_hub`.

### Decision: Test fixture style — `tempfile` + mocked subprocess; no real git

- **Decision:** Unit tests use `tempfile.TemporaryDirectory()` for the filesystem layout and `unittest.mock.patch("_subprocess_util.run", ...)` to stub `git rev-parse --abbrev-ref HEAD` for `_inplace.is_inplace`.
- **Rationale:** Matches the existing `test-paths.py` and `test-inplace.py` style. Fast, leaks no state.
- **Applies to:** Batches 1 and 2.

### Decision: Helper raises propagate; callers do not swallow

- **Decision:** Both `_active.ActiveError` (from `_active.read_all`) and the new `ActiveWorktreeNotFound` / `ActiveWorktreeSlugMismatch` propagate through the helpers unchanged. `_review_common.resolve_path` and `millpy-abandon.py` do not catch them — they bubble up to the CLI which prints and exits.
- **Rationale:** Marker-absence is a hard failure mode; callers cannot meaningfully recover and silent fallthrough hides bugs.
- **Applies to:** Batches 1, 2, 3.

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/millpy-abandon.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/skills/mill-claim/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/unit_tests/test-abandon.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-review-common.py`
