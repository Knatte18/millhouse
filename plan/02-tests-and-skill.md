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
- **Requirements:** Create unit tests for `millpy-implement.py`. Use `unittest.TestCase` (not standalone functions) so common patches and fixture creation can live in `setUp` and be shared across tests. Load the module under test via `importlib.util.spec_from_file_location("millpy_implement", str(_IMPLEMENT_PATH))` and call `main(argv)` in-process.

  **Test fixture helper `_make_fixture(tmp_path)`** (called from `setUp`): creates the fake worktree directory tree:
  - `tmp_path/plan/00-overview.md` — valid overview with one batch entry: `name: test-batch`, `file: 01-test-batch.md`, `depends-on: []`, `verify: null`.
  - `tmp_path/plan/01-test-batch.md` — minimal content (just a heading; not read by tests).
  - `tmp_path/status.md` — valid status.md with top yaml block (`phase: implementing`, `slug: test-slug`, `task: Test Task`, `branch: test-branch`, `parent: main`), a ```` ```text ```` fenced `## Timeline` section containing at least one row (e.g. `implementing  2026-01-01T00:00:00Z`), and a `## Batches` section with one entry: `name: test-batch`, `state: pending`. The `## Timeline` block is required because `_status.append_phase` (called by the CLI in the resume path) raises `ValueError: No \`\`\`text block in status file` if it is absent.
  - `tmp_path/.millhouse/config.local.yaml` — empty file or `{}`.
  - A fake wiki dir `tmp_path/wiki/` with a minimal `config.yaml` containing just `review: {code: {self_fix_rounds: 2}}`.
  - `tmp_path/reviews/` — empty directory; per-test fixtures create review files inside as needed.

  **`setUp` (class-level patches via `addCleanup`):** `tempfile.mkdtemp()` creates `tmp_path`; `addCleanup(shutil.rmtree, tmp_path, ignore_errors=True)`. `_make_fixture(tmp_path)` populates it. Save `original_cwd = os.getcwd()`, then `os.chdir(tmp_path)` and `addCleanup(os.chdir, original_cwd)`. Apply each of the patches below via `unittest.mock.patch.object(...)` followed by `.start()` and `addCleanup(p.stop)`:
  - `millpy_implement._paths.resolve_git_root` → returns `tmp_path`
  - `millpy_implement._paths.resolve_wiki_path` → returns `tmp_path / "wiki"`
  - `millpy_implement._review_common.load_config` → returns `{"review": {"code": {"self_fix_rounds": 2}}, "llm": {"implementer_timeout": 1800}}`
  - `millpy_implement._active.read_slug` → returns `"test-slug"`
  - `millpy_implement._status.read_branch` → returns `"test-branch"`
  - `millpy_implement.subprocess.run` → return `subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")` whenever the first argv element is `"git"` (so all git operations are stubbed)
  - `millpy_implement.uuid.uuid4` → `MagicMock(return_value=uuid.UUID("00000000-0000-0000-0000-000000000001"))`. Per-test methods that need the same fixed UUID can rely on the class-level patch; tests that need a different value override locally.

  Each test method sets up its own `_implementer_sonnet.run` mock return value (or side_effect for exceptions) using `unittest.mock.patch.object(millpy_implement._implementer_sonnet, "run", ...)` inside the test body.

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
  - Create a fake review file at `tmp_path/reviews/review.md` with any text content.
  - Mock `run` → success JSON.
  - Call `main(["test-batch", "--resume", "--round", "2", "--review-file", str(tmp_path / "reviews" / "review.md")])`.
  - Assert: exit code 0; `_implementer_sonnet.run` was called with `session_id="original-session-id"` and `resume=True`; batch state is `fixing`; `review_round == 2`.
  - Inspect the captured `subprocess.run` call list and assert that the `git add` invocation contained both `"status.md"` and the review file path (relative or absolute) in its argv. This guards against regressions where the review file is silently left untracked.
  - Inspect status.md's `## Timeline` and assert the last entry begins with `fixing-test-batch-r2`. This guards against regressions where `_status.append_phase` is silently omitted from the fix-cycle path.

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

  Cwd isolation is handled in `setUp` via `os.chdir(tmp_path)` and `addCleanup(os.chdir, original_cwd)`. Test bodies do not need to manage cwd themselves.

- **Commit:** `feat(tests): add test-millpy-implement.py`

