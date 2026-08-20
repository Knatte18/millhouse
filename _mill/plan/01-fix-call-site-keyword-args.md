# Batch: fix-call-site-keyword-args

```yaml
task: 'mill-plan Entry step 2: _config.load_config called with hub_root/worktree_root swapped vs its own signature'
batch: fix-call-site-keyword-args
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch makes the single-line fix identified in `_mill/discussion.md`: `mill-plan/SKILL.md` Entry
step 2 calls `_config.load_config(worktree_root, git_root)` positionally, which reads as swapped against
the signature quoted two lines below (`_config.load_config(hub_root: Path, worktree_root: Path) -> dict`).
The call already passes the correct values — this is a legibility fix, not a behavior change. Switching
to explicit keyword arguments (`hub_root=worktree_root, worktree_root=git_root`) makes the call read
correctly against the adjacent signature line without renaming any variable or touching `_config.py`,
`_paths.py`, or any other script. There is no external interface for a later batch to consume — this is
the whole task, one batch, one card.

## Cards

### Card 1: Keyword-arg the Entry step 2 `_config.load_config` call

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-plan/SKILL.md` Entry step 2 (the numbered step that
  begins "Load config — deep-merge..."), change the line reading:

  ```
  Call `cfg = _config.load_config(worktree_root, git_root)`.
  ```

  to:

  ```
  Call `cfg = _config.load_config(hub_root=worktree_root, worktree_root=git_root)`.
  ```

  Do not change anything else on that line or elsewhere in the step — the sentence immediately following
  it (the `pipeline.*` config-key documentation) and the `signature: _config.load_config(hub_root: Path,
  worktree_root: Path) -> dict` line at the end of the same paragraph are already correct and stay as-is.
  Do not rename the `worktree_root` local variable anywhere else in the file (bound at Entry step 1 to
  `_paths.resolve_hub_path()`, used unchanged at every other call site — `_paths.resolve_task_path`, the
  `_treeguard.check_and_restore` calls, and the `_plan_validate.run` self-run-validator call — per
  `_mill/discussion.md`'s Decisions section, a blanket rename would only relocate the same naming defect
  onto those call sites instead of fixing it). Do not touch `_config.py`, `_paths.py`, or any other script.
- **Commit:** `docs(mill-plan): keyword-arg the Entry step 2 _config.load_config call`

## Batch Tests

`verify: null` — this batch edits only prose/inline-code in a Markdown skill file (`mill-plan/SKILL.md`);
there is no runnable code path to unit-test (per `_mill/discussion.md`'s Testing section). Verification is
manual: `grep -n '_config.load_config' plugins/mill/skills/mill-plan/SKILL.md` should show the Entry step
2 call in `hub_root=worktree_root, worktree_root=git_root` keyword form, and `grep -n '\bworktree_root\b'
plugins/mill/skills/mill-plan/SKILL.md` should show the same occurrence count and wording as before the
edit everywhere else in the file — plus a full read-through confirming the edited call reads consistently
against the adjacent signature line and that the file still parses as valid Markdown (no broken code
fences or inline-code spans introduced by the edit).
