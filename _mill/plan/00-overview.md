# Plan: mill-implementer: commit_sha transcription/truncation and final-status-line reliability

```yaml
task: 'mill-implementer: commit_sha transcription/truncation and final-status-line reliability'
slug: implementer-commit-sha-and-status-line-reliability
approved: true
started: 20260904-100640
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: brief-instruction-hardening
    file: 01-brief-instruction-hardening.md
    depends-on: []
    verify: null
  - number: 2
    name: git-commit-staging-verification
    file: 02-git-commit-staging-verification.md
    depends-on: []
    verify: null
  - number: 3
    name: commit-sha-field-rename-and-regression-tests
    file: 03-commit-sha-field-rename-and-regression-tests.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-merge-in-subagent.py
```

## Shared Decisions

### Decision: prose/instruction-only edits carry `verify: null`

- **Decision:** Batches 01 and 02 edit `.md` template/skill files with no executable
  surface (implementer-brief instructions, git-commit skill prose). Neither batch
  declares a `verify:` command.
- **Rationale:** There is no automated test for prose instructions in this repo. The
  discussion round confirmed both changes' correctness is verified by the
  discussion/plan review loop itself, not by a test suite. Inventing a fake verify
  command would be worse than `null` — it would claim coverage that doesn't exist.
- **Applies to:** brief-instruction-hardening, git-commit-staging-verification.

### Decision: `commit_sha_field_name` override is additive-only

- **Decision:** The new `commit_sha_field_name: str = "commit_sha"` keyword parameter
  on `_forward_output` / `finalize_from_output` (batch 03) defaults to today's
  literal field name. Every existing caller (the batch/card success path used by
  `millpy-implement.py`, and `millpy-fix.py`'s finalize calls) is left unchanged and
  keeps emitting `commit_sha` exactly as today. Only `millpy-merge-in-subagent.py`'s
  two conflicts-mode call sites pass the override.
- **Rationale:** The discussion round explicitly scoped this to conflicts-mode only —
  the batch/card success path's `commit_sha` already refers to a real,
  already-created commit and is not misleading (see `_mill/discussion.md`'s Scope >
  Out). A default-preserving optional parameter keeps every other caller's behavior
  and existing test coverage (which does assert `commit_sha` on that path — see
  `test-implementer-common.py` cases asserting `data["commit_sha"] == new_head`)
  bit-for-bit unchanged.
- **Applies to:** commit-sha-field-rename-and-regression-tests.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/git-commit/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
