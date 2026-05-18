# Batch: activate-via-psmux

```yaml
task: 58 (D) -- Activate psmux-based claude subprocess routing
batch: activate-via-psmux
number: 1
cards: 4
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py
depends-on: []
```

## Batch Scope

This batch wires the existing psmux subprocess wrapper (`millpy-claude-sub.py`) into the live `_llm_claude._invoke()` call path behind a new opt-in config flag (`llm.claude.via_psmux`, default `false`). After this batch, machines that set the flag in `.millhouse/config.local.yaml` will route every `run_bulk` / `run_tool_use` / `run_implementer` call through the psmux TUI wrapper (subscription billing) while everything else continues to use the existing `cmd /c claude -p` path unchanged. No public API changes; no wrapper changes; the three previously-built artefacts (`_psmux.py`, `_psmux_capture.py`, `millpy-claude-sub.py`) gain their first production caller. Session keepalive remains a follow-up task -- `resume=True` on the psmux path raises `LLMError` per the discussion.

## Cards

### Card 1: Add `llm.claude.via_psmux` to hub `mill-config.yaml` and plugin template

- **Context:** none
- **Edits:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Under the existing top-level `llm:` block in both files, add a `claude:` sub-block containing exactly one key: `via_psmux: false  # Route claude calls through psmux for subscription billing (requires psmux on PATH; resume flows unsupported)`. The `claude:` sub-block is inserted after the four existing scalar keys (`bulk_timeout`, `holistic_timeout`, `tool_use_timeout`, `implementer_timeout`) and before the next `# ---` separator that begins the `pipeline:` section. Indentation: two spaces for `claude:` (sibling of the timeouts), four spaces for `via_psmux`. The line content -- key, value, comment -- must be byte-identical between the two files so any future schema-drift diff is one-line-or-zero. All comment characters are ASCII per CLAUDE.md.
- **Commit:** `feat(config): add llm.claude.via_psmux flag (default false)`

