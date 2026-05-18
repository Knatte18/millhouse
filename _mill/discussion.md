# Discussion: 58 (D) — Activate psmux-based claude subprocess routing

```yaml
task: 58 (D) — Activate psmux-based claude subprocess routing
slug: claude-psmux-activate
status: discussing
parent: main
```

## Problem

The previous task (`claude-p-wrapper`, squash-merged) built the infrastructure for routing
`claude` calls through interactive TUI sessions via psmux (`_psmux.py`, `_psmux_capture.py`,
`millpy-claude-sub.py`, unit tests, integration test). Nothing in production uses it.
`_llm_claude.py` still invokes `cmd /c claude -p` directly via subprocess, so all billing lands
on API credits instead of the operator's subscription.

This task activates the routing: adds a `llm.claude.via_psmux` config toggle (default `false`)
and wires `_llm_claude._invoke()` to fork on that flag. Machines without psmux installed continue
to work unchanged.

Session keepalive (keeping the psmux TUI alive across calls for true session continuity) is
deferred to a follow-up task. The wrapper kills the session in `finally` — this task accepts that
constraint. `resume=True` therefore raises `LLMError` on the psmux path.

## Scope

**In:**
- `mill-config.yaml` (hub) — add `llm.claude.via_psmux: false`
- `plugins/mill/templates/mill-config.yaml` — mirror the same addition
- `plugins/mill/scripts/_llm_claude.py` — `_get_via_psmux_flag()` helper; `_build_psmux_argv()`;
  branch in `_invoke()`
- `plugins/mill/unit_tests/test-llm-claude.py` — new test cases for the psmux branch

**Out:**
- `_psmux.py`, `_psmux_capture.py`, `millpy-claude-sub.py` — no changes (wrapper is finished)
- `_llm_gemini.py` — no changes (Gemini psmux routing is a separate future task)
- `_implementer_claude.py`, `_reviewer_single.py` — no caller-API changes
- Session keepalive (keeping psmux TUI alive across calls) — separate follow-up task
- Rate-limit detection on the psmux path — wrapper doesn't emit stream-json
- Auto-detection of psmux at config-load time

## Decisions

### config-key-shape

- Decision: `llm.claude.via_psmux: false` nested under the existing `llm:` block. Per-provider
  naming (`llm.<provider>.via_psmux`) keeps the door open for `llm.gemini.via_psmux` etc.
  without a schema refactor. Default is `false` everywhere: machines without psmux installed never
  set it, and the operator who wants it explicitly opts in via `.millhouse/config.local.yaml`.
- Rationale: Aligns with existing `llm.claude.*` shape (once we start adding provider-specific
  keys); no breaking change to existing consumers of the `llm:` block.
- Rejected: flat `llm.via_psmux` — provider-agnostic but conflates routing decisions across
  providers. Rejected: env-var only — bypasses the config layer and can't be persisted.

### config-loading-in-invoke

- Decision: Load config inside `_invoke()` on every call via a small `_get_via_psmux_flag()`
  helper. Helper calls `_paths.resolve_git_root(Path.cwd())` → `_paths.resolve_wiki_path(...)` →
  `_config.load_config(wiki_path, worktree_root)`. Returns `bool`, defaults to `False` on any
  error (missing key, config load failure, import error). No caller-API change.
- Rationale: `_llm_claude`'s callers (`_reviewer_single`, `_implementer_claude`) don't thread
  `cfg` today. Adding it would touch every caller, every reviewer module, and every test.
  Config load is a cheap YAML parse; per-call is fine. Per-process the config is effectively
  stable, so the repeated load is harmless.
- Rejected: module-level lazy cache — adds mutable module state with unclear invalidation;
  same per-process behaviour but more complex. Rejected: add `cfg` kwarg to `run_*` functions —
  large caller-API diff with no benefit.

### psmux-argv-construction

- Decision: New `_build_psmux_argv(model, effort, allowed_tools, session_id)` function.
  Python interpreter: `sys.executable` (already running in the venv). Script path:
  `str(Path(__file__).resolve().parent / "millpy-claude-sub.py")` — co-located, no env-var
  dependence, works in both source-tree and cache-install modes.
  Allowed-tools → mode mapping:
    - `""` → `bulk`
    - `"Read,Grep,Glob"` → `tool-use`
    - `"Read,Edit,Write,Bash,Grep,Glob,Skill"` → `implementer`
  Any other value → `LLMError("via_psmux: unsupported allowed_tools ...")`
  Session: if `session_id` is provided, pass `--session-id <id>`; if `None`, omit (wrapper
  generates a UUID internally).
