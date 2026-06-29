# Plan: Fix stale checkpoint safety, Go binary ephemeral allowlist, and bare agent-tier name trap

```yaml
task: "Fix stale checkpoint safety, Go binary ephemeral allowlist, and bare agent-tier name trap"
slug: mill-scope-and-infra-gaps
approved: false
started: "20260629-163520"
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches. Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here. All three batches are independent (no shared files), so all are root batches and may run in parallel._

```yaml
batches:
  - number: 1
    name: bare-tier-aliases
    file: 01-bare-tier-aliases.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py
  - number: 2
    name: go-artifact-allowlist
    file: 02-go-artifact-allowlist.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py
  - number: 3
    name: idempotent-checkpoint
    file: 03-idempotent-checkpoint.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: scope-and-independence

- **Decision:** Each of the three GitHub issues (#565, #571, #567) is implemented as its own batch; batches share no files and carry `depends-on: []`.
- **Rationale:** The three fixes touch disjoint surfaces (the agent registry + `_reviewers.py`; `_cleanliness.py`; one SKILL.md). Independent root batches let mill-go parallelize and isolate verify scope.
- **Applies to:** all batches

### Decision: ascii-only-stdout

- **Decision:** Any new `print`/log output (the #567 audit note, any new messages) uses ASCII only — ` -- ` for em-dash, ` -> ` for arrow.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII (CLAUDE.md convention).
- **Applies to:** all batches

### Decision: verify-isolation-prefix

- **Decision:** Every non-null `verify:` command begins with the literal `PYTHONPATH= ` token so the test subprocess loads worktree modules, not cache modules. The #567 batch is doc-only and uses `verify: null`.
- **Rationale:** Python-project requirement enforced by the `verify-not-isolated` validator (CLAUDE.md).
- **Applies to:** all batches

### Decision: additive-not-restrictive

- **Decision:** All three fixes are strictly additive — new registry entries, a richer error message, an extended allowlist, an idempotent checkpoint. No existing entry, name, or behavior is removed (bare `haiku` stays; existing allowlist suffixes stay; the rollback contract is unchanged).
- **Rationale:** Avoids breaking working configs and the `mill-merge` consumer that resets to the same checkpoint name.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/templates/mill-agents.yaml`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-reviewers.py`
