# Batch: foundation

```yaml
task: Green the unit test suite on wiki-v3-adoption so it can merge to main
batch: foundation
number: 1
cards: 7
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-daemon.py
depends-on: []
```

## Batch Scope

This batch delivers the production-code change to `WikiServer.on_stop` (close logging handlers) and the daemon idle-override env var, plus the two new `_test_helpers` helpers (`wait_for_daemon_exit`, `init_wiki_repo`) and a `seed_task` option for the existing `_make_task_worktree` helper, plus one regression test for the on_stop change. After this batch lands, batch 2 can update fixture call sites with no surface ambiguity.

External interface batch 2 consumes:

- `_test_helpers.wait_for_daemon_exit(wiki_path: Path, *, timeout: float = 5.0) -> None`
- `_test_helpers.init_wiki_repo(wiki_path: Path) -> None`
- `_test_helpers._make_task_worktree(..., seed_task: bool = False)` -- when True, calls `init_wiki_repo` then `wiki.upsert_task(wiki_path, slug, title=title, status=phase)` after creating the wiki directory; raw Home.md write is still performed so non-client-using assertions keep working.
- `_test_helpers.safe_temp_dir()` -- existing context manager extended to auto-wait for any wiki daemon whose state file sits under the tempdir before invoking `safe_rmtree` on exit. Test files that currently use `tempfile.TemporaryDirectory()` migrate to `safe_temp_dir()` in batch 2 (one-line search/replace per file) so they inherit the wait-then-clean teardown without per-block boilerplate.
- `WIKI_DAEMON_IDLE_TIMEOUT` env var honored by `wiki/_server.py`'s `__main__`, defaulted to `"1"` by `_test_helpers` at module import (every test file imports `_test_helpers` already).

Batch-local decision: the regression test for `WikiServer.on_stop` lives in `test-wiki-daemon.py` (already on the `ALLOWED_FILES` whitelist in `test-no-direct-rmtree.py`, so the test may use the safe-rmtree helper without further allowlist edits). No new test file is created.

Batch-local decision: centralising the daemon-exit wait inside `safe_temp_dir` (Card 7) keeps fixture call sites unchanged across the suite. Tests that already use `safe_temp_dir` get the wait for free; tests using bare `tempfile.TemporaryDirectory()` migrate via simple constructor rename in batch 2.

## Cards

### Card 1: WikiServer.on_stop closes logging handlers before returning

