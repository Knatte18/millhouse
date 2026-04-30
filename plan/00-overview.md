# Plan: '22 — par-A — mill-merge: auto-switch to PR path on branch-protection rejection'

```yaml
task: '22 — par-A — mill-merge: auto-switch to PR path on branch-protection rejection'
slug: mill-merge-pr-fallback
approved: true
started: 20260430-173426
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: pr-fallback-edits
    file: 01-pr-fallback-edits.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: no-python-code

- **Decision:** All changes are prose/config edits — no Python files are created or modified.
- **Rationale:** The fallback logic lives in `mill-merge/SKILL.md` (instructions to Claude Code) and the config blocks are YAML comments. No new helper functions or CLI scripts are needed.
- **Applies to:** all batches

### Decision: wiki-write-protocol

- **Decision:** The live `wiki/config.yaml` edit is committed and pushed via `_wiki.write_commit_push`, not left as an uncommitted file edit.
- **Rationale:** The wiki is a separate git repo; file edits without a commit would leave it in a dirty state visible to all concurrent mill sessions.
- **Applies to:** pr-fallback-edits (Card 3)

### Decision: idempotency-guard

- **Decision:** The fallback PR creation is guarded by a `gh pr list --head "$CHILD_BRANCH"` check before calling `gh pr create`, so re-runs after a partial failure do not attempt to open a duplicate PR.
- **Rationale:** Discussed during mill-start. If the user re-runs `/mill-merge` after a crash between PR creation and `pr-pending` append, the entry gate sees `phase: done` again and re-executes the direct path; the push will fail again and the fallback will fire.
- **Applies to:** pr-fallback-edits (Card 1)

## All Files Touched

- `c:/Code/millhouse/wiki/config.yaml`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/templates/wiki-config.yaml`
