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
- **Requirements:** `plugins/mill/unit_tests/test-subprocess-util.py` already exists and is structured as a `main()` function with inline `try/except AssertionError` blocks tagged `(c)`, `(a)`, `(b)`, `(d)`, `(e)`, accumulating into a local `failures: list[str]` and printing `PASS (<tag>): ...` / `FAIL (<tag>) ...` per block. There is no `tests = [...]` list. New test cases are added as additional inline `try/except AssertionError` blocks in `main()`, each with its own letter tag, following the existing pattern (see `(c)` at the top of `main()` as the reference shape).

  First, update the import line at line 18 from `from _subprocess_util import _GRACE_SECONDS, run` to `from _subprocess_util import _GRACE_SECONDS, run, popen_detached` so the new test bodies can call `popen_detached(...)` directly.

  Then add seven new inline blocks at the end of `main()`, before the `if failures:` block. Use letter tags `(f)` through `(l)` (skipping any tag already in use elsewhere in the file — currently none beyond `(a)`–`(e)`):
  - `(f) run with stdout override writes to file`: spawn `[sys.executable, "-c", "import sys; sys.stdout.write('hello')"]` with `stdout=open(<tmp>, 'w', encoding='utf-8')` (test owns the file handle); after `run` returns, assert the file contains `"hello"`, `result.returncode == 0`, and `result.stdout == ""`.
  - `(g) run with stderr-to-stdout redirect`: spawn a child that writes to stderr; pass `stderr=subprocess.STDOUT` and `stdout=<file>`; assert the file contains the stderr content and `result.stderr == ""`.
  - `(h) run default behaviour unchanged`: explicit regression — call `run(["git", "--version"])` with no stdout/stderr kwargs; assert `result.stdout` non-empty (real string, not `""`); duplicates `(c)`'s happy path but written to fence the new defaults.
  - `(i) popen_detached returns Popen with pid`: call `popen_detached([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`; assert the returned object is a `subprocess.Popen`, `proc.pid` is a positive int, and after `proc.wait(timeout=5)` the returncode is 0.
  - `(j) popen_detached injects PYTHONIOENCODING=utf-8`: write a one-shot child python script to a tempfile that writes `os.environ.get("PYTHONIOENCODING", "<missing>")` to a file path passed via argv; spawn it via `popen_detached(...)` with `stdout=subprocess.DEVNULL`, `stderr=subprocess.DEVNULL`; `wait(timeout=5)`; read the file and assert it contains `"utf-8"`.
  - `(k) popen_detached creationflags on Windows`: skip on POSIX with `if os.name != "nt": print("SKIP (k): not applicable on POSIX")` and continue past the block. On Windows, use `unittest.mock.patch.object(subprocess, "Popen")` to record kwargs; call `popen_detached([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`; assert the recorded `creationflags` is `(subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000)`.
  - `(l) popen_detached start_new_session on POSIX`: skip on Windows with `if os.name == "nt": print("SKIP (l): not applicable on Windows")`. On POSIX, use `unittest.mock.patch.object(subprocess, "Popen")` to record kwargs; call `popen_detached(...)`; assert `start_new_session is True` and `creationflags` is not in kwargs.

  Add `import os` and `import unittest.mock` to the existing imports at the top of the file (just below `import time`); the file does not currently import either.

  Each new block follows the existing template: `try: ... assert ... print("PASS (X): ...") except AssertionError as exc: failures.append(f"FAIL (X) ...: {exc}")`. Do not delete or modify the existing `(a)` / `(b)` / `(c)` / `(d)` / `(e)` blocks. Do not introduce a `tests = [...]` list — the existing dispatch is the inline-block pattern.
- **Commit:** `test(_subprocess_util): cover run overrides + popen_detached`

