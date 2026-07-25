# Plan: mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps

```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
slug: mill-go-dispatch-path-gaps
approved: true
started: "20260725-134500"
parent: hanf/linux-port-more
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: fail-fast-guard
    file: 01-fail-fast-guard.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py"
  - number: 2
    name: on-disk-first-resolution
    file: 02-on-disk-first-resolution.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-marker.py test-review-plan-flow.py"
  - number: 3
    name: paths-skip-slug-validation
    file: 03-paths-skip-slug-validation.md
    depends-on: [2]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths.py test-paths-sanitize.py test-review-common.py"
  - number: 4
    name: project-root-rebinding-implement-side
    file: 04-project-root-rebinding-implement-side.md
    depends-on: [1, 3]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-millpy-fix.py test-millpy-merge-in-subagent.py test-merge-in-subagent.py test-paths.py"
  - number: 5
    name: project-root-rebinding-review-side
    file: 05-project-root-rebinding-review-side.md
    depends-on: [3]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-plan-flow.py test-review-plan-finalize-round.py test-review-discussion-flow.py test-paths.py"
  - number: 6
    name: mill-go-resume-fix
    file: 06-mill-go-resume-fix.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py"
```

## Shared Decisions

### Decision: dispatch mode resolution via _agent_dispatch.resolve_dispatch_mode

- **Decision:** Every check that needs to know whether the hub is configured for agent-mode dispatch calls `_agent_dispatch.resolve_dispatch_mode(cfg)` (returns `"subprocess"`, `"psmux"`, or `"agent"`, defaulting to `"agent"` when `llm.claude.dispatch` is unset). Never read `cfg["llm"]["claude"]["dispatch"]` inline.
- **Rationale:** This is the existing, single source of truth used throughout `mill-go`/`mill-start`/`mill-plan`'s Agent-mode dispatch pattern (see `mill-go/SKILL.md` "## Agent-mode dispatch"). `_agent_dispatch` is already imported in `millpy-implement.py`.
- **Applies to:** `fail-fast-guard`.

### Decision: on-disk-first fast paths are additive, never a correctness regression

- **Decision:** Every new "try the cheap on-disk path first" fast path in this plan (`find_active_slug`, `load_task_title`, `resolve_active_worktree`'s `skip_slug_validation`) falls through to the existing, slower, already-correct path on any ambiguity, missing data, or unexpected shape. No fast path is ever allowed to raise a NEW error class the existing callers don't already handle — it can only skip work the existing path would otherwise have done.
- **Rationale:** These are latency fixes for hot dispatch paths, not behavior changes. Preserving today's correctness envelope exactly (just skipping the slow branch in the common case) is what makes each fast path safe to land without re-auditing every caller's error handling.
- **Applies to:** `on-disk-first-resolution`, `paths-skip-slug-validation`.

### Decision: project_root/hub_dir rebind happens AFTER slug resolution, not at the original binding site

- **Decision:** In every one of the 6 files `project-root-rebinding-implement-side`/`project-root-rebinding-review-side` touch, `slug` is resolved (via `_marker.slug_from_branch` or `find_active_slug`) using the file's **existing, unmodified** slug-resolution call — this plan does not change how any file resolves `slug`. The corrected `project_root`/`hub_dir` binding (via `_paths.resolve_active_hub(..., skip_slug_validation=True)`) is inserted as a **second, later** assignment, immediately after the existing slug-resolution try/except block, superseding the original `resolve_hub_path()`-derived value for every use that follows it in the file.
- **Rationale:** `project_root`/`hub_dir` is bound near the top of each file's `main()`, before `cfg` and `slug` are available — `resolve_active_hub` requires both. A literal "fix it at its original definition site" is impossible without either re-ordering config loading (out of scope, higher risk) or resolving slug before cfg exists (impossible — `find_active_slug`/`slug_from_branch` need `cfg` for `spawn.branch_prefix` and, in the review CLIs, the on-disk `_mill/*.active` glob is scoped by the value passed as `hub_root`, which some of these calls receive as the *original* `project_root`/`hub_dir` — changing that argument is a separate, higher-risk change this plan explicitly does not make; see the batch files' per-card notes). Three early consumers of the original value are therefore left untouched by design: the `.millhouse/config.local.yaml` read used to bootstrap `cfg`; each file's own slug-resolution call; and, in `millpy-implement.py`/`millpy-fix.py` specifically, the `git config --global --get user.name`/`user.email` subprocess calls (`cwd=project_root`) that run before slug resolution — harmless in practice since `--global` config reads are cwd-independent, but included here for completeness since they do technically read the original, not-yet-corrected value. Everything computed **after** the rebind — `status_path`, `plan_base`, snapshot paths, every other git subprocess `cwd=`, the `PROJECT_ROOT` template token, and `briefs_dir` — uses the corrected value.
- **Applies to:** `project-root-rebinding-implement-side`, `project-root-rebinding-review-side`.

### Decision: cfg-loading's use of the original (possibly escaped) project_root is a pre-existing, out-of-scope limitation

- **Decision:** This plan does not change how any file bootstraps `cfg` (i.e. `mill_dir = project_root / ".millhouse"` followed by `_review_common.load_config(git_root, mill_dir)`, using the ORIGINAL, not-yet-corrected `project_root`). If `resolve_hub_path()`'s fallback fires, `cfg` may be loaded from the wrong worktree's `config.local.yaml` overlay — a pre-existing bug this plan does not fix.
- **Rationale:** Fixing this would require resolving the active worktree before `cfg` exists, which is what `resolve_active_hub` itself needs `cfg` for (`hub_relative_path` resolution) — a deeper circular dependency than this task's four reported issue clusters call for. None of #672/#665/#683/#693/#691/#675/#680 report a wrong-config-overlay symptom; only `briefs_dir` (and, by the same mechanism, `status_path`/`plan_base`/git `cwd=`/the `PROJECT_ROOT` token) were reported and are fixed by this plan's rebind-after-slug approach.
- **Applies to:** `project-root-rebinding-implement-side`, `project-root-rebinding-review-side`.

### Decision: project-root-rebinding split by file family, not by symptom

- **Decision:** The `project_root`/`hub_dir` rebind for #675 is split into two batches — `project-root-rebinding-implement-side` (`millpy-implement.py`, `millpy-fix.py`, `millpy-merge-in-subagent.py`) and `project-root-rebinding-review-side` (`millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py`) — purely because the combined 6-file batch exceeded `pipeline.max_batch_context_tokens` (~123k vs. the 120k cap) when first drafted as one batch. The two batches touch entirely disjoint files and have no ordering dependency on each other; only `project-root-rebinding-implement-side` depends on `fail-fast-guard` (shared file: `millpy-implement.py`).
- **Rationale:** A structural split (not a mechanical `batch-oversized` auto-fix, per the validator's fix table) was required. Splitting along the existing implementer/fixer vs. review-CLI file-family boundary keeps each batch's cards coherent (the implement-side batch shares the "dispatches an implementer/fixer session" shape; the review-side batch shares the "dispatches a reviewer" shape) rather than an arbitrary file-count split.
- **Applies to:** `project-root-rebinding-implement-side`, `project-root-rebinding-review-side`.

## All Files Touched

- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
