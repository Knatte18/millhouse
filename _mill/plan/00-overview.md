# Plan: mill-plan Entry step 2: _config.load_config called with hub_root/worktree_root swapped vs its own signature

```yaml
task: 'mill-plan Entry step 2: _config.load_config called with hub_root/worktree_root swapped vs its own signature'
slug: mill-plan-entry-config-load-args-swapped
approved: true
started: 20260820-175854
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: fix-call-site-keyword-args
    file: 01-fix-call-site-keyword-args.md
    depends-on: []
    verify: null
```

## Shared Decisions

_No cross-cutting decisions — this is a single-batch, single-card documentation fix confined to one
call-site edit in `mill-plan/SKILL.md`. See the batch's own `## Batch Scope` and Card 1 `Requirements:`
for the full rationale, mirrored from `_mill/discussion.md`._

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `plugins/mill/skills/mill-plan/SKILL.md`
