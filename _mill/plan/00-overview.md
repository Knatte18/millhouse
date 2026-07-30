# Plan: mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation

```yaml
task: 'mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation'
slug: mill-plan-requirements-byte-exactness-gap
approved: true
started: 20260730-105322
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
    name: requirements-quote-indent-drift-check
    file: 01-requirements-quote-indent-drift-check.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: single-batch-scope

- **Decision:** This entire task is one batch with three cards: (1) the new
  `_check_requirements_quote_indent_drift` check implementation in
  `plugins/mill/scripts/_plan_validate.py`, (2) the corresponding
  `mill-plan/SKILL.md` fix-table row + `## Principles` doc warning, (3) the
  nine new unit tests in `plugins/mill/unit_tests/test-plan-validate.py`.
- **Rationale:** All three files are tightly coupled — the fix-table row's
  prose must exactly describe the check's mechanical-fix semantics, and the
  tests exercise the check's exact behavior — so a single Sonnet session
  holding all three in context at once avoids any cross-file drift a
  multi-batch split would risk. Combined `Edits:` byte size (~378KB / ~94.5k
  token estimate) is comfortably under `pipeline.max_batch_context_tokens`
  (120000).
- **Applies to:** all batches (only one exists).

### Decision: check-only-touches-edits-not-context-or-creates

- **Decision:** `_check_requirements_quote_indent_drift` compares a card's
  `Requirements:` fence content only against files resolved from that same
  card's own `Edits:` field (via `resolve_existing_paths`), never
  `Context:`, `Creates:`, or any other card's files.
- **Rationale:** Per `_mill/discussion.md`'s `match-target-edits-only`
  Decision — a `Requirements:` fence meant as Edit-tool `old_string` bait is
  only meaningful against a file this card actually edits.
- **Applies to:** requirements-quote-indent-drift-check.

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path
across every batch, sorted alphabetically (Move **source** paths are
excluded — they disappear, like `Deletes:` tokens). Cards are the
source of truth; this section is the input `_plan_validate.py`'s
`all-files-touched-mismatch` check cross-references against the derived
union of every card's `Edits:`/`Creates:`/Move-target paths, to catch
drift between the hand/agent-maintained list here and that derived
union._

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
