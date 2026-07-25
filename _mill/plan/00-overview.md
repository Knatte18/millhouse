# Plan: Skill doc/table accuracy gaps across mill-groom, mill-start/mill-plan, and implementer-brief

```yaml
task: "Skill doc/table accuracy gaps across mill-groom, mill-start/mill-plan, and implementer-brief"
slug: mill-skill-docs-and-tooling-accuracy
approved: true
started: "20260725-111826"
parent: hanf/linux-port-more
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: doc-tooling-fixes
    file: 01-doc-tooling-fixes.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: verification is manual/inspection-only

- **Decision:** No `verify:` command is set at the batch or module-wide level. Every card in this plan is a prose/markdown edit to a skill doc or `CLAUDE.md` — there is no runnable code path or test suite covering skill-doc text.
- **Rationale:** This repo (a `uv`/Python project) has no markdown-lint gate configured, so there is no equivalent automated check to substitute (per `discussion.md`'s Testing section). Verification is per-file inspection, listed in each card's parent batch under `## Batch Tests`.
- **Applies to:** all batches.

### Decision: independent single-file fixes, no shared code

- **Decision:** The four cards in this plan fix four unrelated documentation/tooling-guidance gaps (mill-groom, mill-start ×2, CLAUDE.md). None share a root cause, a helper, or an interface — each card's `Requirements:` is self-contained and does not depend on another card's outcome.
- **Rationale:** `discussion.md`'s Problem section explicitly frames these as four independently-filed, independently-consolidated GitHub issues bundled into one task for a single plan/implement pass, not a single coherent feature.
- **Applies to:** all batches.

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/skills/mill-groom/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
