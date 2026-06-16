# Plan: Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup

```yaml
task: "Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup"
slug: mill-external-repo-infra
approved: true
started: "20260616-123625"
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches._

```yaml
batches:
  - number: 1
    name: path-resolution-scripts
    file: 01-path-resolution-scripts.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths.py test-review-discussion-flow.py test-review-plan-flow.py
  - number: 2
    name: cleanliness-drift-guard
    file: 02-cleanliness-drift-guard.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py
  - number: 3
    name: orchestrator-skills
    file: 03-orchestrator-skills.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-finalize-dispatch.py test-finalize-cleanup.py
```

## Shared Decisions

### Decision: hub-root is the single anchor for every `_mill/` path

- **Decision:** All `_mill/` task-state resolution anchors on the mill project
  (hub) root via `_paths.resolve_hub_path()` (in-process scripts and SKILL Entry)
  or `_paths.resolve_active_hub()` (mill-go, which already uses it). Never anchor
  on `_paths.resolve_git_root()` or raw `Path.cwd()`. `_paths.resolve_task_path`
  stays a plain `worktree_root / cfg_relative_path` join (with its existing
  `_mill/`→`task/` compat fallback) — callers feed it the hub root.
- **Rationale:** In a nested layout (mill project below the git toplevel) the git
  root holds no `_mill/`; `resolve_hub_path()` already resolves the nested hub via
  the mill-spawn root stub (`hub_relative_path`). The bugs (#484/#490/#491) are
  callsites that bypass this resolver.
- **Applies to:** all batches.

### Decision: never auto-commit out-of-scope drift; revert it

- **Decision:** Formatter/lint drift to files outside the task's scope
  (`task_dir` subtree ∪ the task's parent-diff "owned" set) is reverted, not
  committed. Writing formatters in the `{lang}-build` templates are scoped to
  changed files; whole-project build/test/read-only-lint stay whole-project.
- **Rationale:** #493-A — the cleanliness gate's dirty-tree block tempts a
  wholesale `git add -A` of drift. Reverting out-of-scope drift removes the temptation.
- **Applies to:** cleanliness-drift-guard, orchestrator-skills.

### Decision: stacked tasks open a clean PR to their parent

- **Decision:** mill-finalize PR mode activates on `require_pr_to_base` alone
  (drop the `parent_branch == base_branch` clause); the PR targets
  `parent_branch`. The existing `_finalize_cleanup.base_tracks_task_dir`
  restore-vs-remove logic is reused unchanged.
- **Rationale:** #493-B — the only thing blocking stacked tasks from the existing
  clean-PR cleanup is the `parent == base` gate.
- **Applies to:** orchestrator-skills.

### Decision: tests are unit-level, tempfile + real git, no LLM

- **Decision:** Every test fixture uses tempfile dirs + real `git`; no real LLM or
  review dispatch. Each nested-layout assertion is paired with a flat-layout
  (hub == git root) regression assertion.
- **Rationale:** Matches the repo's `unit_tests/` conventions (in-memory/tempfile
  fixtures, no real git/LLM beyond local `git`).
- **Applies to:** all batches.

## All Files Touched

- `plugins/csharp/skills/csharp-build/SKILL.md`
- `plugins/golang/skills/golang-build/SKILL.md`
- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/git-commit/SKILL.md`
- `plugins/mill/skills/git-pr/SKILL.md`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-mill-finalize-dispatch.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/python/skills/python-build/SKILL.md`
