# Plan: 57 (A) -- Move config.yaml and agents.yaml from wiki to hub worktree

```yaml
task: 57 (A) -- Move config.yaml and agents.yaml from wiki to hub worktree
slug: config-move-to-hub
approved: true
started: 20260516-161442
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-paths.py && python plugins/mill/unit_tests/test-autonomous.py
  - number: 2
    name: loaders-refactor
    file: 02-loaders-refactor.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/test-config.py && python plugins/mill/unit_tests/test-review-common.py && python plugins/mill/unit_tests/test-reviewers.py
  - number: 3
    name: setup-migration
    file: 03-setup-migration.md
    depends-on: [1]
    verify: python plugins/mill/integration_tests/test-migration.py
  - number: 4
    name: cleanup-deletions
    file: 04-cleanup-deletions.md
    depends-on: [2, 3]
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 5
    name: wiki-helpers-post-migration
    file: 05-wiki-helpers-post-migration.md
    depends-on: [1, 2]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: plugin template path resolution

- **Decision:** Plugin templates (`mill-config.yaml`, `mill-agents.yaml`) are loaded by resolving `${CLAUDE_PLUGIN_ROOT}/templates/<name>` when the env var is set, otherwise falling back to `Path(__file__).resolve().parent.parent / "templates" / <name>` (i.e. the source-tree path relative to the script file). The fallback exists for unit tests that run from the source checkout without `CLAUDE_PLUGIN_ROOT` set. Implement this as a helper inside `_config.py` (single place) and reuse it from `_review_common.py` and `_reviewers.py`.
- **Rationale:** Matches the CLAUDE.md cache-form invariant for production while letting `python plugins/mill/unit_tests/test-config.py` work without env shimming. The single-helper rule prevents three near-identical implementations drifting apart.
- **Applies to:** all batches that touch `_config.py`, `_review_common.py`, `_reviewers.py` (batches 2, 3).

### Decision: deep-merge semantics

- **Decision:** Recursive merge of dicts; lists replaced wholesale at the level they appear. Matches the existing `_config.deep_merge` / `_review_common._deep_merge`. The new overlay logic reuses `_config.deep_merge` instead of forking a second helper. `_review_common._deep_merge` is retained as an alias (or replaced by `from _config import deep_merge`) to keep the surface stable.
- **Rationale:** Already documented in discussion. Lists like `verify.skip_known_broken` are operator-owned; partial-merge of lists is unpredictable.
- **Applies to:** batches 2 (both load_config rewrites use it) and 2 (`_reviewers.load` two-layer overlay uses it).

### Decision: ASCII-only stdout/stderr in all warning/error text

- **Decision:** Every `print()` / `_log()` / stderr string emitted by new code uses ASCII. Em-dash -> ` -- `; right-arrow -> ` -> `. Applies to unknown-key warnings, fallback warnings, migration script output, mill-setup Phase 3.0b log lines.
- **Rationale:** CLAUDE.md hard rule. Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **Applies to:** all batches.

### Decision: warn-only unknown-key validation

- **Decision:** Unknown keys produce a stderr line in the form `[config] unknown key: a.b.c (in <source-label>)` and load proceeds. The walker is purely structural -- any key path present in `actual` but not in `template` is "unknown"; leaf value types are not checked. Lists are treated as leaves (no descent). The shared walker lives in `_config.py` and is imported by `_review_common.py` and (in a per-agent-shape adapted form) by `_reviewers.py`.
- **Rationale:** Discussion §"Unknown-key validation: warn, don't fail". Failing-fast on rename breaks live systems.
- **Applies to:** batches 2 (all three loaders).

### Decision: env-var override registry as a module-level constant in `_config.py`

- **Decision:** `_config.ENV_REGISTRY: dict[str, tuple[str, ...]]` is the single source of truth. `_review_common.load_config` imports it. The six entries match the discussion's named registry exactly. Empty-string env value is treated as unset (no override applied).
- **Rationale:** Single registry prevents drift between the lenient and strict load paths. Tuple key paths (vs dotted strings) avoid ambiguity when a key segment legitimately contains a dot.
- **Applies to:** batches 2.

### Decision: card-level commit messages follow conventional-commits

- **Decision:** Every card's `Commit:` field uses `<type>(<scope>): <summary>` lowercase, present tense, < 72 char total. Matches existing repo convention (`feat(spawn): ...`, `refactor: ...`, `chore: ...`).
- **Rationale:** Consistency with surrounding history; review-pipeline parsers can match scopes.
- **Applies to:** all batches.

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Deletes:` across every batch, sorted
alphabetically. mill-go reads this to warn if two parallel batches
touch the same file -- a sign of a misplaced dependency._

- `CLAUDE.md`
- `plugins/mill/integration_tests/test-migration.py`
- `plugins/mill/scripts/_autonomous.py`
- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_machine.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/scripts/_setup.py`
- `plugins/mill/scripts/_wiki.py`
- `plugins/mill/scripts/millpy-abandon.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-color.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-inspect.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-migrate-config.py`
- `plugins/mill/scripts/millpy-migrate-layout.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-status.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/scripts/millpy-validate-plan.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/templates/config.machine.yaml`
- `plugins/mill/templates/mill-agents.yaml`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/reviewers.yaml`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-autonomous.py`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-machine.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-reviewers.py`
- `plugins/mill/unit_tests/test-wiki.py`
