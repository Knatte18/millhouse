# Plan: Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity

```yaml
task: "Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity"
slug: "mill-pipeline-finalize-gaps"
approved: false
started: "20260629-164439"
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
    name: implement-pipeline
    file: 01-implement-pipeline.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-implementer-common.py test-fix-finalize.py test-finalize-cleanup.py
  - number: 2
    name: merge-in-cli-parity
    file: 02-merge-in-cli-parity.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py test-merge-in-subagent.py
```

## Shared Decisions

### Decision: accept-and-ignore CLI flag parity

- **Decision:** Envelope-field parity gaps (#568, #569) are resolved by adding the missing
  flags to the finalize parsers as `default=None`, accepted-but-ignored arguments — never by
  stripping fields from the prepare envelopes. Each new flag carries a help string noting it is
  accepted for CLI-shape parity and ignored (finalize reads authoritative state from status.md
  or re-runs verify directly).
- **Rationale:** `millpy-fix.py` already accepts `--round`/`--start-sha`/`--session-id` as
  ignored flags, and `millpy-implement.py` already accepts ignored `--start-sha`/`--session-id`.
  Accept-and-ignore makes mill-go's generic "thread applicable prepare-envelope fields into
  finalize" guidance universally safe with no skill-doc changes and no divergence of the shared
  `emit_prepare` envelope shape. `millpy-fix.py` is the parity reference and is NOT modified.
- **Applies to:** implement-pipeline (#568 `--round` on implement), merge-in-cli-parity (#569
  `--session-id`/`--start-sha`/`--round` on merge-in-subagent).

### Decision: ASCII-only stdout

- **Decision:** All new reason strings, help text, and log/print output use ASCII only
  (`--` not em-dash, `->` not arrow).
- **Rationale:** CLAUDE.md hard rule — Windows cp1252 stdout crashes on non-ASCII.
- **Applies to:** all batches.

### Decision: content-commit counting excludes the start-batch housekeeping commit

- **Decision:** For #570, `commits_made` / completeness counting must count CONTENT commits,
  excluding the `mill-go: start batch <name>` housekeeping commit. `start_sha` is captured in
  prepare BEFORE that commit, so a raw `git rev-list --count start_sha..HEAD` over-counts
  content by one whenever the housekeeping commit exists. A shared
  `_content_commit_count(project_root, start_sha)` helper centralizes this and is used by both
  the new verify-failure reclassification and the existing `_batch_completeness_stuck` gate.
- **Rationale:** Without excluding the housekeeping commit, the `< card_count` boundary misses
  the common one-card-short case (content N-1 → raw count N, not `< N`) and mislabels a
  zero-content batch as `commits_made=1`.
- **Applies to:** implement-pipeline.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
