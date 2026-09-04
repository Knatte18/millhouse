# Batch: review-hygiene-fixes

```yaml
task: 'mill-start: discussion-review timeline gaps and stray orch-review.md scratch file'
batch: review-hygiene-fixes
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-phase-wait.py test-brief-commit.py test-orch-review-scratch-path.py
depends-on: []
```

## Batch Scope

This batch delivers both bugs from `_mill/discussion.md`: (1) `mill-start`'s interactive discussion-review gap-fix round starts appending a `discussion-gap-fix-r{N}` timeline row it currently omits, and (2) the `--orch` hand-off file `orch-review.md` moves from `_mill/` to `.scratch/` so it stops being invisible, untracked debris. There is no external interface the next batch consumes — this is a terminal, single-batch task. Card 2's two file edits (write side + read side of the same hand-off mechanism) are deliberately one card with one commit — see the overview's `atomic-write-read-path-change` Shared Decision — since a mismatched write/read path would break the mechanism outright.

## Cards

### Card 1: mill-start gap-fix round appends its timeline row

- **Context:**
  - `plugins/mill/unit_tests/test-phase-wait.py`
  - `plugins/mill/unit_tests/test-brief-commit.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `### Phase: Discussion Review`, step 5 (the interactive gap-fix round), locate the paragraph ending in the sentence that begins "When the final batch in this round is answered". Its current exact text is:

  ```
  When the final batch in this round is answered, write `<discussion_path>`, commit on the task branch (`git -C <worktree> add <discussion_path> <reviews_dir>/ _mill/briefs/ && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`), push, and start round N+1.
  ```

  Replace it with:

  ```
  When the final batch in this round is answered, write `<discussion_path>`, call `_status.append_phase(status_path, f"discussion-gap-fix-r{N}", _timestamp.now_utc_iso())`, commit on the task branch (`git -C <worktree> add <discussion_path> <reviews_dir>/ _mill/briefs/ <status_path> && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`), push, and start round N+1.
  ```

  This is the only change in this card: one `_status.append_phase` call inserted (mirroring step 4b's own `_status.append_phase(status_path, f"discussion-fix-r{N}", ...)` call pattern earlier in the same file, but with the `discussion-gap-fix-r{N}` label — see the overview's `gap-fix-timeline-label` Shared Decision for why that exact label, not `discussion-fix-r{N}`, is required), and `<status_path>` added to the existing commit's git-add pathspec so the phase append lands in the same commit as the discussion/review changes. Do not touch step 4b, the `--auto`/`--orch` changes section, or any other part of the file — `test-brief-commit.py`'s `test_mill_start_brief_commits` already asserts `_mill/briefs/` stays within 300 characters of the `mill-start: discussion-gap-fix` commit-message text, so keep `_mill/briefs/` in the same commit-message window it already occupies.

- **Commit:** `mill-start: append discussion-gap-fix-r{N} timeline row to status.md`

### Card 2: relocate --orch hand-off file from _mill/ to .scratch/

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/orch-review/SKILL.md`
  - `plugins/mill/skills/orch-wait/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Change every reference to the `--orch` hand-off file's location in both files from `_mill/orch-review.md` to `.scratch/orch-review.md`. This is a path-only change — do not alter the `Monitor`-wait mechanics, the forking discipline, the review-content rubric, or any other behavior in either file. Every touch point below must change; nothing else in either file changes.

  **`plugins/mill/skills/orch-review/SKILL.md` — 5 touch points:**

  1. In the intro paragraph, the clause `waiting for a file named \`orch-review.md\` to appear next to \`discussion.md\`.` becomes `waiting for a file named \`orch-review.md\` to appear at \`.scratch/orch-review.md\`.`.
  2. In Fork-side Step 1, `If \`<worktree>/_mill/orch-review.md\` already exists, halt and ask whether to overwrite` becomes `If \`<worktree>/.scratch/orch-review.md\` already exists, halt and ask whether to overwrite`. Leave the preceding `Read \`<worktree>/_mill/discussion.md\` in full` sentence untouched — `discussion.md` itself stays under `_mill/`.
  3. Under the (unchanged) `### Step 3 — Write \`orch-review.md\`` heading, replace the paragraph below it. Its current exact text is:

     ```
Write `<worktree>/_mill/orch-review.md` (next to `discussion.md`, never inside `_mill/reviews/` — that directory is reserved for the canonical, timestamped files the worker's `finalize()` call produces) in the exact format `plugins/mill/templates/review-output.schema.md` documents:
     ```

     Replace it with:

     ```
Write `<worktree>/.scratch/orch-review.md` (gitignored ephemeral scratch space per `mill:conversation`'s convention — never inside `_mill/` at all, and specifically never inside `_mill/reviews/`, which is reserved for the canonical, timestamped files the worker's `finalize()` call produces) in the exact format `plugins/mill/templates/review-output.schema.md` documents:
     ```

  4. In Fork-side Step 4's example report message, `Wrote _mill/orch-review.md for <slug>.` becomes `Wrote .scratch/orch-review.md for <slug>.` (rest of that message unchanged).
  5. In the `## Rules` section, the "One file, one purpose, per fork" bullet's `_mill/orch-review.md` becomes `.scratch/orch-review.md`.

  **`plugins/mill/skills/orch-wait/SKILL.md` — 5 touch points:**

  1. In Step 1, the quoted status message ``"Waiting for orchestrator review -- write _mill/orch-review.md next to discussion.md to resume."`` becomes ``"Waiting for orchestrator review -- write .scratch/orch-review.md to resume."`` (drop "next to discussion.md" — it is no longer physically adjacent).
  2. In Step 2, `poll every 30 seconds for \`<worktree_root>/_mill/orch-review.md\` to exist` becomes `poll every 30 seconds for \`<worktree_root>/.scratch/orch-review.md\` to exist`.
  3. In Step 3's lead sentence, `Read \`<worktree_root>/_mill/orch-review.md\` in full as \`raw_text\`` becomes `Read \`<worktree_root>/.scratch/orch-review.md\` in full as \`raw_text\``.
  4. In Step 3's code fence, the line `raw_text = open(worktree_root / '_mill/orch-review.md', encoding='utf-8').read()` becomes `raw_text = open(worktree_root / '.scratch/orch-review.md', encoding='utf-8').read()`.
  5. Under the (unchanged) `## Step 4 — Remove the trigger file` heading, replace the paragraph below it. Its current exact text is:

     ```
`<worktree_root>/_mill/orch-review.md` is ephemeral and never committed — delete it now that `finalize()` produced the canonical copy, so it can't be mistaken for a fresh one on a later task.
     ```

     Replace it with:

     ```
`<worktree_root>/.scratch/orch-review.md` is ephemeral, gitignored, and never committed — delete it now that `finalize()` produced the canonical copy, so it can't be mistaken for a fresh one on a later task.
     ```

