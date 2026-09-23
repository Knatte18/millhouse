# Batch: close-issue

```yaml
task: "Deactivate codeguide integration in millhouse"
batch: close-issue
number: 3
cards: 1
verify: PYTHONPATH= sh -c "! grep -q CODEGUIDE_PLUGIN_ROOT plugins/mill/skills/git-commit/SKILL.md && ! grep -q codeguide-update plugins/mill/skills/mill-merge-in/SKILL.md && uv run --project plugins/mill python plugins/mill/unit_tests/test-sibling.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py && uv run --project plugins/mill python plugins/mill/integration_tests/test-worktree-sibling-resolution.py"
depends-on: [1, 2]
```

## Batch Scope

Close GitHub issue #1137 as moot, now that both call sites into codeguide are gone. The issue's `err.txt` artifact came from codeguide's own `resolve_scope.py`, which stops running the moment nothing invokes `codeguide-update`; batches 1 and 2 are the change that makes that true, so this batch depends on both landing first. This batch's own `verify:` re-confirms the mechanism is actually gone (both marker strings absent from the two edited skill files) immediately before the issue is closed, so the closure is never based on a stale assumption, and additionally re-runs `test-sibling.py`, `test-guards.py`, and `test-worktree-sibling-resolution.py` unmodified -- discussion.md's Testing section names these as the empirical regression check that the files this plan deliberately does NOT touch (`_sibling.py`, the codeguide plugin) still pass, and this is the natural place to run them since it is the plan's last batch.

## Cards

### Card 12: close GitHub issue #1137

- **Context:**
  - `plugins/mill/skills/git-commit/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Run `gh auth status` first; if it fails, halt and report rather than silently skipping this card. Then run `gh issue comment 1137 --body "Closing as moot: mill's git-commit and mill-merge-in skills no longer call into the codeguide plugin (see plugins/mill/skills/git-commit/SKILL.md and plugins/mill/skills/mill-merge-in/SKILL.md), so codeguide's resolve_scope.py -- the source of this issue's err.txt artifact -- no longer runs."` followed by `gh issue close 1137`. Both commands target this repo's own `origin` remote via `gh`'s ambient repo detection -- do not pass an explicit `--repo` flag. If the `gh issue comment` call fails, halt and report -- do not attempt the close. If `gh issue comment` succeeds but the following `gh issue close` call fails (e.g. the issue was already closed by another actor in the meantime), do not treat this as a hard card failure: report that the comment posted successfully and surface the close command's error/exit status to the operator, then continue -- the comment is the durable record either way.
- **Commit:** none

## Batch Tests

`verify:` checks that neither `CODEGUIDE_PLUGIN_ROOT` (git-commit's deleted invocation) nor `codeguide-update` (mill-merge-in's deleted invocation) remain in the two files those batches edited, confirming the mechanism this issue tracked is actually gone before the issue is closed, then re-runs `test-sibling.py`, `test-guards.py`, and `test-worktree-sibling-resolution.py` as a regression check on the files this plan intentionally left untouched. Card 12 itself makes no file changes, so `Commit: none` is correct (`Edits:`/`Creates:`/`Deletes:`/`Moves:` are all also "none").
