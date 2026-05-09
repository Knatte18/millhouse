# Batch: cleanliness-wireup

```yaml
task: 36 (A) — Bug-fix batch 3
batch: cleanliness-wireup
number: 2
cards: 2
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Wire the `_cleanliness` helper from batch 1 into the two mill-go integration points: `millpy-implement.py` (capture the snapshot at batch start) and `mill-go` SKILL.md (use `compute_new_dirt` instead of raw `git status`). The two cards are bundled because they form a single coupling: the implement-side capture is meaningless without the gate-side diff, and the gate-side diff is meaningless without the snapshot file. `verify:` re-runs the full unit-test suite to confirm no regression in helpers the implement script uses (`_status`, `_paths`, etc.) — there is no script-level integration test for `millpy-implement.py`'s `git add` step (the script's existing tests in `test-millpy-implement.py` mock the `git` invocations and do not assert on the argv list shape; rewriting them to do so would be out of scope per discussion.md).

## Cards

### Card 8: capture pre-batch snapshot in millpy-implement

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `import _cleanliness` to the top-level import block in `plugins/mill/scripts/millpy-implement.py`, alphabetically between `import _active` (line 30) and `import _implementer_sonnet` (line 31) — so the new line lands at the second position in the underscore-prefixed import group. In the `if not args.resume:` branch (initial-dispatch path), after the line `start_sha = result.stdout.strip()` (line 129) and before the `_status.set_batch_fields(...)` call (line 133), insert two new lines:

  ```python
  snapshot_path = project_root / "task" / f".cleanliness-snapshot-{args.batch_name}.txt"
  _cleanliness.capture_snapshot(project_root, snapshot_path)
  ```

  Update the `git add` invocation that currently reads `["git", "add", "task/status.md"]` (line 136) to also stage the snapshot file. Replace the argv list with `["git", "add", "task/status.md", str(snapshot_path.relative_to(project_root))]`. The `cwd=project_root` and surrounding error-handling block stay unchanged. Do not modify the `--resume` branch (lines below ~200). Do not modify the `git add` invocation at line 221 (that one stages the review file during fix cycles, not batch-start state).

- **Commit:** `feat(implement): capture pre-batch cleanliness snapshot`

### Card 9: replace raw git status with _cleanliness in mill-go SKILL.md

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-go/SKILL.md`, locate section `### 2b. Cleanliness gate` (currently around lines 91–100). Replace the body so the section reads:

  ```markdown
  ### 2b. Cleanliness gate

  After a `success` report: compute new dirt via `_cleanliness.compute_new_dirt(<worktree>, <worktree>/task/.cleanliness-snapshot-<batch_name>.txt)`. If the returned list is non-empty (genuine implementer-introduced dirt that did not pre-date the batch):
  - `_status.set_batch_field(status_path, batch_name, "state", "blocked")`
  - `_status.set_batch_field(status_path, batch_name, "blocked_reason", "uncommitted working tree after implementer report")`
  - `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`
  - Commit on the task branch: `git -C <worktree> add task/status.md && git -C <worktree> commit -m "mill-go: blocked on <batch_name> — dirty tree"`
  - Go to *Blocked*.

  `signature: _cleanliness.compute_new_dirt(worktree: Path, snapshot_path: Path) -> list[str]`

  If the returned list is empty, continue to "3. Code Review loop" as normal.
  ```

  Preserve the `### 2b. Cleanliness gate` heading exactly. The `signature:` line must use the same one-line backtick-wrapped form as the existing signature lines elsewhere in mill-go SKILL.md (e.g. line 35: `signature: _status.read_full(status_path: Path) -> {"yaml": dict, "timeline": list[str]}`). Do not modify any other section of the file. Do not change the surrounding section headings (`### 2. Parse implementer report`, `### 3. Code Review loop`).

- **Commit:** `docs(mill-go): use _cleanliness helper in cleanliness gate`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` re-runs the full unit-test suite — including `test-cleanliness.py` from batch 1 — to confirm the imports added in card 8 do not break `millpy-implement.py`'s existing test surface. The mill-go SKILL.md edit (card 9) has no automated test surface; correctness of the markdown change is verified at code review by the reviewer reading the section against this card's requirements.
