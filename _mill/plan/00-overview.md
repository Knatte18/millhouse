# Plan: mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies

```yaml
task: 'mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies'
slug: misc-small-bugs-spawn-implement-cleanliness
approved: true
started: '2026-08-13T07:53:54Z'
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: hub-path-terminal-fallback
    file: 01-hub-path-terminal-fallback.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-paths.py
  - number: 2
    name: spawn-config-local-yaml-defensive-write
    file: 02-spawn-config-local-yaml-defensive-write.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-spawn.py
  - number: 3
    name: finalize-batch-scoped-dirty-check
    file: 03-finalize-batch-scoped-dirty-check.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
  - number: 4
    name: cleanliness-unresolvable-parent-diff
    file: 04-cleanliness-unresolvable-parent-diff.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py
  - number: 5
    name: discussion-review-tooling-claim-consistency-check
    file: 05-discussion-review-tooling-claim-consistency-check.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-discussion-flow.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: five-independent-bugs-no-shared-code

- **Decision:** Each batch fixes exactly one GitHub issue (#833, #834, #825, #818, #812) in its own file(s), with its own test file. No batch depends on another; all five are root batches in the DAG.
- **Rationale:** The discussion's Scope section groups #833+#834 under one root symptom (missing `config.local.yaml`) but they touch entirely different files (`_paths.py` vs `millpy-spawn.py`) with no shared code path — batching them together would violate "smart unit" batch sizing without any benefit. #825, #818, #812 are explicitly unrelated per the discussion's Problem section.
- **Applies to:** all batches

### Decision: existing-test-harness-conventions-per-file

- **Decision:** Every new test is added to the existing test file for its module, following that file's own established harness convention exactly — do not introduce a new test-running pattern into a file that doesn't already use it. `test-paths.py`'s `main()` uses inline `try/except AssertionError` blocks with `assert` + `print("PASS: ...")`. `test-millpy-spawn.py` uses standalone `def test_xxx() -> None:` functions (raising bare `AssertionError`) registered in the `tests = [...]` list inside `main()`. `test-implementer-common.py` uses numbered `# Case N:` inline blocks inside `main()`, each wrapped in `try/except`, incrementing a shared `errors` counter/`failures` list (whichever the file already uses at the case's insertion point — read the surrounding cases before adding). `test-cleanliness.py` uses the same numbered inline-block-plus-`failures.append(...)` convention as `test-paths.py`/`test-implementer-common.py`. `test-review-discussion-flow.py` uses a mix: numbered inline blocks inside `main()` for most cases, plus standalone `def test_xxx() -> int:` functions (returning 0/1) invoked via `errors += test_xxx()` near the end of `main()` for a few larger, self-contained cases — the new #812 test is small and self-contained, so add it as one of the latter.
- **Rationale:** Each file's harness already diverged from a single shared runner years ago; matching the surrounding convention keeps the diff minimal and avoids introducing a second competing test-execution style into a single file.
- **Applies to:** all batches

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/handoff.md`
- `plugins/mill/templates/review-discussion.md`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
