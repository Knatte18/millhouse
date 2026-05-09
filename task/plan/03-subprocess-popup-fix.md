# Batch: subprocess-popup-fix

```yaml
task: 39 (A) — mill-start question-format UX
batch: subprocess-popup-fix
number: 3
cards: 5
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Eliminates the Windows console-window flashes that appear during reviewer / mill-go runs by routing every non-interactive subprocess invocation through `_subprocess_util`. Two new entry points are added: a stdout/stderr override on the existing `run(...)` and a fire-and-forget `popen_detached(...)`. All bypassing call sites under `plugins/mill/scripts/` are refactored to use one of these helpers. Two interactive launchers (`millpy-terminal.py`, `millpy-vscode.py`) are explicitly exempted with a single one-line code comment marking why.

External interface emerging from this batch:

- `_subprocess_util.run(argv, *, cwd=None, input=None, check=False, timeout=None, env=None, stdout=None, stderr=None) -> subprocess.CompletedProcess[str]` — stdout/stderr default to `subprocess.PIPE` (current behaviour); when overridden, the caller's value flows directly to `subprocess.Popen`. When stdout/stderr are non-PIPE, `CompletedProcess.stdout` / `.stderr` are empty strings.
- `_subprocess_util.popen_detached(argv, *, stdin=None, stdout=None, stderr=None, cwd=None, env=None) -> subprocess.Popen` — fire-and-forget; on Windows applies `creationflags = CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`; on POSIX applies `start_new_session=True`. Caller reads `.pid` from the returned handle.

Batch-local decisions:

- **Test patch-target update is mechanical**: every existing test that patches `<module>.subprocess.run` (or `.Popen`) is updated to patch `<module>._subprocess_util.run` (or `.popen_detached`) when the production code is refactored. No new test logic.
- **Interactive-launcher exemption marker**: a single comment line — `# Interactive launcher — must keep its console; do NOT route through _subprocess_util.run.` — directly above the `subprocess.run` call. No alternative route, no helper variant.
- **Manual GUI verification is acceptable**: per the discussion's `popup-verification` decision, the popup-flash regression is verified manually on Windows (operator runs a reviewer end-to-end and confirms no flash). No automated GUI test is added.

## Cards

### Card 7: extend `_subprocess_util.run` and add `popen_detached`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Edits:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend `_subprocess_util.run`'s signature to accept two new keyword-only parameters: `stdout=None` and `stderr=None`. When `stdout is None`, the existing `popen_kwargs["stdout"] = subprocess.PIPE` default applies. When `stdout` is supplied (any file-like object, `subprocess.DEVNULL`, `subprocess.STDOUT`), pass it through to `subprocess.Popen` as-is. Same logic for `stderr`. When either override is non-PIPE, the call to `proc.communicate(...)` returns `None` for that stream; coerce those to empty strings before constructing the returned `CompletedProcess` so the return type stays `CompletedProcess[str]`. Update the docstring's `Args:` section to document the two new params, and add a one-line note: "When stdout/stderr are overridden to non-PIPE values, the returned CompletedProcess.stdout/.stderr are empty strings — capture is impossible without PIPE." Existing callers (which never pass these new params) see identical behaviour.

  Add a new public function:

  ```python
  def popen_detached(
      argv: list[str],
      *,
      stdin=None,
      stdout=None,
      stderr=None,
      cwd: Path | str | None = None,
      env: dict[str, str] | None = None,
  ) -> subprocess.Popen:
      """Fire-and-forget detached subprocess. Returns the Popen handle."""
  ```

  In its body: build `child_env = (env or os.environ).copy()` and inject `child_env["PYTHONIOENCODING"] = "utf-8"` mirroring `run`. Print a `[subprocess] popen_detached argv=...` breadcrumb to stderr. Build `popen_kwargs` with `stdin=stdin, stdout=stdout, stderr=stderr, cwd=cwd, env=child_env`. On `os.name == "nt"` set `popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000`. Use the literal `0x01000000` for `CREATE_BREAKAWAY_FROM_JOB` because the `subprocess` module does not export that constant — keep the magic number in a module-level `_CREATE_BREAKAWAY_FROM_JOB` constant declared near `_GRACE_SECONDS` for readability and reference it in the function. On POSIX (`else`) set `popen_kwargs["start_new_session"] = True`. Return `subprocess.Popen(argv, **popen_kwargs)`. Do NOT pass `text=True` / `encoding=...` / `errors=...` — detached fire-and-forget callers don't `.communicate()`, and encoded pipes that aren't drained risk deadlock.

  Update the module docstring's `Public API:` block to list `popen_detached(...)` alongside `run(...)`.
- **Commit:** `feat(_subprocess_util): add stdout/stderr overrides on run + popen_detached helper`

