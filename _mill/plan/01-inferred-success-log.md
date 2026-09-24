# Batch: inferred-success-log

```yaml
task: "mill-go-base / mill-plan documentation gaps"
batch: "inferred-success-log"
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
depends-on: []
```

## Batch Scope

Makes step 6 of mill-go-base's `## Agent-mode dispatch` the single call site for the inferred-success audit (#1150), and fixes the stale caller reference in the helper's docstring.
Card 2 is independent of card 1 in content but shares the subject, so both live here.
No batch-local decisions differ from the overview.

## Cards

### Card 1: Consolidate the inferred-success audit call into step 6

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Agent-mode dispatch` section, three sites change.
  Locate each by its anchor text, not by line number.
  1. Step 6, the paragraph starting "**Branch on verdict:**".
     Keep its two existing sentences unchanged and add, directly after them, a new bold-titled paragraph `**Inferred-success audit (single call site).**` whose body reads as below.
     Indent the new paragraph by the same three spaces as the step's existing continuation line.

     ```text
        **Inferred-success audit (single call site).**
        Before branching, when the finalize envelope has `status: success` and `inferred: true`, call `_status.append_inferred_success_log(status_path, batch_name, round, timestamp)` (`signature: _status.append_inferred_success_log(status_path: Path, batch_name: str, round: int, timestamp: str) -> None`).
        This applies on every path that reaches step 6: plain first-turn success, clean mid-work stop (step 3(b)), and post-`incomplete` recovery (step 5.5).
        Commit the resulting `status.md` change on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: log inferred-success for {batch_name}"`), then continue with the branching below.
        When the envelope came from step 5.5's recovery, append ` (post-recovery)` to that commit message.
        Skip this call when `inferred` is absent or `false`, or when `status` is not `success` (some `inferred: true` envelopes are `status: stuck`).
        This is the only place this call is made; steps 3(b) and 5.5 defer to it.
     ```

  2. Step 3(b), the "Clean mid-work stop" `status: success` bullet.
     Replace everything after the dash following the bold `status: success` label and its parenthetical "(all cards committed and the tree is clean)" — that is, the whole inline `inferred` / `_status.append_inferred_success_log` call description through "proceed normally to step 6." — with the sentence below.
     Keep the bullet's leading `- **`status: success`** (all cards committed and the tree is clean) —` text as is.

     ```text
     proceed to step 6, whose inferred-success rule logs the audit row when `inferred` is `true`.
     ```

  3. Step 5.5 item 3, "After recovery".
     Replace the sentence beginning "A `status: success` (or inferred success) means the batch finished" (it currently carries the inline call and commit command) with the text below.
     Delete the following sentence beginning "This is a structurally separate check from the step 3(b) Clean mid-work stop call site" and the sentence "When `inferred` is absent or `false`, skip this call entirely." — a single step-6 site now catches both first-turn and resumed-turn inference by construction.
     Leave the closing sentence beginning "If the envelope is **still** `stuck_type: incomplete`" untouched.

     ```text
     A `status: success` (or inferred success) means the batch finished — step 6's inferred-success rule logs the audit row when `inferred` is `true`, with the ` (post-recovery)` commit-message suffix, then proceeds normally.
     ```

  After the edit, exactly one instruction to call `_status.append_inferred_success_log` remains in the file (the step 6 one).
  Do not change the `<VARIANT_LABEL>` placeholder, and do not edit any other section.
  `_status.py` is read-only context here; its docstring is Card 2's job.
- **Commit:** `docs(mill-go-base): make step 6 the single inferred-success audit call site`

### Card 2: Fix the stale caller reference in the append_inferred_success_log docstring

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the docstring of `append_inferred_success_log`, the paragraph "This function is the caller's explicit, separate audit-append step." ends with a sentence naming "mill-go's step 4(b) and step 6.5 call sites".
  Replace only that parenthetical clause and its verb so the sentence names the current call site, keeping the docstring's existing line-break style and touching no code.
  The clause and the words around it currently read "callers (mill-go's step 4(b) and step 6.5 call sites) call this helper themselves after" and continue on the next line with "inspecting the finalize envelope's ``inferred`` field."
  The replacement wording is:

  ```text
  the caller (step 6 of mill-go-base's Agent-mode dispatch, the single call site) calls this helper itself after
  ```

  Do not alter any other docstring line, the function signature, or the function body.
  The `mill-go-base/SKILL.md` context confirms step 6 is that call site after Card 1.
- **Commit:** `docs(status): point append_inferred_success_log docstring at mill-go-base step 6`

## Batch Tests

`verify:` runs `test-status.py` only, which imports `_status` (catching a docstring syntax slip) and exercises the existing `append_inferred_success_log` tests.
Card 1 edits markdown with no runnable surface.
