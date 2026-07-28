# Plan: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
task: "Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure"
slug: "mill-merge-conflict-robustness-gaps"
approved: true
started: "20260728-182257"
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
    name: config-yaml-crash-fallback
    file: 01-config-yaml-crash-fallback.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
  - number: 2
    name: merge-in-marker-verification
    file: 02-merge-in-marker-verification.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
  - number: 3
    name: merge-in-semantic-duplication
    file: 03-merge-in-semantic-duplication.md
    depends-on: []
    verify: null
  - number: 4
    name: dirty-parent-worktree-preflight
    file: 04-dirty-parent-worktree-preflight.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: no cross-batch dependencies

- **Decision:** All four batches are root batches (`depends-on: []`) and may run in any order or in parallel.
- **Rationale:** Each of the four issues (#706, #713, #718, #705) touches a disjoint file set (see `_mill/discussion.md` Scope/In) — `_config.py`/`test-config.py`; `millpy-merge-in-subagent.py`/`test-millpy-merge-in-subagent.py`; `merge-in-conflict-brief.md`/`mill-merge-in/SKILL.md`; `mill-merge/SKILL.md`/`test-merge.py`. No card in one batch reads or edits a file another batch edits.
- **Applies to:** all batches

### Decision: Documentation-only batches skip `verify:`

- **Decision:** Batch 3 sets the batch-level `verify: null` — its content is SKILL.md/template prose with no runnable surface. Batch 4 is NOT documentation-only: although Card 15 is prose (`mill-merge/SKILL.md`), Card 16 adds real, directly-invocable integration-test assertions to `test-merge.py`, so batch 4's `verify:` is wired to that file directly (same non-`run-all.py` direct-invocation shape batches 1-2 already use) rather than left `null` — a `null` verify would leave Card 16's new assertions unrun by anything but a human remembering a manual step.
- **Rationale:** `_mill/discussion.md`'s Testing section states the `merge-in-conflict-brief.md` instruction "is not unit-testable (it's an LLM prompt, not code); document two distinct worked examples directly in the template itself" — this applies to batch 3 only. Batch 4's `mill-merge/SKILL.md` edit (Card 15) is likewise prose, but its paired `test-merge.py` extension (Card 16) is real Python, so it gets the same `verify:` treatment as batches 1-2's unit-test files.
- **Applies to:** merge-in-semantic-duplication

## All Files Touched

- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/templates/merge-in-conflict-brief.md`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
