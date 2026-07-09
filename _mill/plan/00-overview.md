# Plan: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing

```yaml
task: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing
slug: codeguide-scope-resolution-fixes
approved: false
started: 20260709-131637
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: resolve-scope-core
    file: 01-resolve-scope-core.md
    depends-on: []
    verify: PYTHONPATH= "$MILL_PYTHON" plugins/codeguide/unit_tests/test-resolve-scope.py
  - number: 2
    name: parent-branch-helper
    file: 02-parent-branch-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
  - number: 3
    name: wire-up-callers
    file: 03-wire-up-callers.md
    depends-on: [1, 2]
    verify: null
```

## Shared Decisions

### Decision: resolve_scope.py stays mill-agnostic

- **Decision:** `resolve_scope.py` gains a generic `--parent <ref>` override flag but never imports mill internals (`_mill`, `_paths`, `_marker`) and never reads `_mill/status.md` directly. All mill-specific detection lives in the calling skill.
- **Rationale:** `plugins/codeguide/scripts/resolve.py` already has zero mill coupling — codeguide must remain usable in non-mill repos. Coupling `resolve_scope.py` to mill's status format would break that boundary.
- **Applies to:** all batches — batch 1 must not add any mill import to `resolve_scope.py`; batch 3 is where mill-specific detection (status.md lookup) actually lives.

### Decision: literal `..HEAD` suffix stripping only, never a generic `..`-split

- **Decision:** When a single token ends with the exact literal suffix `..HEAD`, strip that suffix and verify the remainder resolves as a ref. Any other token containing `..` (e.g. a genuine `<ref>..<other-ref>` range) falls through unchanged to the existing dispatch chain — it is NOT split generically at the last `..`.
- **Rationale:** only `..HEAD` is ever produced by real callers (mill-merge-in's checkpoint-branch range); a generic split would silently drop the right-hand endpoint of any other `..`-range, which is worse than not stripping at all.
- **Applies to:** batch 1 (Card 1).

### Decision: unresolvable `--parent` falls back to git-native detection, never a silent empty scope

- **Decision:** When `--parent <ref>` is supplied but does not resolve via `git rev-parse --verify --quiet <ref>^{commit}`, `_no_arg_scope()` falls back to `_detect_base_branch()`'s existing `origin/HEAD` → `origin/main` → `origin/master` chain exactly as if `--parent` were absent.
- **Rationale:** a `parent:` value that no longer resolves locally (e.g. a deleted parent task branch) must not reproduce the silent-empty-scope failure class this task exists to fix. `resolve_scope.py` already has a graceful-degradation philosophy (no remote at all → empty scope, not an error) and this preserves that floor.
- **Applies to:** batch 1 (Card 2).

### Decision: single-token ref/path ambiguity resolves in favor of "is this a ref"

- **Decision:** A single-token explicit-path call whose string also happens to resolve as a branch/tag name (e.g. a repo-root file literally named `main`) routes to `_head_rev_scope()`, not `_explicit_scope()`. This is a deliberately accepted edge case, not a defect.
- **Rationale:** matches git's own CLI precedent (`git show <token>` prefers ref resolution over path interpretation for an unqualified single token); no caller in this repo passes single-token paths that collide with ref names today.
- **Applies to:** batch 1 (Card 1, Card 3 — the test scenario documents this precedence, it does not attempt to change it).

## All Files Touched

- `plugins/codeguide/scripts/resolve_scope.py`
- `plugins/codeguide/skills/codeguide-update/SKILL.md`
- `plugins/codeguide/unit_tests/test-resolve-scope.py`
- `plugins/mill/scripts/_parent_branch.py`
- `plugins/mill/skills/git-commit/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/unit_tests/test-parent-branch.py`