- Rationale: Deterministic path resolution without relying on `CLAUDE_PLUGIN_ROOT` or cwd.
  The `sys.executable` / `__file__` pair is the standard pattern for "call a co-located script
  with the same interpreter."
- Rejected: `${CLAUDE_PLUGIN_ROOT}` paths — redundant since we're already running in that venv.

### session-id-and-resume-semantics

- Decision: `resume=True` with `via_psmux=true` raises
  `LLMError("psmux path does not support session resume; turn off via_psmux for resume flows")`.
  `session_id` provided with `resume=False` is passed through to wrapper `--session-id`; the
  same value is returned as the session_id for the call.
- Rationale: The wrapper calls `_psmux.kill_session` in `finally` — the TUI is gone before
  `_invoke` returns. There is no live session to resume. Raising `LLMError` is the honest
  contract. Session keepalive (keeping TUI alive between calls) is a separate follow-up task.
- Rejected: silent ignore + stderr warning — callers that rely on session continuity (mill-go's
  implement → review → fix loop) would silently lose context without knowing. Rejected: honor
  `--resume` by passing it to the wrapper — interactive `claude` TUI does not support `--resume`
  (that flag belongs to `claude -p`).

### psmux-availability-check

- Decision: In `_invoke()`, at the start of the psmux branch: call `shutil.which("psmux")`.
  If `None`, raise `LLMError("psmux not on PATH; required when llm.claude.via_psmux=true")`.
  This pre-check produces a clear error instead of the cryptic `PsmuxError` from deep inside
  the wrapper.
- Rationale: Explicit opt-in with loud failure. No silent fallback to the direct path — that
  would violate the operator's intent (they wanted psmux billing).
- Rejected: silently fall back to `cmd /c claude` — defeats the billing goal.
  Rejected: validate at config-load time — loads config in context that has no subprocess at
  hand; cleaner to fail at the call site.

### response-extraction-psmux

- Decision: Skip `_parse_stream_json` entirely on the psmux path. The wrapper writes the raw
  assistant text to stdout. Response text = `result.stdout.rstrip()`. Session_id = the value we
  passed (or `None` if none passed, but the caller should always pass one to get consistent IDs).
  The `[_llm_claude] starting...` and `[_llm_claude] returned N chars` log lines are emitted
  identically to the direct path. No additional logging.
- Rationale: Wrapper output is already plain text (per its design). `_parse_stream_json` would
  fail on it. Verbosity rule from tasks 65/66: `_subprocess_util` only logs on failure; we must
  not regress this.
- Rejected: have wrapper emit stream-json — would require wrapper changes (out of scope).

### fast-fail-retry-psmux

