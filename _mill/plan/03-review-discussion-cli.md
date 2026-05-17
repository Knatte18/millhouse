# Batch: review-discussion-cli

```yaml
task: "61 (A) -- Review pipeline fixes"
batch: review-discussion-cli
number: 3
cards: 1
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Single CLI path-resolution fix in `millpy-review-discussion.py`. Today the CLI uses `project_root = Path.cwd()` and `mill_dir = project_root / ".millhouse"`, which works in the common `hub_relative_path: "."` layout but writes to `<git_root>/_mill/reviews/` instead of `<hub_path>/_mill/reviews/` in a sub-dir hub layout (#306). The fix mirrors mill-start's convention: resolve the hub directory via `_paths.resolve_hub_path()` and the project root via `_paths.resolve_active_hub` (or the simpler `_paths.resolve_git_root()` plus `cfg`-aware fallback). The backend itself is unchanged -- `_review_common.resolve_path` already routes through `_paths.resolve_active_hub` correctly; the bug is in the CLI's path arguments shipped down to `worktree_snapshot_guard` and `read_constraints_md`.

External interface: the CLI's argv (`--max-rounds`) and stdout JSON shape are unchanged; only the resolved internal paths change. The change is observable only in sub-dir-hub layouts.

## Cards

### Card 8: millpy-review-discussion path-resolution fix

- **Context:**
  - `_mill/discussion.md`
  - `_mill/plan/00-overview.md`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/scripts/millpy-review-discussion.py`'s `main()`, replace the current path-resolution block:
    ```python
    project_root = Path.cwd()
    mill_dir = project_root / ".millhouse"
    wiki_root = resolve_wiki_path(project_root)
    cfg = load_config(project_root, mill_dir)
    ```
    with a layout-aware block that mirrors mill-start's convention. Concretely:
    ```python
    from _paths import resolve_git_root, resolve_hub_path, resolve_wiki_path
    git_root = resolve_git_root()
    hub_dir = resolve_hub_path()
    mill_dir = hub_dir / ".millhouse"
    wiki_root = resolve_wiki_path(git_root)
    cfg = load_config(hub_dir, mill_dir)
    project_root = hub_dir
    ```
  - The downstream `run(cfg, slug, mill_dir, project_root, wiki_root, ...)` call receives `project_root = hub_dir` so `worktree_snapshot_guard(project_root, ...)` and `read_constraints_md(project_root)` both operate on the hub. The backend's `resolve_path` continues to compute `reviews_dir` via `_paths.resolve_active_hub` (unchanged); the new `project_root` only affects guard scope and constraints reads.
  - Preserve the existing `_reviewers.load(project_root)` call -- it now correctly looks for `agents.yaml` / `reviewers.yaml` at the hub.
  - Confirm by reading `_paths.py` that `resolve_hub_path()` is a public function (it is: returns `Path.cwd().resolve()` and validates against the wiki-cwd check; mill-start uses it). If `resolve_hub_path` is unavailable, fall back to `Path.cwd()` and document the divergence in the commit message; do NOT add a new function in this batch.
  - Do NOT touch `_review_discussion.run` -- the backend is correct.
  - No unit test in this batch: the bug is observable only in a sub-dir-hub layout and the existing integration-test harness lacks a sub-dir-hub fixture. Add only if a future task introduces the fixture.
- **Commit:** `fix(review-discussion-cli): resolve project_root and mill_dir via hub_path (#306)`

## Batch Tests

The batch verify is `python plugins/mill/unit_tests/run-all.py` to confirm the path-resolution change does not break existing unit tests that exercise `millpy-review-discussion.py` via direct import or via `_review_discussion.run`. The bug-fix itself is not directly unit-testable without a sub-dir-hub fixture (out of scope).
