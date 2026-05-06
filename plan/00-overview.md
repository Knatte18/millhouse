# Plan: 19 (A) — mill-go + scripts infra fixes

```yaml
task: 19 (A) — mill-go + scripts infra fixes
slug: mill-go-infra-fixes
approved: false
started: 20260506-113757
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
  - name: Lock CLI and mill-go SKILL.md updates
    file: 01-lock-cli-and-mill-go-skill.md
    depends-on: []
    verify: null
  - name: Implement parser hardening
    file: 02-implement-parser.md
    depends-on: []
    verify: null
  - name: Cleanup guard
    file: 03-cleanup-guard.md
    depends-on: []
    verify: null
  - name: PYTHONPATH documentation fix
    file: 04-docs-pythonpath.md
    depends-on: []
    verify: null
  - name: Tests
    file: 05-tests.md
    depends-on:
      - Implement parser hardening
      - Cleanup guard
    verify: "python plugins/mill/unit_tests/test-millpy-implement.py && python plugins/mill/unit_tests/test-cleanup.py"
```

## Shared Decisions

### Decision: no-new-phases

- **Decision:** Do not introduce a `merged` phase in mill-merge or any new phases beyond those already in the codebase.
- **Rationale:** The git log check approach in the cleanup guard removes the need for a `merged` phase. More phases = more state machines to keep consistent.
- **Applies to:** Cleanup guard, any future related work.

### Decision: skill-md-as-instructions

- **Decision:** SKILL.md files are instruction text for Claude Code; they are not compiled or tested. Changes to SKILL.md are docs-only from a testing perspective — no runnable verify needed.
- **Rationale:** mill-go SKILL.md and other SKILL.md changes are operator-facing instructions, not code paths.
- **Applies to:** Lock CLI and mill-go SKILL.md updates, PYTHONPATH documentation fix.

### Decision: flat-json-only

- **Decision:** The regex `r'\{[^{}]*"status"[^{}]*\}'` handles flat (non-nested) JSON only. The implementer report schema is always flat.
- **Rationale:** Nested JSON handling requires significantly more complex parsing. The implementer report schema (`{"status":..., "commit_sha":..., "session_id":...}`) is documented as flat and this is a constraint in `implementer-brief.md`.
- **Applies to:** Implement parser hardening.

### Decision: readonly-git-in-build-plan

- **Decision:** `build_plan()` may use read-only git subprocesses (via `_subprocess_util.run`). No git writes, no wiki writes.
- **Rationale:** The function docstring says "side-effect-free w.r.t. git and wiki writes". A read-only `git log` query is consistent with that intent. The docstring is updated to clarify.
- **Applies to:** Cleanup guard.

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/millpy-builder-lock.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
