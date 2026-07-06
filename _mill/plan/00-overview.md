# Plan: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
slug: nested-layout-fixes
approved: true
started: 20260706-173348
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: scope-violation-rebase
    file: 01-scope-violation-rebase.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py test-implementer-common.py
  - number: 2
    name: brief-path-fix
    file: 02-brief-path-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-code-flow.py
  - number: 3
    name: verify-cwd-foundation
    file: 03-verify-cwd-foundation.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-dag.py
  - number: 4
    name: implementer-verify-cwd
    file: 04-implementer-verify-cwd.md
    depends-on: [1, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py
  - number: 5
    name: fixer-verify-cwd
    file: 05-fixer-verify-cwd.md
    depends-on: [3, 4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py test-fix-finalize.py
  - number: 6
    name: plan-validate-verify-cwd
    file: 06-plan-validate-verify-cwd.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 7
    name: merge-in-verify-cwd
    file: 07-merge-in-verify-cwd.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
  - number: 8
    name: mill-plan-authoring-update
    file: 08-mill-plan-authoring-update.md
    depends-on: [3]
    verify: null
```

## Shared Decisions

### Decision: nested-hub-layout terminology

- **Decision:** "hub_root" (also "project_root" in existing code) is the mill project root resolved via `_paths.resolve_hub_path()`. "git_root" is the git repository toplevel resolved via `_paths.resolve_git_root()`. A "nested hub layout" is any repo where `hub_root != git_root` (the hub lives in a subdirectory of the git root). "Flat layout" is the common case where they are equal.
- **Rationale:** These terms are used identically across all eight batches; establishing them once avoids each batch re-deriving the vocabulary.
- **Applies to:** all batches.

### Decision: flat-layout behavior must be byte-identical

- **Decision:** Every fix in this plan must be a no-op for flat-layout repos (`hub_root == git_root`). No existing test assertion for a flat-layout fixture may change its expected value; new nested-layout test cases are additive only.
- **Rationale:** This task exists because five bugs shipped without breaking any existing (flat-layout-only) test. The corrective principle is the same one that would have caught them: never let a nested-layout fix alter flat-layout output.
- **Applies to:** all batches.

### Decision: verify `cwd` field schema

- **Decision:** A plan's `verify:` frontmatter value (per-batch or module-wide/overview) is either a plain string (today's format, implicitly `cwd: git_root`) or a `{cwd: hub|git_root, command: <string>}` mapping. `_plan_dag.parse_verify_field(frontmatter, hub_root, git_root) -> tuple[str | None, Path | None]` (introduced in batch 3) is the single normalizer every other batch's `verify` read site must route through — never re-implement the string-vs-mapping branch elsewhere. Absent/`None`/whitespace-only `verify` normalizes to `(None, None)`. An unrecognized `cwd` value or a mapping missing `command` raises `ValueError` (fail loud — malformed plan files are authoring bugs that must be visible immediately, never silently coerced).
- **Rationale:** Established in `_mill/discussion.md`'s "Verify-cwd explicit field (#604)" decision. One normalizer, reused everywhere, is what keeps the six call sites (implementer, fixer x2, baseline, merge-in, plan-validate) from drifting into inconsistent parsing.
- **Applies to:** batches 3, 4, 5, 6, 7, 8.

## All Files Touched

- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_plan_dag.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_verify_baseline.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/plan-batch.md`
- `plugins/mill/templates/plan-overview.md`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-fix-finalize.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-plan-dag.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
