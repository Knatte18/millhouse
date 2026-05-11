# Plan: 43 (A) — Discussion-review gaps in batches + NOTE-finding handling

```yaml
task: 43 (A) — Discussion-review gaps in batches + NOTE-finding handling
slug: discussion-review-gap-batching
approved: true
started: 20260511-104557
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
    name: skill-edits
    file: 01-skill-edits.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: mirror-mill-plan-shape

- **Decision:** All new prose follows `plugins/mill/skills/mill-plan/SKILL.md`'s patterns verbatim where parallel — step labels `4a` / `4b` / `5`, the `## Fixed` / `## Pushed Back` fixer-report sections, the single-commit message verb shape (`mill-start: discussion-fix round {N} for {slug}`), the `discussion-fix-r{N}` status-phase name, and the `<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md` fixer-report filename pattern. Names swap `plan` → `discussion`, `mill-plan` → `mill-start`.
- **Rationale:** Future readers comparing the two skills should see the same shape. Matches the verbatim suggested fix in GitHub issue #222 and the cross-references in `task/discussion.md`'s "Decisions" and "Technical context" sections.
- **Applies to:** all batches.

### Decision: numbered-options-rule-references-conversation-skill

- **Decision:** When step 5 (gap-batching) cites the numbered-options format rule, it references `mill:conversation` ("the recommended option, if any, MUST be option 1") with a one-line pointer rather than restating the rule. Same for any other rule already anchored in another skill.
- **Rationale:** Avoid drift between the global rule in `conversation/SKILL.md` and a per-skill copy. If `conversation/SKILL.md` ever changes, mill-start inherits the change automatically.
- **Applies to:** all batches.

### Decision: skill-md-only-no-python-no-tests

- **Decision:** No Python files change. No new unit or integration tests. The verification surface is the rendered SKILL.md itself — checked statically in `## Batch Tests` of the single batch. `verify:` in the overview and batch frontmatter is `null`.
- **Rationale:** Per `task/discussion.md` "Scope → Out" and "Testing → Unit tests" sections: no public Python API surface changes, no script behaviour changes, no template changes. Asserting markdown shape via a brittle parser test was explicitly rejected in the discussion.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/skills/mill-start/SKILL.md`
