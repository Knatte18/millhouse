# Batch: Code Fixes and Tests

```yaml
task: 'Fix implement finalize correctness: mid-batch stop recovery, commit-count guard, and empty-commit detection'
batch: Code Fixes and Tests
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

This batch fixes three bugs in `_implementer_common.py` — the `_batch_completeness_stuck` helper and the `_forward_output` finalize orchestrator — then adds eight unit tests to `test-implementer-common.py` covering the new behaviour. All changes are self-contained within the mill plugin's scripts and unit-tests directories. Batch 2 (docs) depends on this batch for the `commits_made` field to exist before the SKILL.md documents it.

## Cards

### Card 1: Fix `_batch_completeness_stuck` — gate-disable and `commits_made` field

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Modify `_batch_completeness_stuck(project_root, start_sha, card_count, session_id)` in `_implementer_common.py`:
  1. Add a new keyword-only parameter `verify_cmd=None` after `session_id`. Signature becomes `_batch_completeness_stuck(project_root, start_sha, card_count, session_id, verify_cmd=None)`.
  2. Insert an early-return guard at the top of the function body (after the docstring / any comment, before the `git rev-list` call): `if verify_cmd is not None: return None`. This disables the gate entirely when a verify command is present; a passing verify is conclusive evidence of batch completeness.
  3. In the existing stuck-dict construction (`count < card_count` branch), add `"commits_made": count` to the returned dict, where `count` is the integer result of `git rev-list --count {start_sha}..HEAD`. The key must appear alongside the existing `"status"`, `"stuck_type"`, and `"reason"` keys. This field enables the mill-go SKILL's `commits_made > 0` routing path (Stuck escalation) which currently never fires because the field is absent.
  Do NOT modify any call sites in this card — that is Card 2's responsibility.
- **Commit:** `fix(implement): gate-disable completeness check on verify_cmd; add commits_made to stuck dict`

---

### Card 2: Fix empty-commit guard and update all four `_batch_completeness_stuck` call sites

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  All changes are in `_implementer_common.py`. Cards 1 and 2 both edit this file; use a combined commit (later card's Commit: message) if preferred.

  **A. Add private helper `_is_only_start_batch_commit`.**
  Add the following helper function near `_batch_completeness_stuck` (any position in the file that is logically grouped with other finalize helpers):
  ```python
  def _is_only_start_batch_commit(project_root: Path, start_sha: str) -> bool:
      """Return True when the only commit since start_sha is the batch-start housekeeping commit.

      Detects Bug #557: prepare makes a "mill-go: start batch" commit, so HEAD != start_sha
      even when the implementer wrote zero code commits. A single-card retry has start_sha ==
      the start-batch commit, so its real code commit message will NOT start with the prefix.
      Returns False on any subprocess failure so the guard is always safe to skip on error.
      """
      result = _subprocess_util.run(
          ["git", "log", "--pretty=%s", f"{start_sha}..HEAD"],
          cwd=project_root,
      )
      if result.returncode != 0:
          return False
      msgs = [m.strip() for m in result.stdout.strip().splitlines() if m.strip()]
      return len(msgs) == 1 and msgs[0].startswith("mill-go: start batch")
  ```

  **B. Extend parsed-success empty-commit guard (lines 659–677).**
  The current guard at lines 659–677 checks `result.stdout.strip() == start_sha`. After this check, add a branch for the start-batch-commit-only case: when `HEAD != start_sha`, call `_is_only_start_batch_commit(project_root, start_sha)`. If it returns True, emit:
  ```python
  print(json.dumps({
      "status": "stuck",
      "stuck_type": "logic",
      "reason": "success reported but no content commit (only batch-start commit since start_sha)",
      "session_id": session_id or parsed.get("session_id"),
  }))
  return 0
  ```
  The guard must fire before the completeness gate (line 683) to emit stuck/logic rather than stuck/transient.

  **C. Update parsed-success completeness call site (line 683).**
  Change `_batch_completeness_stuck(project_root, start_sha, card_count, _gate_session_id)` to `_batch_completeness_stuck(project_root, start_sha, card_count, _gate_session_id, verify_cmd=verify_cmd)`.

  **D. Update inference formatter-drift completeness call site (line 779) and add guard before its success emit (line 802).**
  - Line 779: change the call to pass `verify_cmd=verify_cmd`.
  - Before the inferred-success print at line 802 (inside the `else: print(json.dumps({"status": "success", "commit_sha": new_head, ...}))` block), add the guard:
    ```python
    if _is_only_start_batch_commit(project_root, start_sha):
        print(json.dumps({
            "status": "stuck",
            "stuck_type": "logic",
            "reason": "inferred success but only batch-start commit since start_sha",
            "session_id": session_id or "unknown",
            "inferred": True,
        }))
        return 0
    ```

  **E. Update inference clean-tree completeness call site (line 832) and add guard before its success emit (line 851).**
  - Line 832: change the call to pass `verify_cmd=verify_cmd`.
  - Before the inferred-success print at line 851 (inside the `else` of `if violations`), add the same guard as in D (using `head` as commit_sha context for the log message, but the guard just emits stuck/logic so commit_sha is not included).

  **F. Update inference no-snapshot completeness call site (line 888) and add guard before its success emit (line 894).**
  - Line 888: change the call to pass `verify_cmd=verify_cmd`.
  - Before the inferred-success print at line 894, add the same guard as in D and E.

  The three inference guards in D, E, F all use `start_sha` which is already in scope at each emit point.

- **Commit:** `fix(implement): extend empty-commit guard to catch start-batch-commit-only; update all four completeness call sites`

---

### Card 3: Add unit tests — cases 36–43

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Append eight new test cases (36–43) after the existing Case 35 in `test-implementer-common.py`. Follow the existing functional style: each case is a try/except block, `errors += 1` on failure, `print("PASS: case N ...")` on success. Use `_setup_fixture()` and the real-git-repo pattern from existing cases. For `_forward_output` calls, use the minimal kwargs already established in existing cases (pass `card_count`, `session_id`, `start_sha`, and any case-specific overrides; omit optional params that default to None).

  **Case 36 — Bug #557 (parsed success, start-batch commit only → stuck/logic):**
  Use `_setup_fixture()` to get a real git repo. Capture `pre_start_sha = subprocess.run(["git", "rev-parse", "HEAD"], ...).stdout.strip()`. Make one commit to the repo with message `"mill-go: start batch test-batch"` (this simulates the prepare stage's housekeeping commit). Call `_forward_output` with `output='{"status":"success","commit_sha":"..."}', start_sha=pre_start_sha`. Assert the printed JSON has `"status": "stuck"` and `"stuck_type": "logic"` and `"reason"` contains `"no content commit"`.

  **Case 37 — Bug #557 (start commit + code commit → success, guard does not fire):**
  Same setup. Capture `pre_start_sha`. Make the "mill-go: start batch test-batch" commit. Make a second commit with a real code-change message. Call `_forward_output` with `output='{"status":"success","commit_sha":"..."}', start_sha=pre_start_sha`. Assert `"status": "success"`.

  **Case 38 — Bug #557 (retry scenario: start_sha = start-batch commit, one code commit → success):**
  Same setup. Make the "mill-go: start batch test-batch" commit and capture its SHA as `start_sha` (this is the retry scenario where `skip_start_commit` already ran and start_sha points at the housekeeping commit). Make a real code commit. Call `_forward_output` with `output='{"status":"success","commit_sha":"..."}', start_sha=start_sha` (pointing at the start-batch commit, NOT pre-start). Assert `"status": "success"` (the guard must NOT fire because the code commit message does not start with "mill-go: start batch").

  **Case 39 — Bug #557 (inference path, start-batch commit only, snapshot present → stuck/logic):**
  Use `_setup_fixture()`. Write an empty or trivially correct snapshot file (e.g. write the output of `git status --porcelain --untracked-files=no` to a tempfile — it will be empty for a clean repo). Capture `pre_start_sha`. Make the "mill-go: start batch test-batch" commit. Leave the tree clean. Call `_forward_output` with `output="no json here"` (non-JSON), `start_sha=pre_start_sha`, `snapshot_path=<the snapshot file>`. The inference path should fire (HEAD != pre_start_sha, tree clean, snapshot-present branch), hit the `_is_only_start_batch_commit` guard, and emit stuck/logic. Assert `"status": "stuck"` and `"stuck_type": "logic"`. This exercises the snapshot-present clean-tree emit path (line ~851), NOT the no-snapshot path.

  **Case 40 — Bug #548 (completeness gate disabled when verify_cmd is not None):**
  Call `_batch_completeness_stuck` directly (not via `_forward_output`). Use `_setup_fixture()`. Capture `start_sha`. Make one commit (card_count will be 2, so 1 < 2 would normally fire). Call `_batch_completeness_stuck(project_root, start_sha, card_count=2, session_id="test", verify_cmd="should-not-be-called")`. Assert return value is `None` (gate disabled regardless of whether `verify_cmd` is a valid command).

  **Case 41 — Bug #548 (regression guard: gate fires when verify_cmd is None):**
  Call `_batch_completeness_stuck` directly. Same setup as Case 40 (one commit, card_count=2). Call with `verify_cmd=None`. Assert return value is a dict with `"status": "stuck"` and `"stuck_type": "transient"`.

  **Case 42 — Bug #545/#560 (commits_made: 2 in stuck dict):**
  Call `_batch_completeness_stuck` directly. Use `_setup_fixture()`. Capture `start_sha`. Make two commits. Call `_batch_completeness_stuck(project_root, start_sha, card_count=3, session_id="test")`. Assert return value has `"commits_made": 2`.

  **Case 43 — Bug #545/#560 (commits_made: 0 when no commits since start_sha):**
  Call `_batch_completeness_stuck` directly. Use `_setup_fixture()`. Capture `start_sha = git rev-parse HEAD` (no commits made after). Call `_batch_completeness_stuck(project_root, start_sha, card_count=3, session_id="test")`. Assert return value has `"commits_made": 0` and `"status": "stuck"` and `"stuck_type": "transient"`.

- **Commit:** `test(implement): cases 36-43 for empty-commit guard, completeness gate-disable, and commits_made field`

## Batch Tests

`verify:` runs `test-implementer-common.py` directly (single file, no `run-all.py`). This file covers all `_implementer_common.py` logic including the three changed surfaces: `_batch_completeness_stuck`, `_forward_output` empty-commit guard, and `_forward_output` inference-path guards. New cases 36–43 provide targeted regression coverage. Scope is narrow and appropriate — no cross-cutting helper is touched so the full suite is not needed.
