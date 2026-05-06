# Plan: '11 (B) — Review-code: configurable holistic effort + diff-scoping via start_sha'

```yaml
task: '11 (B) — Review-code: configurable holistic effort + diff-scoping via start_sha'
slug: review-code-enhancements
approved: false
started: 20260506-125306
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: config-and-subprocess
    file: 01-config-and-subprocess.md
    depends-on: []
    verify: null

  - name: reviewer-effort-api
    file: 02-reviewer-effort-api.md
    depends-on: [config-and-subprocess]
    verify: python plugins/mill/unit_tests/test-reviewer-modules.py

  - name: diff-scope-and-effort
    file: 03-diff-scope-and-effort.md
    depends-on: [reviewer-effort-api]
    verify: null

  - name: test-diff-scope-and-effort
    file: 04-test-diff-scope-and-effort.md
    depends-on: [diff-scope-and-effort]
    verify: python plugins/mill/unit_tests/test-reviewer-modules.py && python plugins/mill/unit_tests/test-review-common.py && python plugins/mill/unit_tests/test-review-code-flow.py
```

## Shared Decisions

### Decision: effort-kwarg-default-none

- **Decision:** `effort: str | None = None` is the default on all reviewer `run` signatures. `None` passes through to the LLM provider, which already treats `None` as "no `--effort` flag" (see `_llm_claude._build_argv`). The internal `"max"` default in each reviewer module is preserved for callers that pass nothing.
- **Rationale:** Backwards-compatible: existing callers (plan review, discussion review) pass no `effort` and get current behaviour. Only `_review_code.run` passes a non-None value.
- **Applies to:** reviewer-effort-api, diff-scope-and-effort, test-diff-scope-and-effort

### Decision: no-new-files-except-tests

- **Decision:** No new source files are created. All changes are in-place edits to existing files.
- **Rationale:** The scope is narrow and fully expressible as modifications to existing modules.
- **Applies to:** all batches

### Decision: test-fixture-approach

- **Decision:** New tests follow the existing patterns in `test-review-code-flow.py` and `test-review-common.py`: in-memory fixture dicts for config, `tempfile.TemporaryDirectory` for filesystem state, `_reviewer_test_stub` for LLM responses. Tests that need git diff output create a real git repo in a tempdir with known commits.
- **Rationale:** Matches existing codebase conventions. No mocking frameworks needed — the stub is already there.
- **Applies to:** test-diff-scope-and-effort

## All Files Touched

- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_reviewer_sonnetmax.py`
- `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
- `plugins/mill/scripts/_reviewer_test_stub.py`
- `plugins/mill/scripts/_subprocess_util.py`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-reviewer-modules.py`
- `wiki/config.yaml`
