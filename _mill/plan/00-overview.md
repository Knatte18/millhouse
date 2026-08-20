# Plan: git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented

```yaml
task: 'git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented'
slug: git-pr-graphql-5xx-fallback
approved: false
started: 20260820-175433
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: rest-fallback
    file: 01-rest-fallback.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: unconditional-rest-attempt

- **Decision:** Step 10.5 (REST fallback) fires on any non-zero exit from step 10's `gh pr create`, not only on error text that looks like a GraphQL 5xx.
- **Rationale:** Matching GitHub's error text is fragile across `gh` CLI versions and outage types. An unconditional REST attempt is simpler and still correct: a non-transient failure (e.g. auth) fails REST too and falls through to browser at negligible cost.
- **Applies to:** rest-fallback

### Decision: duplicate-pr-check-after-both-tiers

- **Decision:** The "already exists" check runs only once, after both the GraphQL create (step 10) and the REST create (step 10.5) have failed — not before either attempt.
- **Rationale:** A single check at the final fallback boundary is simpler than duplicating it before every tier, and closes the real gap left by step 7 treating a GraphQL 5xx the same as "no PR exists" (step 7 itself is unchanged — out of scope for this task).
- **Applies to:** rest-fallback

## All Files Touched

- `plugins/mill/skills/git-pr/SKILL.md`
