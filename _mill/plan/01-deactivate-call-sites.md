# Batch: deactivate-call-sites

```yaml
task: "Deactivate codeguide integration in millhouse"
batch: deactivate-call-sites
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
depends-on: []
```

## Batch Scope

Delete the two functional entry points into the codeguide plugin from mill's own skills (`git-commit`'s per-commit sync, `mill-merge-in`'s per-merge-in update), and delete the dead code that removing the first entry point leaves behind (`_parent_branch.resolve_for_codeguide` and its dedicated tests). This is the whole functional change the task is about — batch 2 only cleans up prose elsewhere that describes this behavior. No external interface changes; every edit is a deletion or a rewrite of existing prose/code, so nothing downstream (batch 2, batch 3) needs anything new from this batch beyond "the mechanism is gone," which batch 3's verify checks directly.

## Cards

### Card 1: git-commit/SKILL.md -- delete the Codeguide sync step

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete the entire `### 2. Codeguide sync (only if codeguide is initialized)` section in full -- its heading, the `resolve.py --json` invocation paragraph, the `found == false` skip-check sentence, the parent-branch-hint resolution block (including the `_parent_branch.resolve_for_codeguide` call, its bash invocation, and its Guard paragraph), the `@codeguide:codeguide-update` invocation paragraph, and the trailing "Inline mode"/"Sibling mode" bullet pair. This section runs from immediately after step 1's closing sentence (`... rather than silently skipping the lint/format step.`) through the sibling-mode bullet's closing sentence (`... the sibling has its own history.`), leaving exactly one blank line before the following `## Rules` heading. `## Rules` and everything under it is unchanged. After this deletion the file's only remaining numbered step is `### 1. Lint (language-specific)` -- do not renumber it or add a new step 2, since no other numbered step follows.
- **Commit:** `refactor(git-commit): remove codeguide sync step`

### Card 2: mill-merge-in/SKILL.md -- delete the Codeguide update step and its dependent prose

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. In the frontmatter `description:` field, replace the exact text
```text
Sync the parent branch into the current branch. Checkpoint + conflict policy + verify + codeguide-update. Safe to call standalone or as mill-merge's first step.
```
     with
```text
Sync the parent branch into the current branch. Checkpoint + conflict policy + verify. Safe to call standalone or as mill-merge's first step.
```
  2. In the paragraph immediately following the `# mill-merge-in` heading, replace the exact sentence
```text
Creates a rollback checkpoint first, resolves conflicts conservatively, replays the same batch verifies mill-go ran during implementation, and runs codeguide-update when applicable.
```
     with
```text
Creates a rollback checkpoint first, resolves conflicts conservatively, and replays the same batch verifies mill-go ran during implementation.
```
  3. In `### 1. No-op check`, replace the line
```text
No checkpoint, no verify, no codeguide-update.
```
     with
```text
No checkpoint, no verify.
```
  4. Delete the entire `### 5. Codeguide update` section -- its heading, the `_codeguide/Overview.md`-existence-check paragraph, the five-item bulleted procedure (resolving `hub_root`, the `cd`, the Skill-tool invocation, the `--parent` argument, the restoring `cd`), the "Why the explicit `cd`" rationale paragraph, and the closing "If absent -> skip silently" paragraph -- everything from the `### 5. Codeguide update` heading through the sentence `This is the documented convention in \`plugins/mill/skills/git-commit/SKILL.md\` step 2 and we follow it here for symmetry.`, leaving exactly one blank line between the preceding `### 4. Verify` content and the following heading. Then rename the heading immediately following it, `### 5.5. Commit dispatch briefs`, to `### 5. Commit dispatch briefs`. Do not renumber `### 6. Report` -- it keeps its existing number.
  5. In the (now-renumbered) Step 5's "**Why staged-only, not unscoped porcelain:**" paragraph, replace the exact clause
```text
since briefs (if added above) and codeguide docs (already staged by `codeguide_commit.py --mode inline` in Step 5) are the only two things this step ever stages or expects to find staged.
```
     with
```text
since briefs (if added above) are the only thing this step ever stages or expects to find staged.
```
  6. Delete the entire paragraph