### Card 2: Add `_get_via_psmux_flag()` and `_build_psmux_argv()` helpers in `_llm_claude.py`

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_llm_common.py`
  - `mill-config.yaml`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Add module-level imports for `shutil` and `uuid` (stdlib) alongside the existing `import json` / `os` / `sys` / `time` block.
  2. Add a module-level constant `_MODE_BY_ALLOWED_TOOLS: dict[str, str] = {"": "bulk", "Read,Grep,Glob": "tool-use", "Read,Edit,Write,Bash,Grep,Glob,Skill": "implementer"}` placed immediately after the existing `_MUTATING_TOOLS` constant.
  3. Add `def _get_via_psmux_flag() -> bool:` placed immediately after `_has_mutating_tool`. Body:
     - Wrap the whole lookup in `try` / `except (Exception, SystemExit)` -- on any exception, `return False`. The dual-class clause is required because `_paths.resolve_git_root` raises `SystemExit` (a `BaseException`, not `Exception`) when cwd is outside a git worktree; `except Exception` alone would let that escape. Mirrors the existing pattern at `plugins/mill/scripts/_paths.py:132`.
     - Inside the `try`: do local imports `import _paths` and `import _config` (deferred to keep `_llm_claude` importable in test contexts that monkey-patch only `_subprocess_util`).
     - `git_root = _paths.resolve_git_root(Path.cwd())`
     - `cfg = _config.load_config(git_root, git_root)`
     - `return bool(cfg.get("llm", {}).get("claude", {}).get("via_psmux", False))`
  4. Add `def _build_psmux_argv(model: str, effort: str | None, allowed_tools: str, session_id: str) -> list[str]:` placed immediately after `_build_argv`. Body:
     - `mode = _MODE_BY_ALLOWED_TOOLS.get(allowed_tools)`; if `mode is None`, raise `LLMError(f"via_psmux: unsupported allowed_tools {allowed_tools!r}")`.
     - `wrapper = str(Path(__file__).resolve().parent / "millpy-claude-sub.py")`.
     - Build `argv = [sys.executable, wrapper, "--mode", mode, "--model", model]`.
     - If `effort is not None`: append `["--effort", effort]`.
     - Append `["--session-id", session_id]` unconditionally (the caller guarantees a non-`None` session_id at this point).
     - `return argv`.
  5. Do NOT modify `_build_argv`, `_parse_stream_json`, `_scan_rate_limit`, or any public `run_*` function in this card.
- **Commit:** `feat(_llm_claude): add via_psmux flag lookup and argv builder`

### Card 3: Branch `_invoke()` on `via_psmux` flag

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify the body of `_invoke()` in `_llm_claude.py` so the existing entry-log line is unchanged, then immediately after that log line and BEFORE `start = time.monotonic()` insert `if _get_via_psmux_flag():` opening a new branch. Inside that branch:
  1. If `resume`: `raise LLMError("psmux path does not support session resume; turn off via_psmux for resume flows")`.
  2. If `shutil.which("psmux") is None`: `raise LLMError("psmux not on PATH; required when llm.claude.via_psmux=true")`.
  3. If `session_id is None`: `session_id = str(uuid.uuid4())`. (After this line, `session_id` is guaranteed non-empty for the return value and the argv builder.)
  4. `start = time.monotonic()`.
  5. `argv = _build_psmux_argv(model, effort, allowed_tools, session_id)`.
  6. Call `_subprocess_util.run(argv, input=prompt_text, timeout=float(timeout), cwd=cwd)` inside the existing `try` / `except` shape used by the direct path -- on `TimeoutExpired`-style exception raise `LLMError(f"psmux-claude timed out after {timeout}s") from exc`; on any other exception raise `LLMError(f"Failed to spawn psmux-claude: {exc}") from exc`.
  7. `dt = time.monotonic() - start`.
  8. If `result.returncode != 0`: `error_detail = (result.stderr or result.stdout or "")[:500]`; `raise LLMError(f"psmux-claude exited {result.returncode}: {error_detail}")`. Do NOT call `_scan_rate_limit`. Do NOT run the fast-fail retry. Do NOT raise `LLMSessionError`.
  9. `text = result.stdout.rstrip()`.
  10. `sid_log = session_id[:8] if len(session_id) >= 8 else session_id`.
  11. `print(f"[_llm_claude] claude {model} returned {len(text)} chars in {dt:.1f}s session={sid_log}", file=sys.stderr)`.
  12. `return text, session_id`.

  The else branch (i.e. everything after the `if _get_via_psmux_flag()` block) is the existing direct-path body unchanged: `start = time.monotonic()`, `argv = _build_argv(...)`, the existing try/except, the fast-fail retry block, `_scan_rate_limit`, `_parse_stream_json`, the existing `[_llm_claude] ... returned {N} chars ...` log line, and `return text, effective_sid`. Lift the existing body into the else only if it is mechanically clearer; otherwise simply put `if _get_via_psmux_flag(): ...psmux body... return ...` before the existing direct-path body and let the early-return fall through. No public-API or callers signature changes.
- **Commit:** `feat(_llm_claude): branch _invoke on via_psmux flag`

### Card 4: Extend `test-llm-claude.py` with psmux coverage

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Append new test cases to the existing `main()` body in `plugins/mill/unit_tests/test-llm-claude.py`, using the same `errors += 1` / `print("PASS: ...")` pattern as existing tests. Add `import os`, `import re`, and `import uuid` at top alongside the existing stdlib imports (`os` is needed for test case 1's `os.name` argv-prefix check; `re` and `uuid` for the UUID-shape assertions). Each new case mocks `_subprocess_util_mod.run` with `mock.patch.object` AND additionally monkey-patches `_llm_claude_mod._get_via_psmux_flag` to return either `True` or `False` per case (so no real config file is read). Required new cases, in order:

  1. `via_psmux=False` baseline -- `run_bulk` with the existing OK fakes still emits `cmd` / `/c` / `claude` as `argv[0..2]` on Windows (or `claude` as `argv[0]` on POSIX). Use `os.name` to pick the expected prefix. Proves default did not regress.
  2. `via_psmux=True`, `run_bulk(session_id=None)` -- captured argv starts with `[sys.executable, <wrapper-path>, "--mode", "bulk", "--model", "m"]` where `<wrapper-path>` ends in `millpy-claude-sub.py` (test via `endswith("millpy-claude-sub.py")`); argv contains `"--session-id"` followed by a UUID-shaped token (assert via `uuid.UUID(token)` constructor not raising); returned tuple is `(stdout.rstrip(), <that-same-uuid>)` where the UUID matches the one observed in argv.
  3. `via_psmux=True`, `run_tool_use` -- argv contains `"--mode"` followed by `"tool-use"` (assert by index).
  4. `via_psmux=True`, `run_implementer` -- argv contains `"--mode"` followed by `"implementer"`.
  5. `via_psmux=True`, `session_id="abc-explicit"` -- argv contains `"--session-id"` followed by `"abc-explicit"`; returned `(text, sid)` -> `sid == "abc-explicit"` unchanged.
  6. `via_psmux=True`, `resume=True` -- `LLMError` raised; mocked `_subprocess_util.run` call_count is exactly 0 (raised before subprocess).
  7. `via_psmux=True`, `shutil.which("psmux") -> None` -- monkey-patch `_llm_claude_mod.shutil.which` to return `None`; `LLMError` raised; mocked `_subprocess_util.run` call_count is exactly 0.
  8. `via_psmux=True`, mocked subprocess returns `returncode=1, stdout="", stderr="boom"` -- plain `LLMError` raised (assert NOT a `LLMSessionError` instance and NOT a `LLMRateLimitError` instance via `isinstance` checks).
  9. `via_psmux=True`, mocked subprocess returns `returncode=1` with empty stdout and `time.monotonic` patched to return `[0.0, 1.0]` (dt < 2s) -- mock call_count is exactly 1 (no fast-fail retry on psmux path).
  10. `via_psmux=True`, mocked subprocess returns `returncode=0, stdout="hello world\n"` -- returned text is `"hello world"` (rstrip applied). Assert `_parse_stream_json` is NOT called: this is implicit because if it were called on plain `"hello world\n"` it would raise `LLMError("claude returned no content")`; therefore a clean return through proves the bypass.
  11. `_get_via_psmux_flag()` fallback -- because `_paths` is imported lazily inside the helper (NOT at module level), it is not an attribute on `_llm_claude_mod`. Canonical patching approach: at the top of this test case, do `import _paths` directly in the test module to guarantee `_paths` is in `sys.modules`, then `with mock.patch.object(_paths, 'resolve_git_root', side_effect=SystemExit("test")):` call `_llm_claude_mod._get_via_psmux_flag()` and assert it returns `False`. Equivalent form: `with mock.patch.dict(sys.modules, {'_paths': _paths}), mock.patch.object(sys.modules['_paths'], 'resolve_git_root', side_effect=SystemExit("test")):`. Either form proves the broad `try / except (Exception, SystemExit)` envelope catches `SystemExit` (the explicit BaseException-subclass case from the BLOCKING fix). Do NOT patch `_llm_claude_mod._paths` -- that attribute does not exist on the module because the import is deferred to inside the helper.

  All new cases share a helper closure for capturing argv (extend the existing `_fake_run`/`captured_argv` pattern). Final assertion is the existing `if errors: return 1` envelope -- no new return path. The suite must continue to be invoked via the same `verify:` command at the batch root.
- **Commit:** `test(_llm_claude): cover via_psmux branch`

## Batch Tests

`verify:` runs `uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py`, the canonical unit-test entry point for `_llm_claude.py`. The suite's existing assertions cover the direct path; cards 2-4 add psmux-path coverage. The suite's exit code (`0` = all `PASS:`, non-zero = any `FAIL:` or unhandled exception) is the single verify signal -- no separate harness, no integration test in this batch.

The integration test `plugins/mill/integration_tests/test-claude-psmux.py` already exists and must continue to pass with `via_psmux=true`, but it is operator-run (real `claude`, real `psmux`) and is not part of the `verify:` command for this batch.
