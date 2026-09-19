# Plan: Audit mill-start/mill-plan/mill-go for turn reduction

```yaml
task: Audit mill-start/mill-plan/mill-go for turn reduction
slug: turn-reduction-audit
approved: false
started: 20260919-112719
parent: main
root: ""
verify: null
discussion_sha: e8fa346d9724f5658d730d0e7c13a02ab4c18039
```

## Batch Index

```yaml
batches:
  - number: 1
    name: turn-reduction-audit-doc
    file: 01-turn-reduction-audit-doc.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: Audit document location and format

- **Decision:** The deliverable is `doc/turn-reduction-audit.md`, using the repo's existing
  fenced-`yaml`-metadata-block convention (not `---` frontmatter), following the precedent already
  set by `doc/backlog.md`, `doc/v3-architecture.md`, and `doc/psmux-tui-behavior.md`.
- **Rationale:** `_mill/` is deleted or restored-from-base at merge time, so a permanent
  deliverable cannot live there; `doc/` is the repo's only existing home for durable, git-tracked
  design docs outside the wiki (which holds only `Home.md`). See `_mill/discussion.md`'s "Audit
  document location and format" Decision.
- **Applies to:** all batches (there is only one).

### Decision: No implementation of any collapse candidate

- **Decision:** This plan produces zero changes to any `SKILL.md`, any `millpy-*.py` script, or any
  helper module. The only file this plan creates or edits is `doc/turn-reduction-audit.md`.
- **Rationale:** the task body is explicit that implementing a candidate is out of scope — each
  accepted candidate becomes its own follow-up backlog task once this audit is reviewed.
- **Applies to:** all batches.

### Decision: verify: null is correct for this plan

- **Decision:** Both the module-wide `verify:` above and the single batch's own `verify:` are
  `null`. No test suite runs as part of this task.
- **Rationale:** the deliverable is one markdown document with no executable surface — exactly the
  documented "pure docs batch with no runnable surface" example in
  `plugins/mill/templates/plan-batch.md`'s own `## Batch Tests` guidance. The completeness check
  that substitutes for a test suite is manual (see `_mill/discussion.md`'s Testing section) and is
  applied by the Code Review loop's reviewer, plus an inline coverage self-check the implementer
  runs and records in the doc itself (batch 1, card 4).
- **Applies to:** all batches.

## All Files Touched

- `doc/turn-reduction-audit.md`
