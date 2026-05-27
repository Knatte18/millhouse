# Plan: Sub-project repo (hub_relative_path) support

```yaml
task: "Sub-project repo (hub_relative_path) support"
slug: "hub-relative-path-support"
approved: false
started: "20260527-090728"
parent: "main"
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
    name: helper-api
    file: 01-helper-api.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: config-callsite-fixes
    file: 02-config-callsite-fixes.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: review-paths-threading
    file: 03-review-paths-threading.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 4
    name: skill-md-docs
    file: 04-skill-md-docs.md
    depends-on: [1]
    verify: null
  - number: 5
    name: integration-test
    file: 05-integration-test.md
    depends-on: [2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-hub-relative-path.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: hub_root naming throughout

- **Decision:** The first positional arg of `_config.load_config`, `_review_common.load_config`, and `_paths.resolve_mill_config_path` is named `hub_root`. All call sites pass `_paths.resolve_hub_path()` (the cwd-resolved hub directory) as this value, never `_paths.resolve_git_root()`. Docstrings, signature annotations, error messages, and SKILL.md prose all use the term `hub_root`.
- **Rationale:** `repo_root` is ambiguous in a project where git_root, wiki_path, and hub_root all exist as distinct conceptual paths. `hub_root` aligns with `_paths.resolve_hub_path()` and the layering model documented in discussion.md.
- **Applies to:** all batches.

### Decision: fix at callsite, not at API

- **Decision:** No defensive guards or kw-only enforcement is added to `_config.load_config` or `_review_common.load_config`. The signatures stay positional; the helpers do not validate that the path supplied is in fact a hub root. Misuse is fixed at the call site, never at the helper.
- **Rationale:** Defensive APIs encourage sloppy callers. Per the feedback-memory `fix-misuse-at-callsite-not-api`, internal Python helpers are not a system boundary. The rename + correct-callsite work is the entire fix surface.
- **Applies to:** batches 1, 2, 3.

### Decision: config layering — template is base, hub overlay is optional

- **Decision:** `_config.load_config` no longer raises `FileNotFoundError` when `<hub_root>/mill-config.yaml` is absent. When the overlay file is missing, the function skips the hub-overlay merge step and continues with template + local-stub layers. Template-only output is a valid configuration.
- **Rationale:** The plugin's bundled `templates/mill-config.yaml` is always present and supplies every required key. Hub overlay is optional by design. Issue #369's "fail loudly when args swapped" framing is rejected; the correct fix surface is the call sites and the documented signature, not a runtime presence check.
- **Applies to:** batch 1.

### Decision: ASCII-only stdout

- **Decision:** Any `print()` or `_log()` introduced or modified in this task uses ASCII-only output. Replace any em-dash (`—`) with ` -- ` and any arrow (`->`) with the same form. Existing non-ASCII chars are left as-is unless the line is being touched.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII characters (CLAUDE.md `## Conventions`).
- **Applies to:** all batches.

### Decision: All path resolution via `_paths.py`

- **Decision:** No inline path arithmetic in fixed callsites. Use `_paths.resolve_hub_path()`, `_paths.resolve_git_root()`, `_paths.resolve_container_path()`, `_paths.resolve_active_hub()` as appropriate. Imports of these helpers go through the existing `from _paths import ...` line in each affected script.
- **Rationale:** CLAUDE.md `## Path invariants` mandates this. Keeps hub_relative_path semantics encapsulated in one module.
- **Applies to:** batches 2, 3, 5.

### Decision: TDD for new helper behaviour

- **Decision:** For `_config.load_config` raise-removal, `resolve_ref_paths` git_root fallback, and `resolve_existing_paths` git_root fallback, unit tests are written first within the same card as the production code change. The implementer writes the failing test, confirms it fails for the expected reason, then makes the production-code change and confirms it passes. Mechanical callsite fixes (batches 2, 3) are not TDD candidates — they are no-op refactors covered by the integration test in batch 5.
- **Rationale:** Three real behaviour changes warrant TDD; mass refactors do not (the existing test suite covers regression).
- **Applies to:** batch 1.

## All Files Touched

_Full union of every `Creates:` / `Edits:` across every batch, sorted
alphabetically. mill-go reads this to warn if two parallel batches
touch the same file — a sign of a misplaced dependency._

- `plugins/mill/integration_tests/test-hub-relative-path.py`
- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-claude-sub.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-color.py`
- `plugins/mill/scripts/millpy-inspect.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-status.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/scripts/millpy-validate-plan.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-review-common.py`
