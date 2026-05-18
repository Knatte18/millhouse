# Plan: 64 (A) -- Small infra fixes batch 9

```yaml
task: '64 (A) -- Small infra fixes batch 9'
slug: mill-misc-fixes-9
approved: true
started: 2026-05-18T06:54:40Z
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
    name: subprocess-bg-fixes
    file: 01-subprocess-bg-fixes.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-subprocess-util.py && python plugins/mill/unit_tests/test-millpy-bg.py
  - number: 2
    name: review-backend-fixes
    file: 02-review-backend-fixes.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: test-infra-fixes
    file: 03-test-infra-fixes.md
    depends-on: [2]
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 4
    name: templates-config-skills
    file: 04-templates-config-skills.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: No new library imports

- **Decision:** All changes use only imports already present in each file. No new third-party or stdlib packages are introduced.
- **Rationale:** These are targeted bug fixes in a flat-scripts layout; introducing new dependencies adds unnecessary churn.
- **Applies to:** all batches

### Decision: ASCII-only output strings

- **Decision:** All `print()` and log strings use ASCII only. Em-dash (`—`) → ` -- `; right-arrow (`→`) → ` -> `.
- **Rationale:** Per CLAUDE.md: Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **Applies to:** all batches

### Decision: Test style matches existing files

- **Decision:** Tests follow the non-class-based `main() -> int` pattern with a `failures` list, consistent with every existing test file in `plugins/mill/unit_tests/`.
- **Rationale:** Consistency; avoids mixing pytest-style and ad-hoc styles in the same directory.
- **Applies to:** batches 1, 3

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_subprocess_util.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/plan-batch.md`
- `plugins/mill/templates/plan-overview.md`
- `plugins/mill/unit_tests/_test_helpers.py`
- `plugins/mill/unit_tests/test-millpy-bg.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-subprocess-util.py`
