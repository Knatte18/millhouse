# Plan: 66 (A) -- Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv

```yaml
task: '66 (A) -- Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv'
slug: review-sandbox-followup
approved: false
started: '20260517-151748'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: sandbox-argv
    file: 01-sandbox-argv.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-llm-claude-argv.py
  - number: 2
    name: snapshot-guard
    file: 02-snapshot-guard.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-review-common-guard.py
  - number: 3
    name: review-error-envelope
    file: 03-review-error-envelope.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-review-cli-error-envelope.py
  - number: 4
    name: wiki-noop-commit
    file: 04-wiki-noop-commit.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-wiki-noop-commit.py
  - number: 5
    name: bg-liveness
    file: 05-bg-liveness.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-bg-liveness.py
  - number: 6
    name: millgo-holistic-recovery
    file: 06-millgo-holistic-recovery.md
    depends-on: [5]
    verify: null
```

## Shared Decisions

### Decision: stdlib-only for new helpers

- **Decision:** New helper `_bg.py` and all unit tests use Python stdlib only -- no `psutil`, no third-party imports beyond what the existing scripts pull in (`yaml` is already a dep).
- **Rationale:** mill has been disciplined about stdlib-only dependencies. `os.kill(pid, 0)` works on both Linux and Windows CPython and removes the need for `psutil`.
- **Applies to:** all batches

### Decision: ASCII-only stdout/stderr in production code

- **Decision:** Every new `print()` / log line uses ASCII only. Em-dash becomes ` -- `; right-arrow becomes ` -> `. Docstrings and comments may keep non-ASCII characters.
- **Rationale:** `CLAUDE.md` `## Conventions worth carrying` — Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **Applies to:** all batches

### Decision: Unit-test framework is unittest

- **Decision:** New unit tests use the project's existing `unittest.TestCase` pattern. The tests run as `python plugins/mill/unit_tests/test-<name>.py` via the run-all runner. No pytest, no fixtures beyond `tempfile.TemporaryDirectory()`.
- **Rationale:** Matches every existing test file under `plugins/mill/unit_tests/`. Avoids introducing pytest as a new dependency.
- **Applies to:** all batches that add tests (1, 2, 3, 4, 5)

### Decision: Verify command uses uv run via the source-tree venv

- **Decision:** Every batch's `verify:` command runs as `python plugins/mill/unit_tests/test-<name>.py` and is launched via `uv run --project plugins/mill <command>` when invoked from a fresh shell. mill-go's batch verify-runner already wraps this; the planner just records the test file name in the batch frontmatter.
- **Rationale:** Per `CLAUDE.md` `## Conventions worth carrying` source-tree-form exception, `uv run --project plugins/mill` is the canonical invocation for in-repo testing.
- **Applies to:** all batches with non-null verify

### Decision: ReviewResult ERROR shape

- **Decision:** Every code path that converts an exception into a `verdict: ERROR` review entry uses this exact dict shape:
  ```python
  {
      "scope": <scope_label>,
      "verdict": "ERROR",
      "file": None,
      "error": str(exc),
      "session_id": <session_id_or_None>,
  }
  ```
  The top-level `ReviewResult.verdict` is computed via `_aggregate_top_verdict` (already in `_review_code.py`) so an all-ERROR review aggregates to `"ERROR"`, otherwise to the worst-case non-ERROR verdict.
- **Rationale:** mill-go's ERROR-only-aggregate retry path keys off the top-level `"ERROR"` value and the per-entry `error` string; consistent shape across discussion/plan/code reviews keeps the orchestrator's parsing logic uniform.
- **Applies to:** batch 3

## All Files Touched

- `plugins/mill/scripts/_bg.py`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_wiki.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-bg-liveness.py`
- `plugins/mill/unit_tests/test-llm-claude-argv.py`
- `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- `plugins/mill/unit_tests/test-review-common-guard.py`
- `plugins/mill/unit_tests/test-wiki-noop-commit.py`
