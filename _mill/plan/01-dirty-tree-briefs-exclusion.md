# Batch: dirty-tree-briefs-exclusion

```yaml
task: "mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive"
batch: dirty-tree-briefs-exclusion
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

Fixes issue #885: `_implementer_common._in_scope_dirty_stuck` (`plugins/mill/scripts/_implementer_common.py:417-478`) false-blocks a legitimately successful batch with `stuck_type: logic` when a Builder-owned `_mill/briefs/*.md`/`*.out.md` file is tracked-and-dirty at finalize time (the confirmed reproduction: a blocked-then-resumed batch's round-1 brief/output filenames collide with the same batch's earlier, already-committed round-1 attempt). The fix excludes any path under `_mill/briefs/` from the gate's dirty-file scope entirely — those files are Builder bookkeeping the Builder already stages and commits itself at batch-approve/holistic-approve/handoff time, never implementer content this gate exists to police. This batch is self-contained: one function edit plus its direct unit-test coverage, no other file in the plan depends on or is affected by it.

## Cards

### Card 1: exclude `_mill/briefs/` from `_in_scope_dirty_stuck`'s dirty-file scope

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_in_scope_dirty_stuck` (`plugins/mill/scripts/_implementer_common.py:417-478`), the `owned_paths` set built from `git diff --name-only start_sha` (around line 463) currently includes every changed path with no filtering. Change the set-comprehension so any path under `_mill/briefs/` is excluded from `owned_paths` before it is used to build `dirt`. Replace this exact block:

  ```python
        owned_paths = {line for line in diff_result.stdout.splitlines() if line}
        porcelain_lines = _pygit2_util.status_porcelain(project_root, include_untracked=False)
        dirt = [line for line in porcelain_lines if line[3:] in owned_paths]
  ```

  with:

  ```python
        owned_paths = {
            line for line in diff_result.stdout.splitlines()
            if line and not line.startswith("_mill/briefs/")
        }
        porcelain_lines = _pygit2_util.status_porcelain(project_root, include_untracked=False)
        dirt = [line for line in porcelain_lines if line[3:] in owned_paths]
  ```

  Do not touch any other line inside the `try`/`except` block, and do not touch the function's return-value shape (`None`, or the `{"status": "stuck", "stuck_type": "logic", ...}` dict) — this is a scope-of-input change only.

  Update the function's docstring: immediately after the existing paragraph that begins "Unlike `_cleanliness.compute_terminal_dirt`..." and ends "...that would reintroduce the false-block this function exists to avoid.", add one new paragraph:

  ```
      `_mill/briefs/` paths are excluded from `owned_paths` entirely -- they are Builder-owned
      orchestration bookkeeping (rendered prompt / captured transcript), never implementer content
      this gate exists to police, and the Builder already stages and commits them itself at
      batch-approve/holistic-approve/handoff time (see mill-go-base/SKILL.md and holistic-review.md's
      `git add ... _mill/briefs/` commit lines). A resumed-after-blocked batch's round-1 brief/output
      filenames colliding with an earlier attempt's already-committed files must never trip this gate
      (#885).
  ```

  Do not change the docstring's `Args:`/`Returns:` sections — their contract is unchanged by this edit.
- **Commit:** `fix(implementer): exclude _mill/briefs/ from the finalize dirty-tree gate (#885)`

### Card 2: cover the `_mill/briefs/` exclusion with unit tests

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add two new numbered cases to `plugins/mill/unit_tests/test-implementer-common.py`'s `main()` function, immediately after the existing "Case 75" block (ends at the line `errors += 1` that closes its `except Exception as exc:` clause, directly before the trailing `if errors:` / `print("All _implementer_common unit tests passed.")` block that ends the function). Follow the exact fixture style Case 73/74/75 already use in this file (`tempfile.TemporaryDirectory()`, `_setup_fixture(project_root)` with no return-value binding, direct `subprocess.run([...git...], check=True, capture_output=True)` calls, `_capture_stdout(lambda: _forward_output(...))`, a `try`/`except Exception as exc:` block that increments the module-level `errors` counter on failure).

  **Case 76** — a dirty tracked `_mill/briefs/` file with no other in-scope dirt must not trip the gate:
  1. Call `_setup_fixture(project_root)` (no assignment).
  2. Create `project_root / "_mill" / "briefs"` (via `mkdir(parents=True, exist_ok=True)`) and write a file `implement-test-batch-r1.md` inside it with content `"round-1 brief content"`.
  3. `git add _mill/briefs/implement-test-batch-r1.md` then `git commit -m "blocked-time brief commit"` (both `check=True, capture_output=True`), simulating the Builder's blocked-time commit of the round's brief.
  4. Capture `batch_start_sha` via `git rev-parse HEAD` (`check=True, capture_output=True, text=True`, `.stdout.strip()`).
  5. Rewrite the same `implement-test-batch-r1.md` file's content to `"round-1 brief content, regenerated on resume"` WITHOUT committing — this is the resumed-dispatch collision from #885's reproduction.
  6. Call `_forward_output` via `_capture_stdout` with `agent_output = '{"status":"success","commit_sha":"abc","session_id":"case76"}\n'`, `start_sha=batch_start_sha`, `verify_cmd=None`, `task_dir=project_root / "_mill"`, `parent_branch="main"`.
  7. Assert `data["status"] == "success"` (the dirty `_mill/briefs/` file must not trip the gate). On success print `"PASS: case 76 - #885 dirty _mill/briefs/ file (resumed-batch round-1 collision) does not trip the batch-scoped dirty-tree gate"`; on assertion failure, print `f"FAIL: case 76 ({exc}) captured={captured!r}"` to stderr and increment `errors`, exactly mirroring Case 73/74/75's own `try`/`except` shape.

  **Case 77** — the same dirty `_mill/briefs/` file PLUS a genuinely dirty in-scope source file must still trip the gate, and the gate's reason must name the source file but never the briefs file (proves the exclusion is scoped, not a blanket disable):
  1. Repeat Case 76's steps 1-5 exactly (fresh `tempfile.TemporaryDirectory()`, fresh fixture — do not reuse Case 76's directory).
  2. Additionally write `project_root / "README.md"` with content `"genuinely uncommitted in-scope dirt"` (uncommitted, mirrors Case 74's own "never-committed dirt since start_sha" fixture shape).
  3. Call `_forward_output` via `_capture_stdout` with `agent_output = '{"status":"success","commit_sha":"abc","session_id":"case77"}\n'`, `start_sha=batch_start_sha`, `verify_cmd=None`, `task_dir=project_root / "_mill"`, `parent_branch="main"`.
  4. Assert `data["status"] == "stuck"` and `data["stuck_type"] == "logic"`.
  5. Assert `"README.md" in data.get("reason", "")`.
  6. Assert `"_mill/briefs/implement-test-batch-r1.md" not in data.get("reason", "")` — the briefs file's dirt must stay excluded even when genuine dirt is also present.
  7. On success print `"PASS: case 77 - #885 dirty _mill/briefs/ file does not mask a genuinely dirty in-scope source file, which still trips the gate"`; on assertion failure, print `f"FAIL: case 77 ({exc}) captured={captured!r}"` to stderr and increment `errors`.
- **Commit:** `test(implementer): cover _mill/briefs/ exclusion in the dirty-tree gate (#885)`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-implementer-common.py` directly (its own custom `main()`-based runner, not `unittest`). Card 2's two new cases (76, 77) are the direct TDD-relevant coverage for Card 1's change; the file's existing Case 57/73/74/75 (dirty-tree gate baseline behavior, unaffected by this exclusion) serve as the regression guard proving the exclusion is scoped correctly and does not weaken the gate for genuine in-scope dirt.
