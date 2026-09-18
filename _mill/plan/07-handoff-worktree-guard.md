# Batch: handoff-worktree-guard

```yaml
task: "mill-go-base: orchestration robustness gaps"
batch: handoff-worktree-guard
number: 7
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python -c "import pathlib; t = pathlib.Path('plugins/mill/skills/mill-go-base/handoff.md').read_text(encoding='utf-8'); assert 'already cleaned up' in t, 'missing existence-check-and-skip marker'; window = t.split('mill-self-report')[0][-800:]; assert 'worktree_root' in window, 'worktree_root existence check not found near self-report step'; print('ok')"
depends-on: []
```

## Batch Scope

Fixes #990: guards Handoff step 6 (`/mill-self-report --auto`) against a concurrent `mill-cleanup` run having already deleted the task worktree between step 5 (`mill-finalize`/`mill-merge`, which flips Home.md to `[done]` and creates the archive tag) and step 6 reaching its first shell command (see `_mill/discussion.md`'s `990-worktree-race-guard` Decision — the issue's own literal suggested fix, `cd` to the hub/parent worktree, was rejected because it conflicts with this repo's "Worktree isolation" convention, which forbids a task-worktree session from `cd`-ing to the parent). Single card, single file (`handoff.md`); estimated context ≈ 18,838/4 ≈ 4,710 tokens.

## Cards

### Card 11: existence-check `worktree_root` before invoking self-report

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Locate Handoff step 6: "If `pipeline.auto_report: true` → invoke `/mill-self-report --auto`. **Always fires** at the end of Handoff, including after a `pr-pending` halt in step 5 — do NOT treat the PR-pending message as task termination. The skill checks `gh auth` itself and bails cleanly if absent. Cross-thread merges and post-PR teardowns are not auto-reflected; user can run `/mill-self-report` manually if wanted." Immediately before the `invoke /mill-self-report --auto` action (still inside the `pipeline.auto_report: true` branch, before any other work in step 6), insert a plain filesystem existence check on `worktree_root` (already a Builder-held variable, bound at Path Setup earlier in this skill's Entry section — no new path resolution needed): if it still exists on disk, proceed to invoke `/mill-self-report --auto` exactly as today, unchanged. If it does NOT exist — meaning a concurrent `mill-cleanup` run swept the worktree away after step 5's `mill-finalize`/`mill-merge` flipped Home.md to `[done]` and created the archive tag, but before this session reached step 6 — skip the `/mill-self-report --auto` invocation entirely and instead log one ASCII-only line (per this repo's `print()`/`_log()` ASCII-only convention) stating, using this exact phrase verbatim, that the task's worktree was "already cleaned up" by a concurrent `mill-cleanup` run before self-report could run, and that no further action is taken (self-report has nothing left to inspect for a worktree that a concurrent cleanup has already confirmed-and-archived as done). Do NOT attempt to `cd` anywhere — neither to the hub/parent worktree nor to any other directory — before or as part of this check; the check operates entirely via a plain existence test (e.g. `Path(worktree_root).exists()` or an equivalent `[ -d "<worktree_root>" ]` shell test) against the already-bound `worktree_root` variable from wherever the shell's cwd currently is (which may itself have already auto-recovered to a stable location if the directory was removed — no action needed on this session's own part to react to that).
- **Commit:** `mill-go-base: guard Handoff step 6 against a concurrent mill-cleanup race (#990)`

## Batch Tests

`verify:` (see frontmatter above) is a `python -c` assertion confirming the exact "already cleaned up" marker phrase and a nearby `worktree_root` reference both landed in `handoff.md`, per this plan's "prose-only batches verify via exact-marker grep/python assertions" Shared Decision in `00-overview.md`.