```text
This also now picks up Step 5's inline-mode codeguide docs -- already `git add`-staged by `codeguide_commit.py --mode inline` back in Step 5, before this step runs -- which the prior `_mill/briefs`-scoped guard silently dropped whenever `_mill/briefs/` did not exist (#946).
```
     in full, collapsing the resulting double-blank-line down to a single blank line between the surrounding paragraphs.
  7. In the paragraph beginning "This step runs on the success path only", replace the exact clause
```text
Clean merges (no conflicts, no verify failures) skip steps 3 and 4 entirely, so this step gracefully handles the case where no briefs were written AND no codeguide docs were staged either -- the `git diff --cached --name-only` guard returns empty and the block no-ops.
```
     with
```text
Clean merges (no conflicts, no verify failures) skip steps 3 and 4 entirely, so this step gracefully handles the case where no briefs were written -- the `git diff --cached --name-only` guard returns empty and the block no-ops.
```
  8. In `## No-op guarantee`, replace the exact clause
```text
this skill touches no task state: no checkpoint, no verify, no codeguide-update, no output side effects.
```
     with
```text
this skill touches no task state: no checkpoint, no verify, no output side effects.
```
- **Commit:** `refactor(mill-merge-in): remove codeguide update step`

### Card 3: _parent_branch.py -- delete resolve_for_codeguide

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete the `resolve_for_codeguide` function in full -- its `def resolve_for_codeguide(status_path: Path, *, expected_slug: str | None = None) -> str | None:` signature, its docstring, and its `try: return resolve(...) except ParentBranchError: return None` body. Also remove its entry from the module's top docstring "Public API:" list -- the paragraph beginning `resolve_for_codeguide(status_path, *, expected_slug=None) -> str | None Non-interactive wrapper` through `...git-commit) that must never block on a missing parent.` Do not modify `ParentBranchError`, `resolve`, `check_liveness`, or `resolve_dead_parent`, or their own docstring entries.
- **Commit:** `refactor(_parent_branch): delete unused resolve_for_codeguide`

### Card 4: test-parent-branch.py -- remove resolve_for_codeguide tests

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-parent-branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the import line
```text
from _parent_branch import ParentBranchError, resolve, resolve_for_codeguide  # noqa: E402
```
  drop `resolve_for_codeguide`, leaving
```text
from _parent_branch import ParentBranchError, resolve  # noqa: E402
```
  Then delete these five `resolve_for_codeguide` assert/print pairs (and, for the second pair, the `nonexistent` variable it alone depends on), collapsing any resulting double-blank-line down to a single blank line between the surrounding statements each time:
  1.
```text
            assert resolve_for_codeguide(sp) == "main"
            print("PASS: resolve_for_codeguide reads parent from status.md")
```
  2.
```text
            nonexistent = Path(tmp) / "nonexistent-status.md"
            assert resolve_for_codeguide(nonexistent) is None
            print("PASS: resolve_for_codeguide returns None for a missing status.md file")
```
  3.
```text
            assert resolve_for_codeguide(sp) is None
            print("PASS: resolve_for_codeguide returns None on missing parent instead of raising")
```
  4.
```text
            assert resolve_for_codeguide(sp, expected_slug="demo-task") == "main"
            print("PASS: resolve_for_codeguide with matching expected_slug reads parent from status.md")
```
  5.
```text
            assert resolve_for_codeguide(sp, expected_slug="other-task") is None
            print("PASS: resolve_for_codeguide returns None on mismatched expected_slug instead of raising")
```
  Every `resolve(...)`, `check_liveness(...)`, and `ParentBranchError` assertion in this file is unrelated to `resolve_for_codeguide` and must be left exactly as-is, including their surrounding `sp.write_text(...)` fixture blocks.
- **Commit:** `test(_parent_branch): remove resolve_for_codeguide coverage`

## Batch Tests

`verify:` runs the full `test-parent-branch.py` file (it is the only test file affected by this batch's edits -- Card 3 deletes a function this file directly tests, and Card 4 is this same file). The remaining `resolve`/`check_liveness`/`ParentBranchError` assertions must still pass unmodified after Card 4's edits.
