# Batch: llm-claude-fast-fail-retry

```yaml
task: 44 (A) — Bug-fix batch 4
batch: llm-claude-fast-fail-retry
number: 2
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py
depends-on: []
```

## Batch Scope

Add a bounded single-retry guard to `_llm_claude._invoke` so the known `cmd /c claude` shim-failure mode (exit 1 + empty stdout + duration < 2.0s after a prior session interrupt, per issue #153) recovers automatically on a fresh session. Retry is suppressed when `resume=True` — fast-failures during resume must still propagate as `LLMSessionError` so callers can fall back to a cold session. Existing unit test in `test-llm-claude.py` is extended with the four retry-path scenarios documented in discussion.md.

## Cards

### Card 3: Add fast-fail-retry guard to `_llm_claude._invoke`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In `_invoke`, after the existing `_subprocess_util.run` call wrapped in `try: ... except Exception as exc:` (the timeout/spawn-error path), restructure the post-call branch so that the non-zero exit code can trigger a retry. The retry condition is: `result.returncode != 0 AND time.monotonic() - start < 2.0 AND not result.stdout.strip() AND not resume AND not rate_limited`. (`rate_limited` is computed from `_scan_rate_limit(result.stdout or "")` later in the function — move that computation up so it is available for the retry guard, or compute a fresh `_scan_rate_limit` for the guard.)
  2. When the guard fires, emit one stderr breadcrumb `[_llm_claude] fast-fail retry (duration={dt:.2f}s exit={result.returncode})` and re-invoke `_subprocess_util.run(argv, input=prompt_text, timeout=float(timeout), cwd=cwd)` ONCE. After the second call, fall through to the existing rate-limit / non-zero-exit / parse-stream-json logic with the second `result` — NO further retry.
  3. The retry must use the same `argv` as the first call (same model, same flags, same session_id). The point is that a transient cmd-shim flake is recovered with no semantic difference; we are not re-rolling the session.
  4. Update the docstring of `_invoke` to mention the retry: add a paragraph after the "Raises LLMError on failure..." sentence: `When the subprocess exits non-zero within 2 seconds with empty stdout, and resume=False and no rate-limit was detected, the call is retried once with the same argv (see issue #153 — cmd /c claude shim flakes immediately after a prior session interrupt). The retry's outcome propagates as the final result.`
  5. Do NOT introduce a new module-level constant for the 2.0-second threshold — inline the literal. No new helper functions; the retry adds < 15 lines to `_invoke`.
  6. Do not change `run_bulk`, `run_tool_use`, `run_implementer`, `_build_argv`, `_scan_rate_limit`, or `_parse_stream_json`. The retry is local to `_invoke`.
- **Commit:** `fix(_llm_claude): retry once on fast-fail cmd-shim exit (#153)`

### Card 4: Unit-test the retry behavior

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add four new test functions exercising the retry path. Use monkeypatching of `_subprocess_util.run` (or `subprocess.Popen` if the existing tests do that) to inject controlled `CompletedProcess` results. Tests:
  1. `test_invoke_retries_on_fast_fail_then_succeeds` — first call returns `returncode=1, stdout="", duration<2s`; second call returns the valid stream-json. Assert `_invoke` returns successfully, `_subprocess_util.run` was called exactly twice, and stderr (captured) contains `fast-fail retry`.
  2. `test_invoke_does_not_retry_on_slow_fail` — first call returns `returncode=1, stdout="", duration>=2s` (simulate by patching `time.monotonic`). Assert `_invoke` raises `LLMError`, `_subprocess_util.run` was called exactly once.
  3. `test_invoke_does_not_retry_when_resume_true` — first call returns `returncode=1, stdout="", duration<2s`. Call `_invoke` with `resume=True, session_id="abc"`. Assert `LLMSessionError` is raised, `_subprocess_util.run` was called exactly once.
  4. `test_invoke_does_not_retry_on_rate_limit` — first call returns `returncode=1, stdout=<stream-json containing a "rate_limit_event">, duration<2s`. Assert `LLMRateLimitError` is raised, `_subprocess_util.run` was called exactly once.
  Each test uses a minimal valid stream-json stdout (`'{"type":"result","result":"ok","session_id":"abc"}\n'`) for the success-second-call path. If the existing tests use a helper to build that stream-json, reuse it.
- **Commit:** `test(_llm_claude): cover fast-fail retry path`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py`. The four new tests above must pass, plus all pre-existing tests in the file must continue to pass.
