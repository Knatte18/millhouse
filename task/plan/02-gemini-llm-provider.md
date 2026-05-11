# Batch: gemini-llm-provider

```yaml
task: 31 (A) — Simple Gemini Flash reviewer
batch: gemini-llm-provider
number: 2
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-gemini.py
depends-on: [1]
```

## Batch Scope

Build the Gemini LLM-provider module `_llm_gemini.py` and its accompanying unit test `test-llm-gemini.py`. The module's public surface mirrors `_llm_claude.py`'s `run_bulk` / `run_tool_use` pair (no `run_implementer` — out of scope per discussion.md `In/Out`). It re-exports `LLMError`, `LLMSessionError`, `LLMRateLimitError` from `_llm_common.py` (created in batch 1). All semantic decisions for the Gemini wrapper are locked by discussion.md (`subprocess-transport`, `bulk-mode-argv`, `tool-use-mode-argv`, `windows-path-wrap`, `stream-json-parser`, `session-reuse-not-supported`, `effort-kwarg-accepted-and-ignored`, `rate-limit-detection`) — the implementer applies them; it does not redecide them.

External interface batch 3 will consume: `from _llm_gemini import run_bulk, run_tool_use, LLMError, LLMSessionError, LLMRateLimitError`.

## Cards

### Card 3: Create `_llm_gemini.py`

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_llm_gemini.py`
- **Deletes:** none
- **Requirements:**
  1. Create `plugins/mill/scripts/_llm_gemini.py`. Module docstring (single block at the top, after the optional shebang): describe the file as the LLM-provider wrapper for the `gemini` CLI; state that it mirrors `_llm_claude.py`'s public surface minus `run_implementer`; document the four-layer architecture comment (`Reviewer -> _llm_gemini.run_bulk() / run_tool_use() -> subprocess: gemini -p -o stream-json ...`). Include a `Public API:` section listing `LLMError`, `LLMSessionError`, `LLMRateLimitError`, `run_bulk()`, `run_tool_use()`.
  2. Imports (module top, in this order): `from __future__ import annotations`, then `import json`, `import os`, `import re`, `import sys`, `import time`, `import uuid`, then a blank line, then `from pathlib import Path`, then a blank line, then `import _subprocess_util`, then a blank line, then `from _llm_common import LLMError, LLMSessionError, LLMRateLimitError`. Provider-neutral re-exports come from `_llm_common`.
  3. Define `_gemini_argv_prefix() -> list[str]` matching `_claude_argv_prefix`'s shape: on `os.name == "nt"` return `["cmd", "/c", "gemini"]`; otherwise return `["gemini"]`. Docstring explains the Windows PATH-truncation rationale (point at `_claude_argv_prefix`'s docstring for the canonical explanation, then state the same logic applies to the npm-shim `gemini.cmd` at `%LOCALAPPDATA%\Microsoft\WindowsApps` and at `C:\Code\tools\bin\gemini.CMD`).
  4. Define `_build_argv(model: str, *, tooluse: bool) -> list[str]` — keyword-only `tooluse`. Returns `[*_gemini_argv_prefix(), "-p", "-o", "stream-json", "-m", model, "--approval-mode", "plan"]`. When `tooluse is False`, append `["-e", ""]`. NO `--effort`, NO `--session-id`, NO `--resume` — `effort` is ignored per `effort-kwarg-accepted-and-ignored`; session reuse is short-circuited before this function is reached per `session-reuse-not-supported`.
  5. Define `_scan_gemini_rate_limit(stdout: str, stderr: str) -> bool`. Combine stdout and stderr (e.g. `f"{stdout}\n{stderr}"`), lowercase the combined string ONCE, then return True if any of these substrings is present: `"resource_exhausted"`, `"rate_limit"`, `"rate limit"`, `"quota"`, `"429"`, `"too many requests"`. Return False otherwise. Empty inputs return False. Do NOT iterate stream-JSON lines — substring scan on the raw text is sufficient and tolerates schema drift.
  6. Define `_parse_gemini_stream_json(stdout: str) -> tuple[str, str | None]`. Mirror `_llm_claude._parse_stream_json`'s structure: iterate `stdout.splitlines()`, strip each, skip empty, attempt `json.loads`, on `JSONDecodeError` emit `print(f"[_llm_gemini] warning: could not parse stream-json line: {exc}", file=sys.stderr)` and continue. Capture `session_id` from any top-level `session_id` field (last-wins). Capture final text by inspecting `obj.get("type", "")`:
     - if `"result"`, take `obj.get("result", "")` when it is a non-empty string;
     - else if `"assistant"`, walk `obj.get("message", {}).get("content", [])`; if it is a list, concatenate all `{"type":"text","text":<str>}` items via `"".join(...)`; assign as final text when the joined string strips non-empty.
     Raise `LLMError("gemini returned no content")` when final text is None after consuming all lines. Return `(final_text, session_id)`.
  7. Define `_invoke(prompt_text: str, model: str, mode_label: str, timeout: int, *, tooluse: bool, session_id: str | None = None, resume: bool = False) -> tuple[str, str]`. Steps:
     - If `resume is True`: raise `LLMSessionError("gemini session reuse not supported")` before any subprocess call. Do NOT spawn `gemini`. Do NOT consult `session_id`.
     - Emit stderr breadcrumb: `print(f"[_llm_gemini] gemini {model} ({mode_label}) starting...", file=sys.stderr)`. Do NOT log `session_id` (always None for fresh calls).
     - Build argv via `_build_argv(model, tooluse=tooluse)`.
     - Capture `start = time.monotonic()`. Spawn via `_subprocess_util.run(argv, input=prompt_text, timeout=float(timeout))`. Wrap in `try: ... except Exception as exc:` matching `_llm_claude._invoke`'s exception handling: when `"TimeoutExpired" in type(exc).__name__ or "Timeout" in type(exc).__name__`, raise `LLMError(f"Gemini CLI timed out after {timeout}s") from exc`; otherwise raise `LLMError(f"Failed to spawn gemini: {exc}") from exc`.
     - Compute `dt = time.monotonic() - start`. Compute `rate_limited = _scan_gemini_rate_limit(result.stdout or "", result.stderr or "")`.
     - If `result.returncode != 0`: build `error_detail = (result.stderr or result.stdout or "")[:500]`; if `rate_limited` is True, raise `LLMRateLimitError(f"gemini rate-limited (exit {result.returncode}): {error_detail}")`; otherwise raise `LLMError(f"gemini exited {result.returncode}: {error_detail}")`. Do NOT branch on `resume` here — `resume=True` was rejected above and never reaches this point.
     - On zero exit: `text, observed_sid = _parse_gemini_stream_json(result.stdout or "")`. `effective_sid = observed_sid or f"gemini-{uuid.uuid4()}"` — synthetic id when gemini did not emit one, so callers always receive a non-empty string.
     - Emit success breadcrumb: `print(f"[_llm_gemini] gemini {model} returned {len(text)} chars in {dt:.1f}s session={effective_sid[:8]}", file=sys.stderr)`.
     - Return `(text, effective_sid)`.
  8. Define `run_bulk(prompt_text: str, *, model: str, effort: str | None = None, timeout: int = 600, session_id: str | None = None, resume: bool = False) -> tuple[str, str]`. Body: `return _invoke(prompt_text=prompt_text, model=model, mode_label="bulk", timeout=timeout, tooluse=False, session_id=session_id, resume=resume)`. Docstring states: invokes `gemini` with no extensions in read-only mode; documents that `effort` is accepted for API parity with `_llm_claude.run_bulk` but is silently ignored because gemini-cli exposes no thinking-budget flag in headless mode; documents that `session_id` is accepted but ignored on fresh calls; documents that `resume=True` raises `LLMSessionError` immediately (session reuse not supported).
  9. Define `run_tool_use(prompt_text: str, *, model: str, effort: str | None = None, timeout: int = 900, session_id: str | None = None, resume: bool = False) -> tuple[str, str]`. Body: `return _invoke(prompt_text=prompt_text, model=model, mode_label="tool-use", timeout=timeout, tooluse=True, session_id=session_id, resume=resume)`. Docstring mirrors `run_bulk`'s but states the agent runs with default extensions in read-only mode (file inspection allowed; writes denied by the policy layer).
  10. Do NOT define `run_implementer` — out of scope per discussion.md `In/Out` and `Scope (Out)`. Do NOT add any other public function. Do NOT add `_yaml_writer`, `_paths`, or `_config` imports — this module is a pure transport wrapper.
  11. File length target: roughly 250–320 lines (smaller than `_llm_claude.py` because `run_implementer` is absent and there is no `--resume` argv branch).
- **Commit:** `feat(_llm_gemini): subprocess wrapper for gemini CLI (bulk + tool-use)`

### Card 4: Create `test-llm-gemini.py`

- **Context:**
  - `plugins/mill/scripts/_llm_gemini.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-llm-gemini.py`
- **Deletes:** none
- **Requirements:**
  1. Create `plugins/mill/unit_tests/test-llm-gemini.py`. Structure mirrors `test-llm-claude.py`'s `main() -> int` pattern with `if __name__ == "__main__": sys.exit(main())`. Pure in-process — never spawn the real `gemini` CLI; every subprocess interaction is monkeypatched.
  2. Module docstring matches the style of `test-llm-claude.py`'s docstring (state that tests exercise pure-Python surface — argv construction, stream-JSON parsing, exception hierarchy, signature shape — and refer readers to `integration_tests/smoke-llm-gemini.py` for live-CLI tests).
  3. Imports: `from __future__ import annotations`, then `import inspect`, `import subprocess as _subprocess_mod`, `import sys`, `import unittest.mock as mock`, `from pathlib import Path`. Then `HUB = Path(__file__).resolve().parent.parent.parent.parent`, `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))`. Then `import _subprocess_util as _subprocess_util_mod` and `from _llm_gemini import (...)` — pull in `LLMError`, `LLMSessionError`, `LLMRateLimitError`, `_build_argv`, `_gemini_argv_prefix`, `_invoke` (only if its signature is private but needed; otherwise omit), `_parse_gemini_stream_json`, `_scan_gemini_rate_limit`, `run_bulk`, `run_tool_use`.
  4. Test scenarios (each is a top-level assertion in `main()`; print `PASS:` / `FAIL:` lines and increment `errors`):
     - **Module imports cleanly + public symbols exist:** assert `callable(run_bulk)`, `callable(run_tool_use)`, `issubclass(LLMError, Exception)`, `issubclass(LLMSessionError, LLMError)`, `issubclass(LLMRateLimitError, LLMError)`.
     - **Signature shape:** for both `run_bulk` and `run_tool_use`, assert `inspect.signature(fn).parameters` includes `prompt_text`, `model`, `effort`, `timeout`, `session_id`, `resume`; `model` is `KEYWORD_ONLY`; `session_id` default is `None`; `resume` default is `False`; `effort` default is `None`. Assert `run_bulk` has no `cwd` parameter (since `run_implementer` is out of scope and `cwd` is a `run_implementer`-only concept on the Claude side).
     - **Exception hierarchy round-trip:** raise + catch each of the three exception classes, asserting `str(exc)` round-trips and `LLMSessionError` and `LLMRateLimitError` are catchable as `LLMError`.
     - **`_build_argv` bulk:** `argv = _build_argv("gemini-2.5-flash", tooluse=False)`. Assert `argv == [*_gemini_argv_prefix(), "-p", "-o", "stream-json", "-m", "gemini-2.5-flash", "--approval-mode", "plan", "-e", ""]`.
     - **`_build_argv` tool-use:** `argv = _build_argv("gemini-2.5-flash", tooluse=True)`. Assert `argv == [*_gemini_argv_prefix(), "-p", "-o", "stream-json", "-m", "gemini-2.5-flash", "--approval-mode", "plan"]` — i.e. no trailing `-e ""`.
     - **`_parse_gemini_stream_json` result event:** input `'{"type":"system","subtype":"init","session_id":"abc"}\n{"type":"result","result":"APPROVE","session_id":"abc"}\n'`. Assert returns `("APPROVE", "abc")`.
     - **`_parse_gemini_stream_json` assistant event:** input `'{"type":"assistant","message":{"content":[{"type":"text","text":"OK"}]},"session_id":"sid1"}\n'`. Assert returns `("OK", "sid1")`.
     - **`_parse_gemini_stream_json` system-only:** input `'{"type":"system","subtype":"init","session_id":"sid-init"}\n'`. Assert raises `LLMError` whose message contains `"gemini returned no content"`.
     - **`_parse_gemini_stream_json` bad JSON line skip:** input `'not-json\n{"type":"result","result":"OK","session_id":"s1"}\n'`. Assert returns `("OK", "s1")` (the bad line is skipped silently).
     - **`_scan_gemini_rate_limit` positives:** assert True for each of (stdout-only) inputs `"RESOURCE_EXHAUSTED"`, `"rate_limit"`, `"rate limit"`, `"QUOTA exceeded"`, `"HTTP 429"`, `"too many requests"`. Pass `""` as stderr.
     - **`_scan_gemini_rate_limit` negatives:** assert False for `""`, `("foo", "bar")`, `("Internal error", "stack trace")`.
     - **`_scan_gemini_rate_limit` stderr path:** assert True when the substring is in stderr only and stdout is `""`.
     - **`_invoke` zero-exit (monkeypatched `_subprocess_util.run`):** patch returns `CompletedProcess(returncode=0, stdout='{"type":"result","result":"OK","session_id":"sid-z"}\n', stderr="")`. Call `run_bulk("p", model="gemini-2.5-flash")`. Assert returns `("OK", "sid-z")`.
     - **`_invoke` zero-exit synthetic-id fallback:** patch returns valid result text but the stream has no `session_id` field. Assert returned id starts with `"gemini-"` (the synthetic prefix).
     - **`_invoke` non-zero + rate-limit:** patch returns `returncode=1, stdout="RESOURCE_EXHAUSTED: try again later", stderr=""`. Assert `run_bulk("p", model="m")` raises `LLMRateLimitError` and `"RESOURCE_EXHAUSTED"` appears in `str(exc)`.
     - **`_invoke` non-zero + generic:** patch returns `returncode=1, stdout="", stderr="boom"`. Assert `run_bulk("p", model="m")` raises `LLMError` (NOT `LLMRateLimitError`); `"boom"` appears in `str(exc)`.
     - **`_invoke` resume=True short-circuit:** patch `_subprocess_util.run` to a sentinel that records calls. Call `run_bulk("p", model="m", session_id="anything", resume=True)`. Assert `LLMSessionError` is raised; assert the sentinel was NEVER called (subprocess was not spawned).
     - **`_invoke` timeout:** patch `_subprocess_util.run` to raise `_subprocess_mod.TimeoutExpired(cmd=["x"], timeout=1.0)`. Assert `run_bulk("p", model="m", timeout=1)` raises `LLMError` whose message contains `"timed out"` (case-insensitive) and the timeout value `1`.
  5. Each scenario uses a `try: ... finally:` block to restore `_subprocess_util_mod.run` after monkeypatching. Same pattern as `test-llm-claude.py`'s `_orig_run = _subprocess_util_mod.run` → restore.
  6. The script returns 0 when all `PASS:` lines emit and `errors == 0`; returns 1 otherwise. Final line on success: `print("All _llm_gemini unit tests passed.")`.
- **Commit:** `test(_llm_gemini): unit tests for argv, stream-json, rate-limit, session-reuse short-circuit`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-gemini.py`. The new test file is self-contained — every subprocess interaction is monkeypatched, so the verify command does not require the live `gemini` binary. After this batch, `python plugins/mill/unit_tests/run-all.py` will pick up the new test alongside the existing ones (the runner auto-discovers `test-*.py` files in `unit_tests/`); a manual confirmation pass after merge is not required.