- **Commit:** `mill-start: relocate --orch hand-off file from _mill/ to .scratch/`

### Card 3: regression-lock the .scratch/ hand-off path

- **Context:**
  - `plugins/mill/unit_tests/test-brief-commit.py`
  - `plugins/mill/skills/orch-review/SKILL.md`
  - `plugins/mill/skills/orch-wait/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-orch-review-scratch-path.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Create `plugins/mill/unit_tests/test-orch-review-scratch-path.py`, following `test-brief-commit.py`'s text-regression-lock style (module docstring naming the batch/card, `HUB`/`SKILLS` path constants via `Path(__file__).resolve().parent.parent.parent.parent`, one `test_*` function per file returning a `list[str]` of failure messages, a `main()` that runs them and prints `PASS:`/`FAIL:` lines, `sys.exit(main())` under `if __name__ == "__main__":`). No new helper module — this is a standalone script mirroring `test-brief-commit.py`'s existing shape exactly.

  Implement one function `test_scratch_path_migration() -> list[str]` that, for each of `plugins/mill/skills/orch-review/SKILL.md` and `plugins/mill/skills/orch-wait/SKILL.md`:
  - reads the file's text (append a failure message and continue to the next file on `UnicodeDecodeError`/`OSError`, matching `test-brief-commit.py`'s own read-error handling — do not raise);
  - asserts the literal substring `.scratch/orch-review.md` appears at least once — on failure, append `f"FAIL: {path}: expected '.scratch/orch-review.md' to appear at least once, found 0 occurrences"`;
  - asserts the literal substring `_mill/orch-review.md` does NOT appear (0 occurrences) — on failure, append `f"FAIL: {path}: found {n} occurrence(s) of stale '_mill/orch-review.md', expected 0"` where `n` is the actual count.

  `main()` runs `test_scratch_path_migration()`, prints each failure to stderr, prints a `PASS:`/`FAIL:` summary line (mirroring `test-brief-commit.py`'s `main()` structure), and returns `0` on an empty failure list or `1` otherwise.

- **Commit:** `unit_tests: add regression lock for orch-review .scratch/ path`

## Batch Tests

`verify:` runs three targeted files via `run-all.py --only`, not the full suite:
- `test-phase-wait.py` — already asserts `discussion-gap-fix-r{N}` matches the Entry-gate wait's regex set; Card 1 makes that pattern reachable in practice.
- `test-brief-commit.py` — already asserts the `mill-start: discussion-gap-fix` commit message keeps `_mill/briefs/` in its git-add pathspec; Card 1's edit must not break this.
- `test-orch-review-scratch-path.py` — new in Card 3, regression-locks Card 2's path migration.

No other existing test file references `orch-review`, `orch_review`, `discussion-gap-fix`, or `_mill/briefs/` in a way this batch's edits could affect (confirmed via `discussion.md`'s Technical context grep), so the narrower `--only` scope is correct and complete for this batch.
