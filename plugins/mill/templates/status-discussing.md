<!--
Template: `<WIKI_PATH>/active/<slug>/status.md` initial write for phase=discussing.
Used by: mill-spawn (first status write after claiming a task).
Tokens: <TASK_TITLE>, <TASK_DESCRIPTION>, <TIMESTAMP>, <PARENT_BRANCH>, <SLUG>, <BRANCH>.
render_initial inserts an optional `parent_thread:` row immediately after `parent_branch:` when a non-empty parent_thread is passed; the template has no token for it.
Strip this HTML comment before writing. -->
# Status

```yaml
phase: discussing
slug: <SLUG>
branch: <BRANCH>
plan: null
parent_branch: <PARENT_BRANCH>
task: <TASK_TITLE>
task_description: |
  <TASK_DESCRIPTION>
```

## Timeline

```text
discussing  <TIMESTAMP>
```
