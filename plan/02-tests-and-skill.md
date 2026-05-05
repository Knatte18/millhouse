# Batch: tests-and-skill

```yaml
task: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8)
batch: tests-and-skill
cards: 2
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
depends-on: [implement-cli]
```

## Batch Scope

This batch delivers the unit test suite for `millpy-implement.py` and updates `mill-go/SKILL.md` to reference the new CLI. The two cards are independent of each other (the SKILL.md update requires no test infrastructure and the tests require no SKILL.md changes), but both depend on batch 01 having delivered the CLI script.

The `verify:` command runs the full unit test suite via `run-all.py`, which auto-discovers `test-*.py` files. This catches regressions across the whole unit test corpus, not just the new test file.

No batch-local decisions beyond Shared Decisions.

## Cards

### Card 4: unit tests for millpy-implement.py

- **Reads:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_sonnet.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/unit_tests/test-millpy-validate-plan.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Deletes:** none
- **Requirements:** Create unit tests for `millpy-implement.py`. Follow the exact pattern of `test-millpy-validate-plan.py`: load the module via `importlib.util.spec_from_file_location("millpy_implement", str(_IMPLEMENT_PATH))` and call `main(argv)` in-process.

  **Test fixture helper `_make_fixture(tmp_path)`:** creates the fake worktree directory tree:
  - `tmp_path/plan/00-overview.md` — valid overview with one batch entry: `name: test-batch`, `file: 01-test-batch.md`, `depends-on: []`, `verify: null`.
  - `tmp_path/plan/01-test-batch.md` — minimal content (just a heading; not read by tests).
  - `tmp_path/status.md` — valid status.md with top yaml block (`phase: implementing`, `slug: test-slug`, `task: Test Task`, `branch: test-branch`, `parent: main`) and a `## Batches` section with one entry: `name: test-batch`, `state: pending`.
  - `tmp_path/.millhouse/config.local.yaml` — empty file or `{}`.
  - A fake wiki dir `tmp_path/wiki/` with a minimal `config.yaml` containing just `review: {code: {self_fix_rounds: 2}}`.

  **Module-level patches applied to all tests (via `setUp` or class-level):**
  - `millpy_implement._paths.resolve_git_root` → returns `tmp_path`
  - `millpy_implement._paths.resolve_wiki_path` → returns `tmp_path / "wiki"`
  - `millpy_implement._review_common.load_config` → returns `{"review": {"code": {"self_fix_rounds": 2}}, "llm": {"implementer_timeout": 1800}}`
  - `millpy_implement._active.read_slug` → returns `"test-slug"`
  - `millpy_implement._status.read_branch` → returns `"test-branch"`
  - All git `subprocess.run` calls → return a `CompletedProcess` with `returncode=0`, `stdout="abc1234\n"`, `stderr=""` (matched by checking the first argv element is `"git"`)

  Each test case sets up its own `_implementer_sonnet.run` mock return value and patches `uuid.uuid4` to return a fixed UUID (`"00000000-0000-0000-0000-000000000001"`).

  **Test 1 — initial dispatch success:**
  - Fixture batch state: `pending`.
  - Mock `_implementer_sonnet.run` → `('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")`.
  - Call `main(["test-batch"])` in a context where `Path.cwd()` is `tmp_path`.
  - Assert: exit code 0; stdout contains the success JSON line; `_status.read_batches(status_path)[0]["state"] == "running"` and `implementer_session == "00000000-0000-0000-0000-000000000001"`.

  **Test 2 — initial dispatch crash-recovery (batch already `running`):**
  - Before calling main, set the batch state to `running` via `_status.set_batch_field`.
  - Mock `run` → success JSON.
  - Assert: exit code 0; batch state is still `running`; `implementer_session` is the new fixed UUID (not an old value).

  **Test 3 — initial dispatch stuck:**
  - Mock `run` → `('{"status":"stuck","stuck_type":"verify","reason":"tests failed"}\n', "fake-session")`.
  - Call `main(["test-batch"])`.
  - Assert: exit code 0; stdout JSON has `"status": "stuck"`.

  **Test 4 — resume path success:**
  - Set batch state to `reviewing`, `implementer_session = "original-session-id"` via `_status.set_batch_field` calls.
  - Create a fake review file at `tmp_path/reviews/review.md`.
  - Mock `run` → success JSON.
  - Call `main(["test-batch", "--resume", "--round", "2", "--review-file", str(tmp_path / "reviews" / "review.md")])`.
  - Assert: exit code 0; `_implementer_sonnet.run` was called with `session_id="original-session-id"` and `resume=True`; batch state is `fixing`; `review_round == 2`.

  **Test 5 — resume LLMSessionError:**
  - Set batch state to `reviewing`, `implementer_session = "sess"`.
  - Create fake review file.
  - Mock `run` to raise `_llm_claude.LLMSessionError("session expired")`.
  - Call `main(["test-batch", "--resume", "--review-file", str(review_file)])`.
  - Assert: exit code 1; stdout JSON has `"status": "stuck"` and `"stuck_type": "transient"`.

  **Test 5b — resume bare LLMError:**
  - Same as 5 but raise `_llm_claude.LLMError("timeout")`.
  - Assert: same shape.

  **Test 6 — batch not found:**
  - Call `main(["nonexistent-batch"])`.
  - Assert: exit code 1; no JSON on stdout.

  **Test 7 — malformed JSON from implementer:**
  - Mock `run` → `("implementer output with no json\n", "sess")`.
  - Call `main(["test-batch"])`.
  - Assert: exit code 0; stdout JSON has `"status": "stuck"` and `"stuck_type": "logic"`.

  **Test 8 — --resume without --review-file:**
  - Call `main(["test-batch", "--resume"])`.
  - Assert: exit code 1; no JSON on stdout.

  For cwd isolation, use `os.chdir(tmp_path)` inside each test and restore after (use `addCleanup` or `unittest.mock.patch("os.getcwd", return_value=str(tmp_path))` — but since the CLI uses `Path.cwd()`, the cleanest approach is to actually `os.chdir` and restore via `addCleanup(os.chdir, original_cwd)`.

- **Commit:** `feat(tests): add test-millpy-implement.py`

### Card 5: update mill-go/SKILL.md

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/millpy-implement.py`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Make three targeted edits to `mill-go/SKILL.md`:

  **Edit 1 — "### 1. Implement" section:**
  Replace the block that starts with "- Resolve the batch's file path via the Batch Index entry's `file:`." and ends with the `_implementer_sonnet.run` signature line. Replace with:

  ```
  - Invoke:
    ```bash
    uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
    ```
    The CLI atomically: resolves paths and config, renders the implementer brief, generates a `session_id`, sets batch state → `running`, records `start_sha` and `implementer_session` in status.md, commits and pushes on the task branch, spawns the implementer, and prints the implementer's JSON report on stdout. The Builder reads stdout JSON directly for the Parse step.
  ```

  The commit bullet ("Commit on the task branch: `git -C <worktree> add status.md...` (no push).") is removed entirely — the CLI handles the commit and push.
  The token table and the `_render.render` bullet are removed — the CLI handles rendering.
  The `start_sha` / `implementer_session` bullets are removed — the CLI handles these.

  **Edit 2 — "### 3. Code Review loop → REQUEST_CHANGES" section:**
  Replace the block that starts with "> Load the `mill-receiving-review` skill..." (the quoted user-message block) and ends with "`_implementer_sonnet.run(fix_prompt, session_id=session_id, resume=True, cwd=project_root)`. Parse the JSON report the same way as step 2. On stuck → escalate." Replace with:

  ```
  - Invoke:
    ```bash
    uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume --round <N> --review-file <review-file-abs-path>
    ```
    The CLI reads `implementer_session` from status.md, sets batch state → `fixing`, commits and pushes, and resumes the warm implementer session with the fix prompt (which instructs the implementer to load `mill-receiving-review` and apply findings). Parse the JSON report the same way as step 2. On stuck → escalate.
  ```

  **Edit 3 — "## Board discipline" section:**
  - On every line that ends with `(no push)`, remove `(no push)` from the end. The affected lines are in the Prepare commit and the Approve commit annotations.
  - Replace the final bullet "No push from per-card commits — mill-merge pushes the task branch at task end." with: "Task-branch state commits push to `origin/<task-branch>` immediately after each `git commit`. `millpy-implement.py` handles push for batch-start and fix-cycle commits; mill-go handles push for Prepare, Approve, blocked, and done commits. Per-card implementer commits (via the `git-commit` skill) do not push — mill-merge pushes the full task branch at task end."

  Make no other changes. In particular: keep `## Holistic code review` section unchanged; keep `## Principles` section unchanged; keep all signature lines that remain accurate.

- **Commit:** `docs(mill-go): update SKILL.md — millpy-implement.py dispatch + push policy`

## Batch Tests

`verify:` runs `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. This discovers and runs all `test-*.py` files including `test-millpy-implement.py`. The full corpus run guards against regressions in other helpers that might be broken by the `_implementer_sonnet.py` timeout-parameter change from batch 01.
