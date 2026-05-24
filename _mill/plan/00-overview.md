# Plan: Adopt V3 wiki module in V2 scripts

```yaml
task: Adopt V3 wiki module in V2 scripts
slug: wiki-v3-adoption
approved: false
started: 20260524-170303
parent: main
root: ""
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: wiki-module-refactor
    file: 01-wiki-module-refactor.md
    depends-on: []
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-sync.py && uv run --project plugins/mill python plugins/mill/integration_tests/test-wiki-e2e.py && uv run --project plugins/mill python plugins/mill/integration_tests/test-wiki-daemon-tinydb.py && uv run --project plugins/mill python plugins/mill/integration_tests/test-wiki-concurrency.py"
  - number: 2
    name: migration-script
    file: 02-migration-script.md
    depends-on: [1]
    verify: uv run --project plugins/mill python plugins/mill/integration_tests/test-wiki-migrate.py
  - number: 3
    name: v2-deletion-and-port
    file: 03-v2-deletion-and-port.md
    depends-on: [1]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-sync.py && uv run --project plugins/mill python plugins/mill/integration_tests/test-wiki-e2e.py"
```

## Shared Decisions

### Decision: wiki-api-import-form

- **Decision:** Call sites import the V3 wiki API via `from wiki import _client as wiki` and then call `wiki.upsert_task(...)`, `wiki.list_tasks_brief()`, etc. The constant `wiki.LOCKED_FOLD_PHASES` comes from `wiki/__init__.py` and is re-exported through `_client` only if needed; callers may also do `from wiki import LOCKED_FOLD_PHASES` directly.
- **Rationale:** Discussion's mapping table and per-file ports use the `wiki.X` form throughout (`wiki.set_phase`, `wiki.list_tasks_brief`, `wiki.LOCKED_FOLD_PHASES`). Standardising on one import shape avoids per-file drift.
- **Applies to:** all batches

### Decision: task-shape-dict-not-dataclass

- **Decision:** Tasks are plain dicts. The brief shape is `{id, slug, title, group, brief, status, has_proposal}`. The full shape adds `body` and any other fields TinyDB stores. No `Task` dataclass — `_tasks_md.Task` is deleted with `_tasks_md.py` and not re-introduced anywhere.
- **Rationale:** Discussion decision `delete-v2-wiki-layer` and Q&A r4. Callers consume dicts directly; type hints become `list[dict]` / `dict`.
- **Applies to:** all batches

### Decision: ascii-stdout-only

- **Decision:** All new and modified `print()` / `_log()` output is ASCII only — replace any em-dash, arrow, or non-ASCII glyph with the documented substitutions (` -- `, ` -> `) per CLAUDE.md.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII. CLAUDE.md hard rule.
- **Applies to:** all batches

### Decision: timestamp-helpers-only

- **Decision:** Any generated timestamp (commit message body, log line, backup filename suffix if used) goes through `_timestamp.now_utc_compact()` / `now_utc_iso()`. No hand-formatted dates.
- **Rationale:** mill-plan convention — consistent timestamp shape across all artifacts.
- **Applies to:** all batches

### Decision: protocol-breaking-no-shim

- **Decision:** `OP_READ` and `OP_WRITE` are removed in batch 1 along with their handlers. The `PROTOCOL_VERSION` bump (1 -> 2) is the only mechanism callers need; stale daemons get killed and respawned by the existing version-mismatch path in `_ensure_daemon`. No transitional shim, no dual-dispatch.
- **Rationale:** Discussion decisions `structured-ops-over-socket` and `protocol-version-bump`. Squashed task — no in-flight daemon needs to keep talking the old protocol.
- **Applies to:** batch 1 (definition), batches 2 and 3 (consumption)

### Decision: tinydb-source-of-truth

- **Decision:** `tasks.json` is authoritative. `Home.md`, `_Sidebar.md`, and `proposal-{slug}.md` are daemon-rendered, never written by clients. Every mutating handler does `TinyDB op -> render(all_tasks) -> atomic_write each file -> commit_push`.
- **Rationale:** Discussion decision `tinydb-source-of-truth`. Eliminates the lossy parse-render round-trip from V3-as-shipped.
- **Applies to:** all batches

