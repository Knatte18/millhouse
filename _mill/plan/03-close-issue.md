# Batch: close-issue

```yaml
task: "Deactivate codeguide integration in millhouse"
batch: close-issue
number: 3
cards: 1
verify: PYTHONPATH= sh -c "! grep -q CODEGUIDE_PLUGIN_ROOT plugins/mill/skills/git-commit/SKILL.md && ! grep -q codeguide-update plugins/mill/skills/mill-merge-in/SKILL.md"
depends-on: [1, 2]
```

## Batch Scope

Close GitHub issue #1137 as moot, now that both call sites into codeguide are gone. The issue's `err.txt` artifact came from codeguide's own `resolve_scope.py`, which stops running the moment nothing invokes `codeguide-update`; batches 1 and 2 are the change that makes that true, so this batch depends on both landing first. This batch's own `verify:` re-confirms the mechanism is actually gone (both marker strings absent from the two edited skill files) immediately before the issue is closed, so the closure is never based on a stale assumption.

## Cards

### Card 12: close GitHub issue #1137

- **Context:**
  - `plugins/mill/skills/git-commit/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Run `gh auth status` first; if it fails, halt and report rather than silently skipping this card. Then run `gh issue comment 1137 --body "Closing as moot: mill's git-commit and mill-merge-in skills no longer call into the codeguide plugin (see plugins/mill/skills/git-commit/SKILL.md and plugins/mill/skills/mill-merge-in/SKILL.md), so codeguide's resolve_scope.py -- the source of this issue's err.txt artifact -- no longer runs."` followed by `gh issue close 1137`. Both commands target this repo's own `origin` remote via `gh`'s ambient repo detection -- do not pass an explicit `--repo` flag.
- **Commit:** none

## Batch Tests

`verify:` checks that neither `CODEGUIDE_PLUGIN_ROOT` (git-commit's deleted invocation) nor `codeguide-update` (mill-merge-in's deleted invocation) remain in the two files those batches edited, confirming the mechanism this issue tracked is actually gone before the issue is closed. Card 12 itself makes no file changes, so `Commit: none` is correct (`Edits:`/`Creates:`/`Deletes:`/`Moves:` are all also "none").
