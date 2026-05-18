# Plan: 58 (D) -- Activate psmux-based claude subprocess routing

```yaml
task: 58 (D) -- Activate psmux-based claude subprocess routing
slug: claude-psmux-activate
approved: false
started: 20260518-103615
parent: main
root: ""
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py
```

## Batch Index

```yaml
batches:
  - number: 1
    name: activate-via-psmux
    file: 01-activate-via-psmux.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py
```

## Shared Decisions

### Decision: psmux-flag-lookup

- **Decision:** `_get_via_psmux_flag()` is the single read site for `llm.claude.via_psmux`. Lives in `_llm_claude.py` next to the existing helpers. Resolves `git_root` via `_paths.resolve_git_root(Path.cwd())`, calls `_config.load_config(git_root, git_root)`, returns `cfg.get("llm", {}).get("claude", {}).get("via_psmux", False)`. Wraps the whole body in a broad `try/except Exception` returning `False` so any failure (cwd outside a git worktree, missing/malformed config, import error) silently picks the direct path.
- **Rationale:** Discussion `### config-loading-in-invoke`. Per-call config load is cheap and avoids module-level mutable state. Defaulting to `False` on any error preserves the existing direct-path behaviour for machines that never opted in.
- **Applies to:** all cards in this batch.

### Decision: argv-construction-strategy

- **Decision:** New `_build_psmux_argv(model, effort, allowed_tools, session_id)` function. Python interpreter: `sys.executable`. Wrapper script path: `str(Path(__file__).resolve().parent / "millpy-claude-sub.py")`. Mode mapping (exact-match dict, raise `LLMError` for unsupported values):
  - `""` -> `bulk`
  - `"Read,Grep,Glob"` -> `tool-use`
  - `"Read,Edit,Write,Bash,Grep,Glob,Skill"` -> `implementer`
  Effort -> `--effort <value>` when not `None`. Session -> `--session-id <id>` when not `None` (always non-`None` at the call site because `_invoke` generates one when missing -- see card 3).
- **Rationale:** Discussion `### psmux-argv-construction`. Deterministic path resolution that works in both source-tree and cache-install modes without `${CLAUDE_PLUGIN_ROOT}`. The unsupported-value branch surfaces a misconfigured caller as a clear `LLMError` rather than silently misrouting.
- **Applies to:** card 2.

### Decision: branch-shape-in-_invoke

- **Decision:** Inside `_invoke()`, immediately after computing `mode_suffix` and the entry-log line but BEFORE `start = time.monotonic()`, branch on `_get_via_psmux_flag()`. The psmux branch:
  1. If `resume`: raise `LLMError("psmux path does not support session resume; turn off via_psmux for resume flows")`.
  2. If `shutil.which("psmux") is None`: raise `LLMError("psmux not on PATH; required when llm.claude.via_psmux=true")`.
  3. If `session_id is None`: generate `session_id = str(uuid.uuid4())` so the function still returns a non-`None` sid.
  4. `start = time.monotonic()` (same log shape).
  5. `argv = _build_psmux_argv(model, effort, allowed_tools, session_id)`.
  6. Call `_subprocess_util.run(argv, input=prompt_text, timeout=float(timeout), cwd=cwd)`. Wrap timeout/spawn errors identically to the direct path.
  7. On non-zero exit: raise `LLMError(f"psmux-claude exited {result.returncode}: {error_detail}")` (no `_scan_rate_limit`, no fast-fail retry, no `LLMSessionError` -- discussion `### fast-fail-retry-psmux` and `### rate-limit-detection-psmux`).
  8. `text = result.stdout.rstrip()`; emit the existing `[_llm_claude] ... returned {N} chars in {dt:.1f}s session={sid_log}` log line; `return text, session_id`.
  The direct path (else-branch) keeps the existing argv/retry/`_parse_stream_json`/rate-limit machinery byte-for-byte.
- **Rationale:** Single fork point keeps the public surface and all three public functions (`run_bulk`, `run_tool_use`, `run_implementer`) unchanged. Wrapper output is plain text by design, so `_parse_stream_json` is skipped. The fast-fail retry exists to paper over the `cmd /c` claude shim flake (issue #153) which is not relevant on the psmux path.
- **Applies to:** card 3.

### Decision: config-mirror-doc-comments

- **Decision:** Add `via_psmux: false  # Route claude calls through psmux for subscription billing (requires psmux on PATH; resume flows unsupported)` to both `mill-config.yaml` (hub) and `plugins/mill/templates/mill-config.yaml`, in identical positions inside a new `claude:` sub-block under `llm:`. Insertion point: after `implementer_timeout:` and before the next `# -----` separator.
- **Rationale:** Per CLAUDE.md "Template `mill-config.yaml` is the canonical config schema" -- hub-root file is source of truth for the value, template is source of truth for the doc comment. Identical content prevents drift; new hubs seeded from the template inherit the same key with the same comment.
- **Applies to:** card 1.

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-llm-claude.py`
