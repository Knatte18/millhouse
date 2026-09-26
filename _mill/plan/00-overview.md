# Plan: plan validator and wiki-guard hook false positives

```yaml
task: "plan validator and wiki-guard hook false positives"
slug: "tooling-false-positives"
approved: true
started: "20260926-085319"
parent_branch: "main"
discussion_sha: "68505c337c3a057f32a29d999506431cfaff1e60"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: wiki-guard
    file: 01-wiki-guard.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-guard.py
  - number: 2
    name: hook-install
    file: 02-hook-install.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-claude-settings.py
  - number: 3
    name: symbol-resolution
    file: 03-symbol-resolution.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate-cross-batch-build-break.py test-plan-validate-indent-drift-line.py
  - number: 4
    name: symbol-resolution-tests
    file: 04-symbol-resolution-tests.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate-symbol-resolution.py
```

## Shared Decisions

### Decision: source-of-truth is discussion.md

- **Decision:** every design choice (framework-name set contents, type-first resolution order, the wiki-guard tokenizer order and accepted-conservative behaviors, the hook command template and reconcile rules) is fixed in the task's discussion.md; batches implement it and never re-decide it.
- **Rationale:** discussion.md went through discussion review to convergence.
- **Applies to:** all batches

### Decision: new test file for the validator, not the 677KB existing one

- **Decision:** validator tests go in a NEW file `test-plan-validate-symbol-resolution.py`, modelled on the sibling standalone `test-plan-validate-indent-drift-line.py`; `test-plan-validate.py` is far too large to cite as Context and is run only as a regression check inside batch 3's verify.
- **Rationale:** keeps the batch under the context cap.
- **Applies to:** symbol-resolution, symbol-resolution-tests

### Decision: hook fails open when its script path is stale

- **Decision:** the installed hook command embeds the versioned plugin cache path; a stale path makes the guard fail open until mill-setup Phase 4.8 is re-run. Accepted per discussion.md.
- **Rationale:** same lifecycle as the existing `MILL_PYTHON` setting.
- **Applies to:** hook-install

### Decision: recommended done_gate (not applied)

- **Decision:** recommend `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` as a repo-wide gate. Not applied: mill-go gates on the effective config value, not this Decision.
- **Rationale:** batch verifies are scoped to single test files; the installed hook and validator changes touch shared modules.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_claude_settings.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_wiki_guard.py`
- `plugins/mill/scripts/millpy-wiki-guard.py`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/unit_tests/test-claude-settings.py`
- `plugins/mill/unit_tests/test-plan-validate-symbol-resolution.py`
- `plugins/mill/unit_tests/test-wiki-guard.py`