### Card 9: route `millpy-bg.py` launcher through new helpers; suppress popup in worker

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** `plugins/mill/scripts/millpy-bg.py` is split into two distinct sections at line 22 by the comment `# ── worker fast-path — stdlib only, no mill imports ──`. The worker section (lines 22–61, inside `if "--_worker" in sys.argv:`) MUST remain stdlib-only — do NOT add `import _subprocess_util` to the worker section under any circumstance. The launcher section (line 64 onward) does not have this constraint and is the only section that imports `_subprocess_util`.

  Worker section changes (line 22–52, stdlib-only invariant preserved):
  - Do NOT add any new imports. Keep `import subprocess` at line 24 unchanged.
  - At line 49, change `result = subprocess.run(cmd, stdout=log_f, stderr=subprocess.STDOUT)` to:
    ```python
    result = subprocess.run(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    ```
    `getattr(...)` returns `0` on POSIX (where `subprocess.CREATE_NO_WINDOW` does not exist), which is a no-op for `creationflags`. `subprocess.run` forwards `creationflags` directly to `subprocess.Popen`. This keeps the worker stdlib-only and adds Windows console-flash suppression for the user command spawn.

  Launcher section changes (line 64 onward):
  - Add `import _subprocess_util` after the existing `import subprocess` at line 65. Keep the bare `subprocess` import — `subprocess.STDOUT` and `subprocess.DEVNULL` constants are still referenced.
  - Replace `git_result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)` at lines 94–98 with `git_result = _subprocess_util.run(["git", "rev-parse", "--show-toplevel"])`. Drop the `capture_output=True, text=True` kwargs since `_subprocess_util.run` already provides them. The subsequent `git_result.returncode` / `git_result.stderr.strip()` / `git_result.stdout.strip()` reads work identically.
  - Replace the `subprocess.Popen(worker_argv, **popen_kwargs)` block at lines 121–136 with `proc = _subprocess_util.popen_detached(worker_argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`. Delete the local `popen_kwargs` dict, the local `DETACHED_PROCESS / CREATE_NEW_PROCESS_GROUP / CREATE_BREAKAWAY_FROM_JOB` constants, and the entire `if os.name == "nt": ... else: ...` flag block — `popen_detached` owns all of that. Keep the `print(f"pid={proc.pid} log={log_path}")` line.

  In `plugins/mill/unit_tests/test-millpy-bg.py`:
  - Tests `(a)`, `(b)`, `(c)`, `(m)` (lines 58–86, 87–107, 108–131, 218–244): update the `unittest.mock.patch.object` calls so the patch target is `_launcher_mod._subprocess_util` rather than `_launcher_mod.subprocess`. Specifically `patch.object(_launcher_mod._subprocess_util, "run", return_value=...)` for the git rev-parse mock and `patch.object(_launcher_mod._subprocess_util, "popen_detached", return_value=...)` for the worker-spawn mock. The existing mock return values (`_mock_git_run_result(...)` and `_mock_popen_instance(...)`) stay valid since `_subprocess_util.run` returns a `CompletedProcess`-shaped object and `popen_detached` returns a `Popen`-shaped handle.
  - Tests `(d)` (lines 133–161, "Windows creationflags") and `(e)` (lines 163–194, "POSIX start_new_session"): the launcher no longer passes `creationflags` or `start_new_session` directly to `Popen` — `popen_detached` sets those internally. The `mock_popen_cls.call_args[1]` no longer contains those kwargs after the refactor. Remove the four assertions that inspect `creationflags` / `start_new_session` (lines 148–156 in test (d), lines 182–189 in test (e)) and the `expected_flags` / `_concrete_path_cls` setup. Replace the assertion bodies with: in test (d), `assert mock_popen_cls.call_count == 1, "popen_detached should call Popen exactly once"` plus a confirmation that the `pid` was forwarded (`buf.getvalue()` contains `"pid=1"`); in test (e), the same shape with `pid=2`. Switch the `patch.object(_launcher_mod.subprocess, "Popen", ...)` to `patch.object(_launcher_mod._subprocess_util.subprocess, "Popen", ...)` so the underlying Popen call inside `popen_detached` is captured. Keep the `patch.object(_launcher_mod.os, "name", "nt")` / `"posix"` patches — those still gate the launcher's behaviour through helper paths the test exercises. Update the test (d) `print(f"PASS (d): Windows creationflags = {expected_flags:#010x}")` to `print("PASS (d): Windows path forwards pid via popen_detached")`, and similarly simplify (e)'s PASS message. The deeper creationflags / start_new_session coverage now lives in `test-subprocess-util.py` blocks `(k)` and `(l)`.
