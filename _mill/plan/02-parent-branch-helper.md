# Batch: parent-branch-helper

```yaml
task: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing
batch: parent-branch-helper
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Adds `resolve_for_codeguide(status_path) -> str | None` to `plugins/mill/scripts/_parent_branch.py` — a non-interactive, exception-swallowing wrapper around the existing `resolve()` that mill's `git-commit` skill (wired up in batch 3) will use to learn a task's declared parent branch without ever raising or blocking a commit. Independent of batch 1 (no shared files, no import relationship) — both batches are consumed together only by batch 3.

## Cards

### Card 5: Add `resolve_for_codeguide` helper

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a new function `resolve_for_codeguide(status_path: Path) -> str | None` at the end of the file, after `resolve()`. Signature takes `status_path` directly (mirrors `resolve()`'s existing signature — never a `hub_root` the function would resolve internally). Body: call `resolve(status_path, interactive=False)` inside a `try` block; on success return the branch name string. On `ParentBranchError`, return `None` (never re-raise, never prompt). Add a short docstring stating this is for callers (e.g. `git-commit`) that must degrade silently rather than block a commit over a missing/unreadable parent.
  - Do not modify `resolve()`, `_read_parent_from_status()`, or `ParentBranchError` — this card is additive only.
- **Commit:** `feat(mill): add _parent_branch.resolve_for_codeguide non-interactive wrapper`

### Card 6: Extend test-parent-branch.py with resolve_for_codeguide scenarios

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-parent-branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Update the `from _parent_branch import ParentBranchError, resolve` line to also import `resolve_for_codeguide`.
  - Add scenario: write a `status.md` with a `parent: main` row (reuse the existing fenced-yaml pattern already in the file) and assert `resolve_for_codeguide(sp) == "main"`.
  - Add scenario: point `resolve_for_codeguide` at a `status.md` path that does not exist on disk (e.g. `Path(tmp) / "nonexistent-status.md"`) and assert it returns `None` without raising.
  - Add scenario: write a `status.md` with a fenced yaml block that has no `parent:` row (reuse the file's existing "missing parent" fixture, already present in the file for the `ParentBranchError` scenario) and assert `resolve_for_codeguide(sp)` returns `None` without raising — this exercises the same missing-parent fixture that currently proves `resolve()` raises `ParentBranchError`, showing the wrapper catches it.
  - Keep both existing scenarios (`resolve` reads parent; `resolve` raises `ParentBranchError` on missing parent) unchanged.
- **Commit:** `test(mill): cover _parent_branch.resolve_for_codeguide`

## Batch Tests

`verify:` runs `test-parent-branch.py` directly (5 scenarios after this batch: 2 existing + 3 new) — the complete test surface for this batch's single-file change.