- Decision: The fast-fail retry (issue #153 `cmd /c` shim flake) is skipped on the psmux path.
  The condition `dt < 2.0 and not result.stdout.strip()` is only entered in the `not via_psmux`
  branch.
- Rationale: The flake is specific to the `cmd /c` shim. The psmux wrapper has its own failure
  modes (psmux boot timeout, claude TUI not ready); its non-zero exits are meaningful and should
  not trigger a blind retry.

### cwd-forwarding

- Decision: Pass `cwd` through to `_subprocess_util.run(psmux_argv, input=..., cwd=cwd)`.
  The wrapper inherits the process cwd; `psmux new-session` inherits it from the subprocess;
  the spawned pwsh session starts in that directory. No wrapper changes needed.
- Rationale: `run_implementer(cwd=<worktree>)` must land the claude TUI in the correct directory.
  The inheritance chain handles this transparently. Rejected: add `--cwd` to wrapper — out of
  scope per proposal.

### rate-limit-detection-psmux

- Decision: No rate-limit detection on the psmux path. Any non-zero exit raises plain `LLMError`.
- Rationale: The wrapper doesn't emit stream-json, so `_scan_rate_limit` would always return
  `False`. The mill-go ERROR-only retry handles repeated errors; the operator can inspect logs.
  Rate-limit signals through psmux are a future concern.

## Technical context

`_llm_claude._invoke()` is the single code path that all three public functions
(`run_bulk`, `run_tool_use`, `run_implementer`) funnel into. The psmux branch only diverges in
`_invoke()`, not in the public functions themselves. Callers have no API change.

Config loading: `_config.load_config(wiki_path, worktree_root)` already handles the full
overlay chain (plugin template → hub `mill-config.yaml` → `.millhouse/config.local.yaml`).
The new `llm.claude.via_psmux` key is added to both the hub file and the plugin template so
new hubs get the schema doc comment.

`millpy-claude-sub.py` and `_llm_claude.py` are co-located in `plugins/mill/scripts/`.
`Path(__file__).resolve().parent` is the deterministic script directory for both source-tree
and cache-install modes.

The wrapper emits exactly one line on stderr on success (JSON metadata) and one error line on
failure — verbosity is already minimal and must not be increased.

Mode mapping is exact: `_llm_claude`'s `allowed_tools` strings match `millpy-claude-sub.py`'s
`MODE_TOOL_FLAGS` keys one-to-one. No translation table needed in code.

Existing unit tests in `test-llm-claude.py` exercise `_build_argv`, `_invoke`, error hierarchy,
retry logic, and all three public functions. New tests follow the same mock-`_subprocess_util.run`
pattern.

## Constraints

- `millpy-claude-sub.py` wrapper is not modified (proposal: out of scope).
- No caller API change (`run_bulk`, `run_tool_use`, `run_implementer` signatures unchanged).
- Verbosity must not regress tasks 65/66: no new log lines on the happy path beyond what the
  direct branch already emits.
- `llm.claude.via_psmux` schema addition in the plugin template must stay in sync with the hub
  `mill-config.yaml` (per CLAUDE.md: mirror key additions across both files).
- All string literals in script output must be ASCII only (CLAUDE.md convention: `--` not `—`).

## Testing

**Unit tests (extend `test-llm-claude.py`):**
- `via_psmux=false` (direct path): `_subprocess_util.run` receives `["cmd", "/c", "claude", "-p", ...]`.
  Existing tests already cover this indirectly; add explicit assertion that argv prefix is the
  direct-claude form.
- `via_psmux=true`, `run_bulk`: argv starts with `[sys.executable, ".../millpy-claude-sub.py",
  "--mode", "bulk", "--model", ...]`. No `--session-id` when `session_id=None`.
- `via_psmux=true`, `run_tool_use`: `--mode tool-use` in argv.
- `via_psmux=true`, `run_implementer`: `--mode implementer` in argv.
- `via_psmux=true`, `session_id="abc"`: `--session-id abc` present in argv.
- `via_psmux=true`, `resume=True`: `LLMError` raised before `_subprocess_util.run` is called.
- `via_psmux=true`, psmux not on PATH (mock `shutil.which` → `None`): `LLMError` raised.
- `via_psmux=true`, wrapper exits 0: `result.stdout.rstrip()` returned as text; session_id
  is the value passed in (or `None`).
- `via_psmux=true`, wrapper exits non-zero: `LLMError` raised (not `LLMSessionError`).
- Fast-fail retry not triggered on psmux path (mock `monotonic` to return dt < 2s; verify only
  1 subprocess call).

**Integration test (`integration_tests/test-claude-psmux.py`):** already exists; must continue
to pass with `via_psmux=true` in the test config.

**Manual smoke test (operator, post-deploy):**
1. Set `via_psmux: true` in `.millhouse/config.local.yaml` under `llm: claude:`.
2. Run `python plugins/mill/scripts/millpy-review-discussion.py` (or trigger via mill-go).
3. Confirm Anthropic dashboard shows subscription usage, not API credits.

## Q&A log

- **Q:** Where should `_llm_claude` read the `via_psmux` flag from? **A:** Load config per-call
  inside `_invoke()` via a small helper; no caller-API change.
- **Q:** Should `via_psmux` be per-provider or flat? **A:** Per-provider (`llm.claude.via_psmux`)
  to match the existing `llm.<provider>.*` shape and allow future `llm.gemini.via_psmux` without
  a schema refactor.
- **Q:** `session_id`/`resume` semantics on psmux path? **A:** `resume=True` raises `LLMError`;
  `session_id` is passed through to `--session-id`. Session keepalive is a separate follow-up
  task — the wrapper kills the session in `finally`.
- **Q:** How to find `millpy-claude-sub.py`? **A:** `sys.executable` + `Path(__file__).resolve().parent`.
- **Q:** What if psmux is not on PATH? **A:** `shutil.which("psmux")` pre-check → `LLMError`.
- **Q:** Rate-limit detection on psmux path? **A:** Not implemented; non-zero exits → plain
  `LLMError`. Wrapper doesn't emit stream-json.
- **Q:** Fast-fail retry on psmux path? **A:** Skipped; the `cmd /c` shim flake is not relevant
  to psmux.