### Decision: no-advisory-lock

- **Decision:** `wiki_lock` and the `.mill-lock` file are gone. The daemon's single-threaded request handler serialises writes on a single host; `commit_push`'s existing one-rebase-retry handles cross-host non-fast-forward conflicts. Callers do not wrap mutations in any lock context manager and do not need to retry on `WikiConflictError` (the V3 `base_hash` CAS path is removed in batch 1 cards 5-6 because structured ops carry full intent and never require client-supplied base hashes — see card 6's CAS-removal rationale). Permanent push failure surfaces as `WikiPushError`; callers may surface that to the user but do not auto-retry.
- **Rationale:** Discussion decision `no-advisory-lock` plus batch 1's protocol redesign. With structured task ops (each = one TinyDB write + one render + one commit), there is no read-modify-write window for the client to expose; conflicts are exclusively at the git-push layer and handled inside `commit_push`.
- **Applies to:** all batches

### Decision: card-numbering-global

- **Decision:** Cards are numbered globally across all three batches. Batch 1 holds cards 1-12; batch 2 holds cards 13-14; batch 3 holds cards 15-38. Reviewer and implementer cite by global card number.
- **Rationale:** mill-plan template rule; uniqueness avoids ambiguity.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/integration_tests/test-cleanup.py`
- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/integration_tests/test-migration.py`
- `plugins/mill/integration_tests/test-review-discussion.py`
- `plugins/mill/integration_tests/test-wiki-concurrency.py`
- `plugins/mill/integration_tests/test-wiki-daemon-tinydb.py`
- `plugins/mill/integration_tests/test-wiki-e2e.py`
- `plugins/mill/integration_tests/test-wiki-migrate.py`
- `plugins/mill/unit_tests/test-wiki-daemon.py`
- `plugins/mill/unit_tests/test-wiki-noop-commit.py`
- `plugins/mill/unit_tests/test-wiki-sync.py`
- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_junction.py`
- `plugins/mill/scripts/_marker.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_setup.py`
- `plugins/mill/scripts/_sidebar.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/_tasks_md.py`
- `plugins/mill/scripts/_wiki.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-add.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-fold.py`
- `plugins/mill/scripts/millpy-inspect.py`
- `plugins/mill/scripts/millpy-migrate-config.py`
- `plugins/mill/scripts/millpy-migrate-layout.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-status.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/scripts/millpy-wiki-migrate.py`
- `plugins/mill/scripts/millpy-wikipush.py`
- `plugins/mill/scripts/wiki/__init__.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/scripts/wiki/_parse.py`
- `plugins/mill/scripts/wiki/_render.py`
- `plugins/mill/scripts/wiki/_server.py`
- `plugins/mill/scripts/wiki/_store.py`
- `plugins/mill/skills/mill-claim/SKILL.md`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/integration_tests/bench-reviewers.py`
- `plugins/mill/integration_tests/test-spawn-units.py`
- `plugins/mill/integration_tests/test-spawn.py`
- `plugins/mill/integration_tests/test-worktree-sibling-resolution.py`
- `plugins/mill/unit_tests/_test_helpers.py`
- `plugins/mill/unit_tests/test-abandon.py`
- `plugins/mill/unit_tests/test-bg-launcher.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-fold.py`
- `plugins/mill/unit_tests/test-millpy-add.py`
- `plugins/mill/unit_tests/test-millpy-bg.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-millpy-color.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-millpy-terminal.py`
- `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- `plugins/mill/unit_tests/test-millpy-vscode.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-reviewers.py`
- `plugins/mill/unit_tests/test-setup-hub-links.py`
- `plugins/mill/unit_tests/test-sidebar.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
- `plugins/mill/unit_tests/test-tasks-md.py`
- `plugins/mill/unit_tests/test-wiki-parse.py`
- `plugins/mill/unit_tests/test-wiki-protocol.py`
- `plugins/mill/unit_tests/test-wiki-render.py`
- `plugins/mill/unit_tests/test-wiki-store.py`
- `plugins/mill/unit_tests/test-wiki.py`
