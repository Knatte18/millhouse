# Plan: mill-config.yaml unknown-key warning for pipeline.autonomous_mode

```yaml
task: mill-config.yaml unknown-key warning for pipeline.autonomous_mode
slug: mill-config-autonomous-mode-unknown-key
approved: false
started: 20260802-113219
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
    name: deprecated-key-suppression
    file: 01-deprecated-key-suppression.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: suppress via deprecated_keys, no shim

- **Decision:** Add `"pipeline.autonomous_mode"` as a bare entry to the
  `deprecated_keys` set in `_config.py`'s `warn_unknown_keys`, mirroring
  the existing `"llm.claude.psmux.via_psmux"` entry. No migration shim,
  no config-value handling of any kind.
- **Rationale:** `pipeline.autonomous_mode` was fully deleted (commit
  `6cbd6dc6`), not merely deprecated with a successor value — there is
  nothing to migrate to, so pure suppression is correct. This matches
  the exact precedent `deprecated_keys` was built for.
- **Applies to:** all batches

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path
across every batch, sorted alphabetically (Move **source** paths are
excluded — they disappear, like `Deletes:` tokens). Cards are the
source of truth; this section is the input `_plan_validate.py`'s
`all-files-touched-mismatch` check cross-references against the derived
union of every card's `Edits:`/`Creates:`/Move-target paths, to catch
drift between the hand/agent-maintained list here and that derived
union._

- `plugins/mill/scripts/_config.py`
- `plugins/mill/unit_tests/test-config.py`