- **Commit:** `refactor(millpy-bg): route launcher through _subprocess_util; suppress worker popup`

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
  - `millpy-merge-in-subagent.py`:
    - Line 133 is **EXEMPT** from this refactor. The call is `subprocess.run(args.cmd, shell=True, capture_output=True, text=True, cwd=project_root)` where `args.cmd` is a single user-supplied verify-command string (not a list) executed via the shell. `_subprocess_util.run` accepts only `argv: list[str]` and has no `shell` parameter; routing this through it would type-mismatch and silently break the shell expansion the user's verify command depends on. Leave line 133 as a bare `subprocess.run(...)` and add a comment immediately above it:
      ```
      # Shell-escaped user verify command — _subprocess_util.run does not support shell=True.
      ```
      The Windows console-flash for this specific call is acceptable: the verify command is invoked once per merge-in cycle (not every reviewer dispatch) and the worker process running this code path was launched by `popen_detached` (CREATE_NO_WINDOW already set on the parent), so the child shell inherits the no-console state.
    - Lines 142 and 154 — both list-form git calls — receive the standard refactor: replace `subprocess.run(...)` with `_subprocess_util.run(...)` and drop the redundant `capture_output=True, text=True` kwargs.
  - `millpy-skills-index.py:27` — same treatment.

  For each test file in **Edits:**, update the `patch.object` target so the patched attribute is `_subprocess_util.run` on the module under test, not `subprocess.run`:
  - `test-millpy-implement.py`:
    - Line 132 (the main test class' `setUp`): change `_p(millpy_implement.subprocess, "run", ...)` to `_p(millpy_implement._subprocess_util, "run", ...)`. The `return_value=subprocess.CompletedProcess(...)` mock stays valid. The mock is still referenced as `self.mock_subprocess_run` and `self.mock_subprocess_run.call_args_list` (line 242) — the variable name stays even though the underlying attribute path changed; no other rewrites needed.
    - `class TestForwardOutput` at line 335: this class patches `_implementer_common.subprocess.run` directly in three places — line 340 (the shared `_call()` helper), line 400 (in `test_fo_7_sha_normalized`), and line 415 (in `test_fo_8_sha_git_failure`). Change all three `patch.object(_implementer_common.subprocess, "run", ...)` calls to `patch.object(_implementer_common._subprocess_util, "run", ...)`. The mocked `return_value` (subprocess.CompletedProcess(...)) stays valid because `_subprocess_util.run` returns the same shape. Without this update, the patches would go inert post-refactor and `_call()` would invoke a real `git rev-parse HEAD` against a temp directory with no git repo, breaking `test_fo_*`.
  - `test-millpy-implement-holistic.py:143` — change `_p(millpy_implement_holistic.subprocess, "run", ...)` to `_p(millpy_implement_holistic._subprocess_util, "run", ...)`. No second occurrence in this file; verify before merging.
  - `test-millpy-merge-in-subagent.py` — wherever the test patches `millpy_merge_in_subagent.subprocess.run` (around lines 95, 120, 157, 158, 186, 189, 192, 224, 227, 230), change the target attribute path to `millpy_merge_in_subagent._subprocess_util.run`. Keep the `subprocess.CompletedProcess(...)` return-value construction. Note: any test that exercises the verify-fix code path (where line 133's `shell=True` call sits in production) MUST continue to patch `millpy_merge_in_subagent.subprocess.run` (not `._subprocess_util.run`) for that single call, since line 133 stays as `subprocess.run`. Walk the file once and apply per-call: list-form git calls (lines 142, 154 in production) → `_subprocess_util` patch target; the verify-command call (line 133 in production) → keep the `subprocess` patch target. If a single test mocks the same `subprocess.run` to drive both line 133 and lines 142/154 with `side_effect=[...]`, split the mock into two: one `patch.object(...subprocess, "run", ...)` for line 133 and one `patch.object(..._subprocess_util, "run", ...)` for the rest.

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