### Card 5: update mill-go/SKILL.md

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/millpy-implement.py`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Make five targeted edits to `mill-go/SKILL.md`:

  **Edit 1 — "### 1. Implement" section:**
  Replace the block that starts with "- Resolve the batch's file path via the Batch Index entry's `file:`." and ends with the `_implementer_sonnet.run` signature line. Replace with:

  ```
  - Invoke:
    ```bash
    uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
    ```
    The CLI atomically: resolves paths and config, renders the implementer brief, generates a `session_id`, sets batch state → `running`, records `start_sha` and `implementer_session` in status.md, commits and pushes on the task branch, spawns the implementer, and prints the implementer's JSON report on stdout. The Builder reads stdout JSON directly for the Parse step. Note: the CLI exits 0 when the implementer produced JSON (success or stuck). On exit code 1 the stdout still carries a `{"status":"stuck","stuck_type":"transient",...}` line if an LLM-layer failure (timeout, dead session, etc.) occurred — parse it the same way and route through Stuck escalation. Only treat exit 1 as an unrecoverable pre-launch error when stdout is empty.
  ```

  The commit bullet ("Commit on the task branch: `git -C <worktree> add status.md...` (no push).") is removed entirely — the CLI handles the commit and push.
  The token table and the `_render.render` bullet are removed — the CLI handles rendering.
  The `start_sha` / `implementer_session` bullets are removed — the CLI handles these.

  **Edit 2 — "### 3. Code Review loop → REQUEST_CHANGES" section:**
  Replace the entire `REQUEST_CHANGES` bullet block. The replacement starts at "— set batch state → `fixing`. `_status.append_phase(...)`. Commit on the task branch: `git -C <worktree> add status.md reviews/<file>...`. **Resume the implementer session** with a new user message:" (immediately after the literal `REQUEST_CHANGES` token at the start of the bullet) and ends after "`_implementer_sonnet.run(fix_prompt, session_id=session_id, resume=True, cwd=project_root)`. Parse the JSON report the same way as step 2. On stuck → escalate." This includes the blockquote (`> Load the mill-receiving-review skill...`) in between. Replace with:

  ```
  — invoke:
    ```bash
    uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume --round <N> --review-file <review-file-abs-path>
    ```
    The CLI atomically: reads `implementer_session` from status.md, sets batch state → `fixing`, calls `_status.append_phase` for `fixing-{batch_name}-r{N}`, commits and pushes (status.md plus the review file), and resumes the warm implementer session with the fix prompt (which instructs the implementer to load `mill-receiving-review` and apply findings). Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior described under "1. Implement". On stuck → escalate.
  ```

  After this edit the REQUEST_CHANGES bullet contains exactly one Invoke block — no leading state-management text, no orphaned blockquote, no orphaned spawn line.

  **Edit 3 — "## Board discipline" section:**
  - On every line whose text ends with `(no push)`, remove the trailing `(no push)` from that line (and any leading single space). The affected lines in the current SKILL.md are the Prepare commit (Prepare section) and the Handoff step-1 done commit (Handoff section). Do not search by commit-message text; the rule "remove `(no push)` from any line ending with it" is unambiguous and finds the right lines.
  - Replace the final bullet "No push from per-card commits — mill-merge pushes the task branch at task end." with: "`millpy-implement.py` pushes its own task-branch state commits (batch-start, fix-cycle) to `origin/<task-branch>` immediately after each `git commit`. The Builder's own state commits (Prepare, Approve, blocked, done) and per-card implementer commits do not push — mill-merge pushes the full task branch at task end. Adding push to the Builder's own commits is a follow-up task; this PR scopes the push policy to CLI commits only."

  **Edit 4 — "## Holistic code review" section:**
  Update the inline `_implementer_sonnet.run` signature line to include the new `timeout` parameter introduced by Card 2. Locate the signature line:

  ```
  `signature: _implementer_sonnet.run(prompt_text: str, *, session_id: str | None = None, resume: bool = False, cwd: Path | str | None = None) -> tuple[str, str]`
  ```

  Replace with:

  ```
  `signature: _implementer_sonnet.run(prompt_text: str, *, session_id: str | None = None, resume: bool = False, cwd: Path | str | None = None, timeout: int = 1800) -> tuple[str, str]`
  ```

  Change nothing else in the Holistic section. The `_implementer_sonnet.run(...)` call site itself does not need editing — the timeout parameter is optional with a default that matches the prior behavior.

  **Edit 5 — "### Stuck escalation" section:**
  The current first bullet starts: "**`LLMError` from `_llm_claude.run_implementer`** (subprocess crashed before producing a JSON report) → treat as `stuck_type: transient`. Apply the existing one-retry policy: retry once with a fresh session (new UUID, `resume=False`). If the second attempt also raises `LLMError`, escalate to user with the regular `transient` three-option prompt (retry fresh, edit plan and retry, block). Note: catch `_llm_claude.LLMError` specifically (not bare `Exception`) so genuine programmer errors still propagate."

  Replace this entire bullet with:

  "**CLI emits `stuck_type: transient`** (LLM-layer failure surfaced as the synthetic stuck JSON described in Implement step 2; the CLI exits 1 in that case but stdout carries the JSON) → apply the one-retry policy: re-invoke `millpy-implement.py <batch_name>` once with no `--resume` flag (a fresh session). If the second invocation also reports `stuck_type: transient`, escalate to user with the regular `transient` three-option prompt (retry fresh, edit plan and retry, block)."

  Make no other changes. In particular: keep `## Holistic code review` section's prose and call site unchanged (only the inline signature line is edited per Edit 4); keep `## Principles` section unchanged; keep all signature lines elsewhere that remain accurate.

- **Commit:** `docs(mill-go): update SKILL.md — millpy-implement.py dispatch + push policy`

## Batch Tests

`verify:` runs `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. This discovers and runs all `test-*.py` files including `test-millpy-implement.py`. The full corpus run guards against regressions in other helpers that might be broken by the `_implementer_sonnet.py` timeout-parameter change from batch 01.
