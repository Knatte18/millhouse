# Plan: Miscellaneous small tooling and doc/template accuracy gaps

```yaml
task: "Miscellaneous small tooling and doc/template accuracy gaps"
slug: mill-misc-tooling-and-docs-gaps
approved: false
started: "20260716-133957"
parent: hanf/linux-port-more
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: fixer-tier-warning
    file: 01-fixer-tier-warning.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-millpy-fix.py
  - number: 2
    name: cleanliness-nested-hub-revert
    file: 02-cleanliness-nested-hub-revert.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py
  - number: 3
    name: golang-build-gopath-fallback
    file: 03-golang-build-gopath-fallback.md
    depends-on: []
    verify: null
  - number: 4
    name: plan-overview-comment-fix
    file: 04-plan-overview-comment-fix.md
    depends-on: []
    verify: null
  - number: 5
    name: mill-plan-source-edit-guardrail
    file: 05-mill-plan-source-edit-guardrail.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: five issues, five independent batches

- **Decision:** Each batch fixes exactly one sourced GitHub issue (#651, #640, #658, #632, #623). No batch depends on another; all five are file-disjoint and safe to run fully in parallel.
- **Rationale:** the issues share no root cause, code path, or file — see `_mill/discussion.md`'s `batch-structure` Decision, which also documents (and corrects) an earlier false claim that #651 and #640 shared a file.
- **Applies to:** all batches.

### Decision: docs-only batches carry `verify: null`

- **Decision:** Batches 3, 4, and 5 are pure Markdown/SKILL.md instructional-text edits with no executable surface (no test harness in this repo parses SKILL.md or template-comment content). Their `verify:` is `null`; each batch's `## Batch Tests` states this explicitly, matching `_mill/discussion.md`'s Testing section for #658/#632/#623.
- **Rationale:** matches this repo's existing convention — `plugins/mill/unit_tests/` only covers `.py` modules, never skill/template prose.
- **Applies to:** batch 3 (golang-build-gopath-fallback), batch 4 (plan-overview-comment-fix), batch 5 (mill-plan-source-edit-guardrail).

## All Files Touched

- `plugins/golang/skills/golang-build/SKILL.md`
- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/plan-overview.md`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-reviewers.py`
