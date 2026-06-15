# Plan: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling

```yaml
task: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling
slug: review-plan-and-ref-paths
approved: true
started: 20260615-113046
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: ref-path-resolution
    file: 01-ref-path-resolution.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
  - number: 2
    name: validator-git-root-threading
    file: 02-validator-git-root-threading.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
  - number: 3
    name: review-plan-cli
    file: 03-review-plan-cli.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py
  - number: 4
    name: skill-doc-update
    file: 04-skill-doc-update.md
    depends-on: [3]
    verify: null
```

## Shared Decisions

### Decision: three-roots resolution model

- **Decision:** Three filesystem bases are kept distinct: **hub** (`git_root/hub_relative_path`, where `_mill/` lives) for `_mill/` paths, resolved via `resolve_path(...)`; **git_root** (repo top) for source `root:`/raw refs → `git_root/root/raw`; **cwd** is incidental and must never be the base for source-ref resolution.
- **Rationale:** Both #466 and #471 are symptoms of resolving source refs against `cwd`. `root:` is repo-relative by definition, so `git_root/root/raw` is correct regardless of where cwd sits. See discussion.md "three-roots model".
- **Applies to:** all batches

### Decision: git_root primary, project_root fallback

- **Decision:** When `root` is set, source-ref resolution tries `git_root/root/raw` FIRST, then falls back to `project_root/root/raw`, then bare/`git_root/raw`. `project_root/root/raw` is retained (not deleted) as a fallback because `git_root` may be `None` in unit contexts and some non-`root` layouts legitimately resolve against `project_root`.
- **Rationale:** The current additive fallback only "works" because the doubled `project_root/root/root/raw` candidate happens not to exist on disk — fragile. Making `git_root/root/raw` primary removes that dependence.
- **Applies to:** ref-path-resolution, validator-git-root-threading

### Decision: do not touch resolve_path or hub-base machinery

- **Decision:** `resolve_path` (`_review_common.py:319`) and the `_paths.py` hub-base helpers stay as-is. The Jun-13 revert (`88c08793`) is correct — `_mill/` lives at the hub subfolder, NOT the worktree root. Do not re-apply `b62ca5e7`. `plan_dir` continues to resolve via `resolve_path` (it is `--slug`-from-main safe).
- **Rationale:** The #466 slug-concat symptom is already gone; the residual is base-consistency for source refs, fixed by threading `git_root`+`root` into the validator — not by re-resolving `plan_dir`.
- **Applies to:** all batches

### Decision: Python verify-command shape

- **Decision:** Every batch `verify:` (non-null) starts with `PYTHONPATH= ` (empty value, single space) and runs the named test file via `run-all.py --only`. This is a Python/mill project so `verify-not-isolated` enforces the prefix.
- **Rationale:** Resets `PYTHONPATH` so the test subprocess loads worktree modules, not the stale cache scripts dir.
- **Applies to:** all batches with a runnable surface

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
