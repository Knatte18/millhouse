# Batch: wire-guard-backends

```yaml
task: '63 (A) — Reviewer tool-sandbox: git snapshot guard + fix --allowedTools'
batch: wire-guard-backends
number: 2
cards: 3
verify: python plugins/mill/unit_tests/test-review-plan-flow.py && python plugins/mill/unit_tests/test-review-code-flow.py && python plugins/mill/unit_tests/test-review-discussion-flow.py
depends-on: [1]
```

## Batch Scope

Wire each of the three review-backend `run()` functions to enter `worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]])` around the existing body. The guard catches any HEAD or working-tree change introduced by a reviewer LLM call. The reviews_dir entry in `expected_paths` lets `write_review_file`'s legitimate untracked output pass through. Existing per-backend control flow (parallel `ThreadPoolExecutor` fan-out, holistic call, NEED_CONTEXT resume retries, error-tail handling) is preserved unchanged.

Depends on batch 1's `worktree_snapshot_guard` and `ReviewerOverstepError`. The existing flow tests (`test-review-plan-flow.py`, `test-review-code-flow.py`, `test-review-discussion-flow.py`) run the backends end-to-end via `_reviewer_test_stub`, which never mutates git — but the existing fixtures `git init` without committing, so `git rev-parse HEAD` would return exit 128 inside the new guard. Each card in this batch also seeds an initial commit at every `git init` call site in the corresponding flow-test file so the guard can capture a valid HEAD before the wrapped body runs.

External interface: no public-API change. `run()` continues to return `ReviewResult` or raise `ReviewError`; `ReviewerOverstepError` propagates as a `ReviewError` to the API-layer catch sites in `millpy-review-*.py`.

## Cards

### Card 3: Wrap _review_plan.run() body in worktree_snapshot_guard + seed flow-test fixture

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. In `_review_plan.py`, add `worktree_snapshot_guard` to the existing import block from `_review_common`:

     ```python
     from _review_common import (
         # ... existing imports ...
         worktree_snapshot_guard,
     )
     ```

     Preserve alphabetical ordering within the import tuple if present; otherwise append.

  2. Locate the existing `def run(cfg, slug, mill_dir, wiki_root, project_root, *, max_rounds=None, holistic_only=False, no_holistic=False) -> ReviewResult:` function. Currently the body starts with the `if holistic_only and no_holistic:` precondition check (line 284). The validation check must remain BEFORE the guard (a precondition failure should not consume a snapshot). Everything from `# 1. Paths and round` (line 287) through the closing `return ReviewResult(...)` (line 622-628) is the body to wrap.

  3. Wrap that body in `with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):`. Indent the wrapped body one level. The final `return ReviewResult(...)` lives inside the with-block.

  4. Do not add any `try/except ReviewerOverstepError` — let it propagate as a `ReviewError` to the API-layer catch in `millpy-review-plan.py`. Existing `except ReviewError` sites continue to work because of the subclass relationship.

  5. ASCII rule: no new `print()` strings are added in this card. The guard helper raises with an already-ASCII message.

  6. **Seed an initial commit in the flow-test fixture.** In `test-review-plan-flow.py`, locate `_make_plan_fixture` (around line 90). Currently it runs `git init` and `git checkout -b hanf/<SLUG>` but never commits — `git rev-parse HEAD` therefore returns exit 128 on the fresh worktree, which the new guard's `_capture_head_sha` would surface as a `ReviewError` before the wrapped body runs. After the existing `git checkout -b` line, add a seed commit:

     ```python
     subprocess.run(["git", "-C", str(worktree), "config", "user.email", "test@example.com"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(worktree), "config", "user.name", "test"], check=True, capture_output=True)
     (worktree / ".gitignore").write_text("\n", encoding="utf-8")
     subprocess.run(["git", "-C", str(worktree), "add", ".gitignore"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(worktree), "commit", "-m", "seed"], check=True, capture_output=True)
     ```

     Place the block immediately after the `git checkout -b` call and before any later fixture work (mill_dir creation, wiki seeding, etc.). The `.gitignore` choice is intentional — it's a real file the seed commit needs and matches how live worktrees behave. If a `.gitignore` is later written by other fixture code, the second write+add+commit overwrites/extends harmlessly.

     If the file contains additional `git init` call sites not routed through `_make_plan_fixture`, apply the same seed-commit pattern to each before any review-backend `run()` is invoked. (Per the current code, only `_make_plan_fixture` does git init in this file; verify by grep.)

- **Commit:** `feat(_review_plan): wrap run() in worktree_snapshot_guard + seed flow-test fixture`