### Card 8: tests for the new `_subprocess_util` surface

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add new test functions to `plugins/mill/unit_tests/test-subprocess-util.py` (which already exists and tests `run`'s happy path / timeout / breadcrumb / check= behaviour):
  - `_test_run_with_stdout_override_writes_to_file`: spawn a `[sys.executable, "-c", "import sys; sys.stdout.write('hello')"]` child with `stdout=open(<tmp>, 'w', encoding='utf-8')` (the test owns the file handle); after `run` returns, assert the file contains `"hello"`, `result.returncode == 0`, and `result.stdout == ""`.
  - `_test_run_with_stderr_to_stdout_redirect`: spawn a child that writes to stderr; pass `stderr=subprocess.STDOUT` and `stdout=<file>`; assert the file contains the stderr content and `result.stderr == ""`.
  - `_test_run_default_behaviour_unchanged`: explicit regression check — call `run(["git", "--version"])` with no stdout/stderr kwargs; assert `result.stdout` non-empty (real string, not `""`); duplicates the existing happy-path check but written specifically to fence the new defaults.
  - `_test_popen_detached_returns_popen_with_pid`: call `popen_detached([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`; assert returned object is a `subprocess.Popen`, `proc.pid` is a positive int, and after `proc.wait(timeout=5)` the returncode is 0.
  - `_test_popen_detached_injects_pythonioencoding_env`: write a one-shot child python script to a tempfile that opens a file path passed via argv and writes `os.environ.get("PYTHONIOENCODING", "<missing>")` to it; spawn the child via `popen_detached(...)` with stdout/stderr=DEVNULL; `wait(timeout=5)`; read the file and assert it contains `"utf-8"`.
  - `_test_popen_detached_creationflags_on_windows`: when `os.name == "nt"`, monkey-patch `subprocess.Popen` (via `unittest.mock.patch`) to record kwargs; call `popen_detached([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`; assert the recorded `creationflags` contains all four bits (`CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | 0x01000000`). Skip the test on POSIX (`if os.name != "nt": return  # not applicable`).
  - `_test_popen_detached_start_new_session_on_posix`: when `os.name != "nt"`, monkey-patch `subprocess.Popen` to record kwargs; assert `start_new_session=True`. Skip on Windows.
  Append each new test function to the existing `tests = [...]` list in `main()` so the module's existing dispatch picks them up. Do not delete or modify the existing tests.
- **Commit:** `test(_subprocess_util): cover run overrides + popen_detached`

### Card 9: route `millpy-bg.py` through new helpers

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-bg.py`:
  - Add `import _subprocess_util` near the existing `import subprocess` (keep the bare `subprocess` import — `subprocess.STDOUT` and `subprocess.DEVNULL` constants are still referenced).
  - Replace `result = subprocess.run(cmd, stdout=log_f, stderr=subprocess.STDOUT)` at line 49 with `result = _subprocess_util.run(cmd, stdout=log_f, stderr=subprocess.STDOUT)`. The `result.returncode` usage in the next line is unchanged.
  - Replace `git_result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)` at lines 94–98 with `git_result = _subprocess_util.run(["git", "rev-parse", "--show-toplevel"])`. Drop the `capture_output=True, text=True` kwargs since `_subprocess_util.run` already provides them. The subsequent `git_result.returncode` / `git_result.stderr.strip()` / `git_result.stdout.strip()` reads work identically.
  - Replace the `subprocess.Popen(worker_argv, **popen_kwargs)` block at lines 121–136 with `proc = _subprocess_util.popen_detached(worker_argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`. Delete the local `popen_kwargs` dict, the local `DETACHED_PROCESS / CREATE_NEW_PROCESS_GROUP / CREATE_BREAKAWAY_FROM_JOB` constants, and the entire `if os.name == "nt": ... else: ...` flag block — `popen_detached` owns all of that. Keep the `print(f"pid={proc.pid} log={log_path}")` line.
  In `plugins/mill/unit_tests/test-millpy-bg.py`:
  - Update the `unittest.mock.patch.object` calls at lines 61–66 (and any sibling occurrences in the file) so the patch target is `_launcher_mod._subprocess_util` rather than `_launcher_mod.subprocess`. Specifically: `patch.object(_launcher_mod._subprocess_util, "run", return_value=...)` and `patch.object(_launcher_mod._subprocess_util, "popen_detached", return_value=...)`. The mock return values for the git rev-parse query (`_mock_git_run_result`) and the popen handle (`_mock_popen_instance`) stay valid since `_subprocess_util.run` returns a `CompletedProcess`-shaped object and `popen_detached` returns a `Popen`-shaped handle. Verify the second occurrence around line 92–94 receives the same target switch.
- **Commit:** `refactor(millpy-bg): route subprocess calls through _subprocess_util`

### Card 10: route remaining non-interactive call sites through `_subprocess_util.run`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/scripts/millpy-skills-index.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** For each production source file in **Edits:**, add `import _subprocess_util` near the existing `import subprocess` and replace every direct `subprocess.run(...)` invocation with `_subprocess_util.run(...)`. When the call site already passes `capture_output=True`, `text=True`, `encoding=...`, or `errors=...`, drop those kwargs since `_subprocess_util.run` provides them. Keep references to `subprocess.CompletedProcess`, `subprocess.STDOUT`, `subprocess.DEVNULL`, `subprocess.CalledProcessError`, and other constants/types unchanged — the bare `subprocess` import stays. Do NOT touch any `subprocess.run` calls inside test files in this card; production callers only.

  Specific call-site refactors:
  - `_implementer_common.py:19` — `subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=project_root)` → `_subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)`. Drop `capture_output=True, text=True`.
  - `_review_common.py:610` — `subprocess.run(["git", "-C", str(project_root), "diff", f"{start_sha}..HEAD", "--", rel_path], text=True, encoding="utf-8", errors="replace", capture_output=True)` → `_subprocess_util.run(["git", "-C", str(project_root), "diff", f"{start_sha}..HEAD", "--", rel_path])`. Drop the four redundant kwargs.
  - `millpy-implement.py` lines 120, 135, 144, 154, 220, 229, 239 — replace each `subprocess.run(...)` with `_subprocess_util.run(...)`. Inspect each call's kwargs and drop only those that overlap with `_subprocess_util.run`'s built-ins; keep `cwd=...`, `input=...`, `timeout=...`, `check=...`, `env=...` as-is.
  - `millpy-implement-holistic.py` lines 122, 132, 142 — same treatment.
  - `millpy-merge-in-subagent.py` lines 133, 142, 154 — same treatment.
  - `millpy-skills-index.py:27` — same treatment.

  For each test file in **Edits:**, update the `patch.object` target so the patched attribute is `_subprocess_util.run` on the module under test, not `subprocess.run`:
  - `test-millpy-implement.py:132` — change `_p(millpy_implement.subprocess, "run", ...)` to `_p(millpy_implement._subprocess_util, "run", ...)`. The `return_value=subprocess.CompletedProcess(...)` mock stays valid. If the test assertions later inspect `self.mock_subprocess_run.call_args_list` (line 242), the mock is still the same object — no further change needed.
  - `test-millpy-implement-holistic.py:143` — same: `_p(millpy_implement_holistic.subprocess, "run", ...)` → `_p(millpy_implement_holistic._subprocess_util, "run", ...)`.
  - `test-millpy-merge-in-subagent.py` — wherever the test patches `millpy_merge_in_subagent.subprocess.run` (around lines 95, 120, 157, 158, 186, 189, 192, 224, 227, 230), change the target attribute path to `millpy_merge_in_subagent._subprocess_util.run`. Keep the `subprocess.CompletedProcess(...)` return-value construction.

  Note: `test-review-common.py` patches nothing — its `subprocess.run` calls are real fixture-setup operations (git init, git add, git commit) and are NOT affected by the `_review_common.py` refactor. Do not modify `test-review-common.py`. Confirm before merging by running `python plugins/mill/unit_tests/run-all.py` (the batch's verify command).
- **Commit:** `refactor: route remaining subprocess calls through _subprocess_util`

### Card 11: mark interactive launchers exempt with a one-line comment

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-terminal.py`, immediately above the existing `subprocess.run(["cmd", "/c", "claude", "--name", selected_slug], cwd=launch_path)` call at line 112 AND above the existing `subprocess.run(["claude", "--name", selected_slug], cwd=launch_path)` call at line 114, insert this exact comment line (matching the indentation of the call below):
  ```
  # Interactive launcher — must keep its console; do NOT route through _subprocess_util.run.
  ```
  The comment goes once above each call (so two insertions in this file). Do not change the `subprocess.run(...)` invocations themselves.

  In `plugins/mill/scripts/millpy-vscode.py`, immediately above the existing `subprocess.run(code_argv)` call at line 169, insert the same one-line comment matching the call's indentation. One insertion in this file.

  Do not modify any other lines in either file. Do not add `import _subprocess_util`.
- **Commit:** `chore(launchers): mark interactive subprocess sites exempt from _subprocess_util`

## Batch Tests

Verified by running `python plugins/mill/unit_tests/run-all.py` (the batch's `verify:` command). The expanded `test-subprocess-util.py` (card 8) covers the new `run` overrides and `popen_detached` happy path / env injection / creationflags on Windows / start_new_session on POSIX. The updated `test-millpy-bg.py`, `test-millpy-implement.py`, `test-millpy-implement-holistic.py`, and `test-millpy-merge-in-subagent.py` (cards 9 and 10) preserve their existing assertions; only the patch targets shift, so the same behavioural coverage is preserved.

GUI popup-flash verification is manual: after this batch lands and is verified to pass `run-all.py`, an operator on Windows triggers a reviewer end-to-end (e.g. `mill-go` against a small task or a standalone `millpy-bg.py --slug verify -- uv run ... millpy-review-discussion.py` invocation) and visually confirms no console-window flashes appear during the run. Document the verification result in the merge commit body. No automated GUI test is added because popup behaviour is not reliably mockable.
