# Plan: Accumulated bug fixes

```yaml
task: Accumulated bug fixes
slug: mill-bug-fixes
approved: false
started: 20260519-120358
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
    name: verify-fix-post-verify
    file: 01-verify-fix-post-verify.md
    depends-on: []
    verify: "plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-millpy-merge-in-subagent.py"
  - number: 2
    name: mill-plan-handoff-guard
    file: 02-mill-plan-handoff-guard.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: ASCII-only output

- **Decision:** Any new `print()` / log output must be ASCII only. Use `--` instead of em-dash and `->` instead of arrow glyphs.
- **Rationale:** CLAUDE.md hard constraint — Windows cp1252 stdout crashes on non-ASCII.
- **Applies to:** all batches.

### Decision: Test invocation form

- **Decision:** Run unit tests with `plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` for a single file (or `…/run-all.py` for the full suite). Do not invoke pytest. Do not invoke `uv run` inside cards.
- **Rationale:** Matches the existing direct-venv invocation pattern used elsewhere in this repo's unit tests. The `uv run --project plugins/mill` form in CLAUDE.md is an alternative; we standardize on direct-venv here for consistency with the existing test files.
- **Applies to:** verify-fix-post-verify.

## All Files Touched

- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