### Card 4: Wrap _review_code.run() body in worktree_snapshot_guard + seed flow-test fixtures

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. In `_review_code.py`, add `worktree_snapshot_guard` to the existing import block from `_review_common`.

  2. Locate `def run(cfg, slug, mill_dir, wiki_root, project_root, *, max_rounds=None, batch_name=None, extra_files=None) -> ReviewResult:`. The entire body — from `# 1. Paths + round counter` to the final `return ReviewResult(...)` — is wrapped in `with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):`. The wrapped block covers the NEED_CONTEXT resume retry path on both happy and error branches.

  3. The early-exit `except LLMError` branch (around line 318) that returns a `ReviewResult` with `verdict: ERROR` is inside the guard block — preserved as-is. The guard checks state on with-block exit regardless of which return path is taken, so the LLMError early-return is still snapshot-validated.

  4. Same propagation rule as card 3: do not catch `ReviewerOverstepError` locally.

  5. **Seed initial commits in every `git init` call site in `test-review-code-flow.py`.** This file has multiple call sites — the shared `_make_fixture` helper around line 90 plus inline `git init` calls inside individual tests (around lines 265, 331, 466, 685). For EACH `git init` invocation in the file, add a seed-commit block immediately after (and after any subsequent `git checkout -b` call, if present):

     ```python
     subprocess.run(["git", "-C", str(worktree_or_project_root), "config", "user.email", "test@example.com"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(worktree_or_project_root), "config", "user.name", "test"], check=True, capture_output=True)
     (worktree_or_project_root / ".gitignore").write_text("\n", encoding="utf-8")
     subprocess.run(["git", "-C", str(worktree_or_project_root), "add", ".gitignore"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(worktree_or_project_root), "commit", "-m", "seed"], check=True, capture_output=True)
     ```

     Substitute `worktree_or_project_root` with whichever local variable each site uses (`worktree`, `project_root`, etc.). For inline-test sites that already write a `.gitignore` or another initial file before committing, reuse that file in the seed-commit (do not add a duplicate `.gitignore`). For inline-test sites that already perform `git add` + `git commit` later in the test setup (e.g. the existing `["git", "-C", str(project_root), "commit", "-m", "initial a.py"]` around line 808), no separate seed commit is needed at that site — the existing commit IS the seed; just ensure the commit happens BEFORE the `code_run(...)` invocation. Verify by grep across the file: every `git init` either has a subsequent `git commit` before any `code_run` / `run` call, or gets the seed block above.

     This pattern is repeated rather than factored into a helper because the inline tests have site-specific needs (different file names, different commit messages) and factoring would obscure them. If three or more sites end up byte-identical, hoist them to a `_seed_repo(path)` helper at the top of the file.

- **Commit:** `feat(_review_code): wrap run() in worktree_snapshot_guard + seed flow-test fixtures`

### Card 5: Wrap _review_discussion.run() body in worktree_snapshot_guard + seed flow-test fixture

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. In `_review_discussion.py`, add `worktree_snapshot_guard` to the existing import block from `_review_common`.

  2. Locate `def run(cfg, slug, mill_dir, project_root, wiki_root, *, max_rounds=None) -> ReviewResult:`. Note the parameter order here differs from `_review_plan`/`_review_code` — `project_root` is the 4th positional, `wiki_root` is the 5th. Pass the correct one to the guard (`project_root`).

  3. Wrap the entire body — from `# 1. Resolve paths` to the final `return ReviewResult(...)` — in `with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):`.

  4. The existing `try: raw, session_id = _reviewer_single.run(spec, prompt_text)` / `except LLMError as exc: raise ReviewError(f"All sub-reviews failed: {exc}") from exc` block is inside the guard — when `LLMError` is caught and re-raised as `ReviewError`, propagation past the guard's `__exit__` will still cause the guard to re-raise the original exception (the `except Exception: raise` branch in the helper). On normal return, the guard then performs the after-snapshot check. Both behaviours are correct.

  5. **Seed an initial commit in the flow-test fixture.** In `test-review-discussion-flow.py`, locate `_make_fixture` (around line 31). Currently it runs `git init` (around line 39) but never commits. After the existing `git init` call (and any subsequent `git checkout -b` call, if present), insert:

     ```python
     subprocess.run(["git", "-C", str(worktree), "config", "user.email", "test@example.com"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(worktree), "config", "user.name", "test"], check=True, capture_output=True)
     (worktree / ".gitignore").write_text("\n", encoding="utf-8")
     subprocess.run(["git", "-C", str(worktree), "add", ".gitignore"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(worktree), "commit", "-m", "seed"], check=True, capture_output=True)
     ```

     Apply the same pattern to any additional `git init` call sites in the file (verify by grep). The seed commit must land before any `_review_discussion.run` invocation so `git rev-parse HEAD` succeeds inside the guard.

- **Commit:** `feat(_review_discussion): wrap run() in worktree_snapshot_guard + seed flow-test fixture`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-review-plan-flow.py && python plugins/mill/unit_tests/test-review-code-flow.py && python plugins/mill/unit_tests/test-review-discussion-flow.py`

The three flow tests run each backend end-to-end against `_reviewer_test_stub`, which never mutates git. Adding the guard plus the fixture seed-commit must not change any test outcome — same PASS lines as before this batch. Any new FAIL means either: an import error; a parameter mismatch (especially the `_review_discussion.run` positional-arg ordering); a stub fixture that accidentally writes outside `_mill/reviews/`; or a missed `git init` site whose seed commit was not added (`ReviewError: git rev-parse HEAD failed`). The seed-commit edit is intentionally per-site rather than mocked because the guard's HEAD check is a real subprocess call and must observe a real commit.

No new unit test file is needed in this batch — the guard helper itself is covered by `test-review-guard.py` (batch 1). The flow tests verify the wiring does not regress existing behaviour.