- **Context:**
  - `plugins/mill/scripts/_daemon.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify `WikiServer.on_stop` (currently `plugins/mill/scripts/wiki/_server.py:79-81`) so that, after the existing `self._log.info("wiki-server stopping")` line, it iterates `list(self._log.handlers)` and for each handler calls `handler.close()` inside a `try/except Exception: pass` (best-effort) and then `self._log.removeHandler(handler)`. Iterate over `list(...)` because `removeHandler` mutates `self._log.handlers`. The log line MUST be emitted BEFORE the handlers are closed so the shutdown line lands in the file. No other method on `WikiServer` changes. No new imports. ASCII-only log string. Method docstring stays one line, updated to "Log shutdown and release log handlers." or similar.
- **Commit:** `fix(wiki-daemon): close log handlers in WikiServer.on_stop to release Windows file lock`

### Card 2: wiki/_server.py __main__ honors WIKI_DAEMON_IDLE_TIMEOUT env var

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `if __name__ == "__main__":` block (currently `plugins/mill/scripts/wiki/_server.py:332-336`), change the `idle_timeout` resolution so the precedence is: (1) `os.environ.get("WIKI_DAEMON_IDLE_TIMEOUT")` if present and parseable as `int`, else (2) `int(sys.argv[2])` if `len(sys.argv) > 2`, else (3) `600`. `refresh_interval` resolution stays unchanged. Add no new imports (`os` is already imported at line 4). If `WIKI_DAEMON_IDLE_TIMEOUT` is set but cannot be parsed as int, fall through to the argv / default chain silently (do not raise on bad env-var content -- tests should not be able to abort the daemon by setting garbage). The client launcher `_client._spawn_server` is NOT modified in this card.
- **Commit:** `feat(wiki-daemon): honor WIKI_DAEMON_IDLE_TIMEOUT env var for idle override`

### Card 3: add wait_for_daemon_exit helper to _test_helpers

- **Context:**
  - `plugins/mill/scripts/_daemon.py`
- **Edits:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a public function `wait_for_daemon_exit(wiki_path: Path, *, timeout: float = 5.0) -> None` to `_test_helpers.py`. Body: compute `state_file = wiki_path / ".wiki-daemon.json"`; if `not state_file.exists()` return immediately; otherwise loop `time.monotonic() < deadline` polling every 0.05s for state-file absence; return silently on either disappearance or timeout (no exception on timeout). Add the necessary imports (`time`) at module top. Update the module docstring's `Public API:` section to list the new helper. Do not call any wiki client function; this helper is pure filesystem polling.
- **Commit:** `test(_test_helpers): add wait_for_daemon_exit polling helper`

### Card 4: add init_wiki_repo helper to _test_helpers

- **Context:**
  - `plugins/mill/unit_tests/test-fold.py`
- **Edits:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a public function `init_wiki_repo(wiki_path: Path) -> None` to `_test_helpers.py`. Body: ensure `wiki_path.mkdir(parents=True, exist_ok=True)`; run `git init` (use `--initial-branch=main`, fall back to `git init` + `git checkout -b main` on failure, mirroring `_make_task_worktree`); run `git config user.email "test@test.com"` and `git config user.name "Test"`; create an empty `.keep` file, `git add .keep`, `git commit -m "init"`; create a sibling bare repo at `wiki_path.parent / f"{wiki_path.name}.git"` via `git init --bare`; run `git -C <wiki_path> remote add origin <bare-path>`; run `git -C <wiki_path> push --set-upstream origin main`. All `subprocess.run` calls use `capture_output=True, check=True`. Update the module docstring's `Public API:` section to list the new helper. Pattern source: `test-fold.py:45-82`'s existing setup (the same shape, extracted for reuse).
- **Commit:** `test(_test_helpers): add init_wiki_repo helper for V3 fixture setup`

### Card 5: extend _make_task_worktree with seed_task option and module-level idle env-var setdefault

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Two changes in `_test_helpers.py`. (1) At module top (after the existing scripts-path `sys.path.insert` block, before any function definition), add `import os` and `os.environ.setdefault("WIKI_DAEMON_IDLE_TIMEOUT", "1")` so every test file that imports `_test_helpers` (all unit tests do) gets the fast-exit daemon automatically without per-test boilerplate. Use `setdefault` so a test that wants a longer timeout can override before importing. (2) Add a keyword parameter `seed_task: bool = False` to `_make_task_worktree`. When `False` (default), behaviour is unchanged. When `True`: before the existing `(wiki_path / "Home.md").write_text(home_body, ...)` step, call `init_wiki_repo(wiki_path)` to turn the wiki directory into a real git repo with a local bare origin; after writing Home.md, also call `wiki.upsert_task(wiki_path, slug, title=title, status=(None if phase == "none" else phase))` so the slug lands in `tasks.json`. Add `from wiki import _client as wiki` to the module imports if not already present (existing `parse_home_md` import is unrelated). The Home.md write stays in both branches so existing tests that assert on rendered text remain valid. Update the module docstring's `Public API:` signature and the function's docstring with the new parameter and the env-var default.
- **Commit:** `test(_test_helpers): add seed_task option and WIKI_DAEMON_IDLE_TIMEOUT default`

### Card 6: extend safe_temp_dir to wait for daemon exit before rmtree

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Edits:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `safe_temp_dir` (currently `plugins/mill/unit_tests/_test_helpers.py:159-165`), insert -- inside the existing `finally` block, BEFORE the existing `_safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)` call -- a pre-cleanup step: glob `tmp.rglob(".wiki-daemon.json")` and for each match call `wait_for_daemon_exit(match.parent, timeout=5.0)`. Use `list(...)` around the rglob to materialise the iterator before mutating the tree. Use a `try/except OSError: pass` around the rglob in case the tree is in a weird state. The wait helper itself returns silently on timeout, so the overall fixture teardown remains best-effort. Update the function docstring to note the daemon-wait sweep.
- **Commit:** `test(_test_helpers): wait for daemon exit in safe_temp_dir cleanup`

### Card 7: regression test asserting WikiServer.on_stop closes handlers

- **Context:**
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/_daemon.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new test function `test_wiki_server_on_stop_closes_log_handlers` (registered in the file's main-runner list, following the existing PASS-line convention used by sibling tests in the file) that: (a) creates a tempdir wiki_path via `_test_helpers.safe_temp_dir()`, (b) instantiates `WikiServer(wiki_path, idle_timeout=1)` directly (does NOT call `.run()` -- the test exercises `on_stop` in isolation), (c) captures `handler = wiki_server._log.handlers[0]` and asserts it is a `logging.handlers.RotatingFileHandler`, (d) calls `wiki_server.on_stop()`, (e) asserts `wiki_server._log.handlers == []` AND `handler.stream is None or handler.stream.closed` (RotatingFileHandler clears `stream` to None after close on some Python versions; both states are accepted). Print `PASS: WikiServer.on_stop closes log handlers and clears handler list` on success. Do NOT use `subprocess` to spawn a real daemon -- in-process is sufficient and fast. No allowlist edit to `test-no-direct-rmtree.py` needed (`test-wiki-daemon.py` is already on the list).
- **Commit:** `test(wiki-daemon): regression for on_stop log-handler close`

## Batch Tests

This batch's `verify:` runs `plugins/mill/unit_tests/test-wiki-daemon.py`, which after Card 6 includes the new on_stop regression test. The rest of the suite still has the original RC1 / RC2 / RC3 / RC4 reds at this point (batch 2 and 3 fix those); running `run-all.py` here would still fail and would not give clean signal on whether this batch's work is correct. The targeted verify confirms (a) the existing tests in `test-wiki-daemon.py` still pass (no regression in the daemon-base unit tests), and (b) the new on_stop regression test passes (Card 1 + Card 6 land together). Cards 2-5 add public surface but no behaviour observable from `test-wiki-daemon.py`; their correctness is implicitly tested by batch 2's fixtures consuming them.
