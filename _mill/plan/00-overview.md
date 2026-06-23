# Plan: Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling

```yaml
task: "Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling"
slug: mill-review-and-verify-quality
approved: false
started: 20260623-084455
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches._

```yaml
batches:
  - number: 1
    name: windows-verify-gate
    file: 01-windows-verify-gate.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py
  - number: 2
    name: nit-enforcement
    file: 02-nit-enforcement.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-nit-gate.py test-millpy-fix.py
  - number: 3
    name: fixer-holistic-verify
    file: 03-fixer-holistic-verify.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py
  - number: 4
    name: reviewer-anti-oscillation
    file: 04-reviewer-anti-oscillation.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-common.py
  - number: 5
    name: scope-violation-cleanup
    file: 05-scope-violation-cleanup.md
    depends-on: [4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py
```

## Shared Decisions

### Decision: win32-gated behaviour

- **Decision:** Any new platform-specific behaviour (the benign-cleanup verify success in batch 1) MUST be gated on `sys.platform == "win32"` so Linux/CI verify semantics are unchanged. Non-win32 paths keep today's exit-code behaviour exactly.
- **Rationale:** Issues #517 are Windows-only races; broadening to all platforms would risk masking real failures elsewhere.
- **Applies to:** windows-verify-gate (others have no platform-specific code).

### Decision: ASCII-only stdout

- **Decision:** All new `print()` / `_log()` / status-row / gate-message strings are ASCII only — replace `—`/`->` with ` -- `/` -> `. Windows cp1252 crashes on non-ASCII stdout.
- **Rationale:** Hard constraint from CLAUDE.md; mill runs on Windows.
- **Applies to:** all batches.

### Decision: verify-command shape (Python project)

- **Decision:** Every per-batch `verify:` starts with the literal `PYTHONPATH= ` prefix (empty value, single space) so the test subprocess loads worktree modules, not the cache. Tests run via `uv run --project plugins/mill`.
- **Rationale:** `verify-not-isolated` validator + the cache-vs-worktree module hazard.
- **Applies to:** all batches.

### Decision: test fixtures — no real git/LLM

- **Decision:** Unit tests use in-memory/tempfile fixtures, no real git or LLM calls, matching the existing suite. Where a tempfile git repo is needed (cleanliness, status), follow the existing `test-cleanliness.py` / `test-millpy-fix.py` fixture style.
- **Rationale:** Project testing convention.
- **Applies to:** all batches.

### Decision: intra-batch created modules

- **Decision:** A module created in this plan (`_nit_gate.py`, `test-nit-gate.py`) is referenced by name in card `Requirements:`, never listed in another card's `Context:` (it does not exist at plan time). Each batch is implemented by one Sonnet session that creates and consumes the module within the same run.
- **Rationale:** `Context:` is a plan-time allowlist of on-disk files; listing a to-be-created file would fail `non-existent-path`.
- **Applies to:** nit-enforcement.

## All Files Touched

- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_nit_gate.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-receiving-review/SKILL.md`
- `plugins/mill/templates/fixer-batch-brief.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-nit-gate.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
