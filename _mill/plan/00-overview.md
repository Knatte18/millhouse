# Plan: mill-finalize/mill-merge-in citation-scan pathspec `:!_mill` fails on git 2.53+

```yaml
task: mill-finalize/mill-merge-in citation-scan pathspec `:!_mill` fails on git 2.53+
slug: mill-finalize-citation-scan-pathspec-magic-bug
approved: true
started: 20260919-112545
parent: main
root: ""
verify: null
discussion_sha: 302160e17d2d3c0bc80307f7d24138e548280aa4
```

## Batch Index

```yaml
batches:
  - number: 1
    name: fix-citation-scan-pathspec
    file: 01-fix-citation-scan-pathspec.md
    depends-on: []
    verify: PYTHONPATH= git grep -q '.' -- . ':(exclude)_mill' ':(exclude)plugins/**/SKILL.md' ':(exclude)plugins/**/unit_tests/**' ':(exclude)plugins/**/integration_tests/**'
```

## Shared Decisions

### Decision: long-form pathspec, not a version guard

- **Decision:** Replace the short-form exclude pathspec `:!<pattern>` with the long-form `:(exclude)<pattern>` for all four exclusions in both affected citation-scan snippets, unconditionally (no git-version detection).
- **Rationale:** On git 2.53+, `:!<pattern>` fails with `fatal: Unimplemented pathspec magic '_' in ':!_mill'` whenever the character immediately following `!` is an underscore — confirmed via local repro (see Batch 1's `## Batch Tests`). `:(exclude)<pattern>` is semantically identical on every git version and is documented as a drop-in replacement by every duplicate GH issue (#1042, #1011, and others) tracking this bug. A version-detection branch would add complexity for no behavioral benefit, since the long form is universally valid.
- **Applies to:** fix-citation-scan-pathspec (the only batch).

### Decision: scope excludes mill-merge-in/SKILL.md

- **Decision:** This plan touches only `plugins/mill/skills/mill-finalize/SKILL.md` and `plugins/mill/skills/mill-merge/SKILL.md`. `plugins/mill/skills/mill-merge-in/SKILL.md` is explicitly out of scope.
- **Rationale:** A full read of the current `mill-merge-in/SKILL.md` and a repo-wide `grep -rn "':!" plugins/` (re-confirmed at plan-writing time) show it contains no citation-scan step and no `:!` pathspec at all — the task title and several duplicate GH issues (#1011, #1006, #1004) misattribute mill-merge's own snippet to mill-merge-in. See `_mill/discussion.md`'s "Scope correction: mill-merge-in is not affected" Decision for the full analysis this plan inherits.
- **Applies to:** all batches (i.e., the absence of any mill-merge-in edit anywhere in this plan is intentional, not an oversight).

## All Files Touched

- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
