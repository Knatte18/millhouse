# Discussion: 31 (A) — Simple Gemini Flash reviewer

```yaml
task: 31 (A) — Simple Gemini Flash reviewer
slug: gemini-reviewer
status: discussing
parent: main
```

## Problem

The review subsystem currently calls Claude (Sonnet/Opus) for every discussion-gap, plan, and code review. The Sonnet 4.6 weekly quota is the practical bottleneck in mill — every review round consumed against Sonnet is one fewer round available for implementation work. We need an alternative LLM-provider that is fast, cheap, and capable enough for low-stakes review work so operators can offload non-critical reviews onto it.

**Why now:** task 34 (already merged) landed `_reviewer_single.py`, which dispatches reviewer calls by reading `provider:` from the registry spec and importing `_llm_<provider>` at runtime. With that in place, adding a second LLM-provider is a localized change — no reviewer-strategy module, no backend changes, no template changes. Just a new `_llm_<provider>.py` file plus registry entries. The gemini-cli is already installed locally (`C:\Code\tools\bin\gemini.CMD`) and exposes the headless surface we need (`-p`, `-o stream-json`, `-m`, `-r`, `--approval-mode plan`).

## Scope

**In:**

- New `plugins/mill/scripts/_llm_common.py` — `LLMError`, `LLMSessionError`, `LLMRateLimitError` extracted from `_llm_claude.py` so both providers can raise the same exception types.
- `plugins/mill/scripts/_llm_claude.py` — error classes become thin re-exports from `_llm_common`. Public surface unchanged for callers that import from `_llm_claude` directly.
- New `plugins/mill/scripts/_llm_gemini.py` — subprocess wrapper around the gemini CLI, exposing `LLMError`/`LLMSessionError`/`LLMRateLimitError` re-exports + `run_bulk(...)` + `run_tool_use(...)`. Mirrors `_llm_claude.py`'s function signatures and breadcrumb logging style.
- `plugins/mill/scripts/_review_discussion.py`, `_review_plan.py`, `_review_code.py` — change `from _llm_claude import LLMError` to `from _llm_common import LLMError`. One-line edit per file.
- New entries in `wiki/reviewers.yaml`: `gemini_flash` (bulk) and `gemini_flash_tool` (tool-use), both `provider: gemini`, `model: gemini-2.5-flash`.
- New `plugins/mill/unit_tests/test-llm-gemini.py` — mirrors `test-llm-claude.py`'s structure: signatures, argv builder, stream-json parser, rate-limit scanner, monkey-patched-subprocess paths (ok / error / rate-limit / session). Pure in-process; no real `gemini` subprocess.
- New `plugins/mill/integration_tests/smoke-llm-gemini.py` — mirrors `smoke-llm-claude.py` for bulk + tool-use against the live `gemini` CLI. SKIP-and-exit-0 when `shutil.which("gemini")` is None. No session-reuse smoke test (session reuse is not supported).

**Out:**

- `run_implementer` for gemini. mill-go's warm-session pattern depends on `claude -p --resume <uuid>` semantics; gemini-cli's `--resume <id-or-index>` lookup is shaped differently and the cost/benefit of mapping them is not worth it for an MVP. Implementer stays Claude-only.
- `gemini_pro` / `gemini_pro_tool` registry entries. Task title is "Gemini Flash reviewer"; pro variants can be added later by appending to `reviewers.yaml`.
- Changing the default reviewer in `wiki/config.yaml`. `roles.discussion-review.holistic.reviewer: sonnetmax_tool` stays the shipped default; operators opt into Gemini by editing `.millhouse/config.local.yaml` (or the shared `wiki/config.yaml` at their discretion).
- Removing the obsolete `_reviewer_opusmax.py` / `_reviewer_opusmid.py` modules. They are dead code post-task-34 but cleanup is out of scope.
- Effort/thinking-budget plumbing for gemini. gemini-cli has no `--effort` flag; the `effort` kwarg on `run_bulk`/`run_tool_use` is accepted-and-ignored for signature parity.
- Any change to template files in `plugins/mill/templates/` — review prompts are reviewer-agnostic.

## Decisions

### shared-llm-error-hierarchy

- **Decision:** Extract `LLMError`, `LLMSessionError`, `LLMRateLimitError` to a new `plugins/mill/scripts/_llm_common.py`. `_llm_claude.py` and `_llm_gemini.py` both re-export them so direct importers keep working (`from _llm_claude import LLMError` and `from _llm_gemini import LLMError` both resolve to the same class object). The three `_review_*.py` modules switch their imports to `_llm_common`.
- **Rationale:** Without this, `_review_*.py`'s `except LLMError as exc:` only catches Claude failures — a Gemini failure would propagate as an uncaught exception and crash the review CLI. Sharing the class object means callers can keep their existing `except LLMError` patterns and they cover both providers automatically. The cost is one new file and three one-line import edits.
- **Rejected:**
  - Define independent `_llm_gemini.LLMError` and add a normalisation layer inside `_reviewer_single.py`. More code, more failure modes, no upside.
  - Have `_llm_gemini.LLMError` subclass `_llm_claude.LLMError`. Cross-provider coupling at the class level; subclasses leak whenever someone introspects the MRO.

### subprocess-transport

- **Decision:** Spawn the gemini CLI as a subprocess via `_subprocess_util.run(...)`, exactly mirroring `_llm_claude.py`. Argv structure: `gemini -p <prompt-via-stdin> -o stream-json -m <model> --approval-mode plan [-e ""]`. Prompt is delivered on stdin (not as argv) so we are not constrained by the OS argv-length cap. Stdout is decoded as stream-JSON; stderr collects breadcrumbs and error detail.
- **Rationale:** Subprocess matches the pattern that already works for Claude — same UTF-8 enforcement, same breadcrumb logging, same timeout behaviour, same Windows console-suppression flags. No new Python dependency. No new auth plumbing — gemini-cli handles its own credentials.
- **Rejected:** Google Python SDK (`google-genai`). Would add a dependency and a parallel error-handling code path. Operator already has gemini-cli configured for interactive use; reusing that auth context is simpler.

### bulk-mode-argv

- **Decision:** `bulk` mode argv is `[*_gemini_argv_prefix(), "-p", "-o", "stream-json", "-m", <model>, "--approval-mode", "plan", "-e", ""]`. Prompt is written on stdin. `-e ""` forces an empty extension set, so no tool access is loaded into the agent; `--approval-mode plan` is the read-only mode and prevents any inadvertent write attempt at the policy layer.
- **Rationale:** The Claude analogue is `--allowedTools ""`, which is the explicit "no tools" toggle. gemini-cli's `--allowed-tools` flag is marked deprecated in `gemini --help`, and the supported equivalent is "no extensions + read-only approval mode". Using `-e ""` is the supported path and is robust to gemini-cli versions that drop the deprecated flag.
- **Rejected:** `--allowed-tools ""`. Works today but is deprecated; couples us to a flag the upstream is removing.
- **Rejected:** `--approval-mode yolo` + prompt-level "do not use tools" instruction. Less safe — relies on the model honouring the instruction; gives up the policy-layer guarantee.

### tool-use-mode-argv

- **Decision:** `tool-use` mode argv is `[*_gemini_argv_prefix(), "-p", "-o", "stream-json", "-m", <model>, "--approval-mode", "plan"]`. No `-e ""`. Default extensions stay loaded so the agent has Read/Grep/Glob equivalents; `--approval-mode plan` makes the whole tool surface read-only so the policy layer denies any Edit/Write/Bash attempt.
- **Rationale:** The Claude tool-use mode is `--allowedTools Read,Grep,Glob` — file inspection only. gemini-cli's "plan" approval mode is a published read-only mode that achieves the same outcome by policy rather than allow-list. Same robustness argument as bulk-mode-argv.
- **Rejected:** `--allowed-tools Read,Grep,Glob`. Deprecated.
- **Rejected:** Adding `--include-directories <hub-root>` to pin the workspace. Out of scope — review reviewers are launched from inside the worktree so default cwd resolution should work; adding it is a future enhancement if reviewers need to escape into the wiki.

### windows-path-wrap

- **Decision:** `_gemini_argv_prefix()` returns `["cmd", "/c", "gemini"]` on Windows, `["gemini"]` on POSIX. Same shape as `_claude_argv_prefix()`.
- **Rationale:** Identical root cause: `%LOCALAPPDATA%\Microsoft\WindowsApps` (and other npm/cmd shim directories like `C:\Code\tools\bin`) are stripped from the PATH that Python inherits in non-interactive subprocess environments (debugpy, CC's Bash tool). Delegating through `cmd /c` lets cmd.exe use its full interactive PATH. The Claude wrapper documents this in detail; the same comment applies verbatim.
- **Rejected:** Bare `gemini` argv. Confirmed broken in CC's Bash tool subshell during exploration (`gemini: command not found` on bare invocation; works through `cmd //c gemini`).

### stream-json-parser

- **Decision:** Implement `_parse_gemini_stream_json(stdout)` with the same defensive structure as `_llm_claude._parse_stream_json`: iterate lines, JSON-decode each, skip on `JSONDecodeError`, extract `session_id` from any top-level `session_id` field (last-wins), accept text from either `{"type":"result","result":"..."}` or `{"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}` shapes. Raise `LLMError("gemini returned no content")` if no assistant text is found.
- **Rationale:** Defensive parsing is the lesson `_llm_claude` already absorbed — CLI event schemas evolve and the parser must tolerate that. By accepting both event shapes we cover whichever variant gemini-cli emits without needing perfect upstream documentation. If concrete fields differ from the assumed shapes, the integration smoke test will surface it on first run.
- **Rejected:** Use `-o text` and skip JSON parsing. Loses the session_id channel and the ability to detect rate-limit events from structured fields; text output is also more vulnerable to ANSI/sanitization differences.

### session-reuse-not-supported

- **Decision:** `run_bulk(...)` and `run_tool_use(...)` accept `session_id: str | None = None` and `resume: bool = False` for signature parity with `_llm_claude`. Behaviour: any caller-supplied `session_id` is ignored on a fresh call (gemini-cli has no `--session-id <new-uuid>` flag, only `--resume <id-or-index>` for existing sessions). When `resume=True`, raise `LLMSessionError("gemini session reuse not supported")`. The returned session_id is whatever the stream-JSON output exposes (if anything) or a synthetic `gemini-<uuid4>` placeholder so callers always get a non-empty string.
- **Rationale:** mill-go's warm-implementer pattern is the only consumer of session reuse, and the implementer is out of scope for this task. The review CLIs (`millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`) never pass `resume=True` — they always start fresh sessions. So this constraint is invisible to every actual consumer of the gemini provider. Raising `LLMSessionError` (a typed subclass of `LLMError`) gives any future consumer a clear, recoverable signal, and matches the same exception backend already uses for stale Claude sessions.
- **Rejected:** Map caller-supplied `session_id` to gemini's `--list-sessions` index lookup. Adds an extra subprocess call per warm turn, semantics differ (index numbering vs. UUIDs), brittle.
- **Rejected:** Raise `NotImplementedError` for any session_id usage. Too aggressive — callers that pass `session_id` without `resume` are just asking for symmetry; silently ignoring is fine.

### effort-kwarg-accepted-and-ignored

- **Decision:** `run_bulk(...)` and `run_tool_use(...)` accept `effort: str | None = None`. The value is logged in the breadcrumb line for parity but is not translated to any gemini-cli flag — gemini-cli does not expose a thinking-budget knob in headless mode. The docstring states this divergence explicitly.
- **Rationale:** Callers (`_reviewer_single.py`, registry specs) pass `effort` unconditionally. The cleanest path is "accept and ignore" — the dispatch code does not need to special-case providers. Future Gemini work can wire this up if/when upstream exposes a budget flag.
- **Rejected:** Map `effort` to an env-var (`GEMINI_THINKING_BUDGET=<n>`). No such env-var documented; would be guesswork.
- **Rejected:** Drop the kwarg from the gemini signature. Breaks `_reviewer_single.py`'s uniform dispatch path.

### rate-limit-detection

- **Decision:** Add `_scan_gemini_rate_limit(stdout, stderr)` that case-insensitively searches the combined text for any of the substrings: `RESOURCE_EXHAUSTED`, `rate_limit`, `rate limit`, `quota`, `429`, `too many requests`. When `result.returncode != 0` and the scan returns True, raise `LLMRateLimitError`; when returncode != 0 and scan returns False, raise the regular `LLMError` (or `LLMSessionError` if resume=True, matching Claude's pattern).
- **Rationale:** The mill-go ERROR-only retry path catches `LLMRateLimitError` specifically and applies a longer backoff than for transient errors. False positives (mis-classifying a generic crash as rate-limited) only cause that longer backoff, which is harmless. False negatives mean the loop retries too fast on a real quota event and hits the same wall — survivable but worse. The bias toward false-positive is correct.
- **Rejected:** Skip detection; surface every non-zero exit as generic `LLMError`. Loses the typed signal mill-go uses for backoff selection.

### registry-entries

- **Decision:** Append to `wiki/reviewers.yaml`:

  ```yaml
  gemini_flash:
    type: single
    provider: gemini
    model: gemini-2.5-flash

  gemini_flash_tool:
    type: single
    provider: gemini
    model: gemini-2.5-flash
    tooluse: true
  ```

  No `effort:` key on either (gemini ignores it; omit for clarity).
- **Rationale:** Two entries cover the only two modes `_llm_gemini.py` exposes. Names mirror the existing `sonnetmax` / `sonnetmax_tool` naming convention (`<provider><tier>` and `<provider><tier>_tool` suffix). The `provider: gemini` value triggers `_reviewer_single.py` to import `_llm_gemini`.
- **Rejected:** Adding `gemini_pro_*` entries in the same task. Pro variants are a deliberate cost trade-off; not in scope of "simple Gemini Flash reviewer".

### default-reviewer-unchanged

- **Decision:** `wiki/config.yaml` is not modified by this task. The shipped default for `roles.discussion-review.holistic.reviewer` stays `sonnetmax_tool`. Operators who want Gemini flip it themselves in `.millhouse/config.local.yaml`.
- **Rationale:** Quality bar: Sonnet 4.6 is the validated reviewer; Gemini Flash is unproven for this codebase. The right rollout is operator-driven opt-in until we have evidence Gemini hits the bar.
- **Rejected:** Switch default to `gemini_flash_tool`. Premature.

## Technical context

**Files touched (new):**

- `plugins/mill/scripts/_llm_common.py` — three exception classes, no other code.
- `plugins/mill/scripts/_llm_gemini.py` — subprocess wrapper. Structure mirrors `_llm_claude.py` (~400 LOC). Re-exports `LLMError`, `LLMSessionError`, `LLMRateLimitError` from `_llm_common` at the top so `from _llm_gemini import LLMError` works.
- `plugins/mill/unit_tests/test-llm-gemini.py` — unit tests. Structure mirrors `test-llm-claude.py`.
- `plugins/mill/integration_tests/smoke-llm-gemini.py` — integration smoke. Structure mirrors `smoke-llm-claude.py`.

**Files touched (modified):**

- `plugins/mill/scripts/_llm_claude.py` — remove the three exception-class bodies, replace with `from _llm_common import LLMError, LLMSessionError, LLMRateLimitError`. No other change to the public surface.
- `plugins/mill/scripts/_review_discussion.py` — change `from _llm_claude import LLMError` to `from _llm_common import LLMError`.
- `plugins/mill/scripts/_review_plan.py` — same one-line change.
- `plugins/mill/scripts/_review_code.py` — same one-line change.
- `wiki/reviewers.yaml` — append two new top-level entries.

**Reused helpers (do not modify):**

- `_subprocess_util.run(...)` — UTF-8-enforced subprocess invocation with breadcrumbs and timeout handling. Used identically by both `_llm_claude` and `_llm_gemini`.
- `_reviewer_single.run(spec, prompt_text, ...)` — already does `importlib.import_module(f"_llm_{provider}")` and picks `run_tool_use` vs. `run_bulk` from `spec["tooluse"]`. No changes needed here — adding `_llm_gemini.py` makes `provider: gemini` work automatically.
- `_reviewers.load(...)` / `_reviewers.resolve(...)` / `_reviewers.validate_role_refs(...)` — validate the registry. No changes; new entries pass validation because they use `type: single` and have `provider:` + `model:` strings.

**gemini-cli surface (verified via `gemini --help` 2026-05-11):**

- `-p, --prompt <str>` — non-interactive (headless) prompt.
- `-m, --model <str>` — model id (e.g. `gemini-2.5-flash`).
- `-o, --output-format text|json|stream-json` — output schema.
- `-r, --resume <id|index|"latest">` — resume a previous session.
- `--list-sessions` — list sessions; not used by this task.
- `--approval-mode default|auto_edit|yolo|plan` — `plan` is read-only.
- `-e, --extensions <list>` — extensions allow-list. Empty list = no tool access.
- `--allowed-tools <list>` — deprecated; do not use.

**gemini-cli binary location:**

- Windows: `C:\Code\tools\bin\gemini.CMD` (npm shim). Subject to the same `cmd /c` PATH-wrap pattern as `claude`.

**Constraints carried in from `CLAUDE.md`:**

- Plugin scripts MUST use `${CLAUDE_PLUGIN_ROOT}` for path references in any agent-level Bash command or SKILL.md. This task adds no new agent-level invocations; helpers stay accessible via the `_reviewer_single` import chain that already runs from the plugin cache.
- All path resolution goes through `_paths.py`. This task adds no new path resolution — `_llm_gemini.py` does not resolve paths; it is a transport wrapper.
- Generated markdown uses fenced ```yaml for metadata. `discussion.md` (this file), the new test files, and any future docs follow that rule. `reviewers.yaml` is the only YAML edit and it is appended to an existing YAML doc.

## Constraints

No `CONSTRAINTS.md` is present at the hub root (verified). The CLAUDE.md path/invocation rules above are the binding constraints. Worktree-isolation rule applies (this work runs entirely under `C:\Code\millhouse\wts\gemini-reviewer\` — no parent-worktree writes).

## Testing

### Unit tests — `plugins/mill/unit_tests/test-llm-gemini.py`

Structure mirrors `test-llm-claude.py`. All assertions are in-process; no real `gemini` subprocess spawned.

- **Module imports cleanly + public symbols exist** — `run_bulk`, `run_tool_use`, `LLMError`, `LLMSessionError`, `LLMRateLimitError` are present and exception classes have the expected hierarchy (`LLMSessionError`, `LLMRateLimitError` are subclasses of `LLMError`).
- **Signature shape** — `run_bulk` and `run_tool_use` have keyword-only `model`, `effort`, `timeout`, `session_id`, `resume` parameters; `session_id` defaults to `None`, `resume` defaults to `False`. No `cwd` parameter (since `run_implementer` is out of scope).
- **`_build_argv`** —
  - bulk mode with default flags produces `[<prefix>, "-p", "-o", "stream-json", "-m", <model>, "--approval-mode", "plan", "-e", ""]`.
  - tool-use mode omits the `-e ""` pair but otherwise matches.
  - `session_id` set without resume → no `--resume` in argv (ignored, per session-reuse-not-supported).
  - `resume=True` raises `LLMError` (or `LLMSessionError`) before reaching argv — verify the exception path.
- **`_parse_gemini_stream_json`** —
  - well-formed `{"type":"result","result":"text","session_id":"abc"}` returns `("text", "abc")`.
  - `{"type":"assistant","message":{"content":[{"type":"text","text":"text"}]}}` is accepted and returns the text.
  - Empty or `type:"system"`-only stream returns the system event's `session_id` if present and synthetic-id fallback otherwise; raises `LLMError("gemini returned no content")` when no assistant text is found anywhere.
  - Bad JSON line is skipped silently (with a stderr warning, asserted via captured stderr if practical).
- **`_scan_gemini_rate_limit`** —
  - `"RESOURCE_EXHAUSTED"` substring → True.
  - `"rate_limit"`, `"rate limit"`, `"quota"`, `"429"`, `"too many requests"` (case-insensitive) → True.
  - Generic error text without those substrings → False.
  - Empty input → False.
- **`_invoke` integration via monkey-patched `_subprocess_util.run`** —
  - Zero-exit + valid stream-JSON → `(text, sid)` returned.
  - Non-zero exit + rate-limit stdout → `LLMRateLimitError` raised, with stdout fragment in the message.
  - Non-zero exit + generic stderr, `resume=False` → `LLMError` raised.
  - Any call with `resume=True` → `LLMSessionError` raised before subprocess is spawned (so monkey-patched run is never invoked).
  - Timeout → `LLMError` raised, message contains the timeout value.

### Integration smoke — `plugins/mill/integration_tests/smoke-llm-gemini.py`

Mirrors `smoke-llm-claude.py`. Runs the real `gemini` CLI. Exits 0 on success, 1 on failure, **and 0 with a SKIP message when `shutil.which("gemini")` is None** (so CI without gemini installed does not fail).

- `test_bulk()` — Invoke `run_bulk` with an inline reviewer-style prompt that instructs the model to emit `verdict: APPROVE` or `verdict: REQUEST_CHANGES` for a tiny inline file. Assert `verdict:` appears in the response and a non-empty session_id is returned.
- `test_tool_use()` — Write a temporary `sample.py` under `.scratch/`. Pass its absolute path in the prompt. Invoke `run_tool_use`. Assert `verdict:` appears and session_id is non-empty.
- **No session-reuse smoke** — session reuse is not supported; instead include a tiny negative test that calls `run_bulk(..., resume=True, session_id="anything")` and asserts `LLMSessionError` is raised.

### Validation outside the smoke harness

- After implementation, `python plugins/mill/unit_tests/run-all.py` must continue to pass — confirms the `_llm_common.py` extraction and the three `_review_*.py` import edits did not break anything.
- Manual operator validation (one-shot): change `roles.discussion-review.holistic.reviewer: gemini_flash_tool` in `.millhouse/config.local.yaml`, run a single `millpy-review-discussion.py` invocation against this very `discussion.md`, confirm a review file is produced and a verdict is parsed. This is an operator step, not a CI step.

## Q&A log

- **Q:** Which API surface should `_llm_gemini.py` mirror from `_llm_claude.py`? **A:** [auto-pick] `run_bulk` + `run_tool_use` only. **Why:** mill-go's implementer is the only consumer of `run_implementer` and its warm-session pattern depends on Claude's `--resume <uuid>` semantics, which gemini-cli does not match.
- **Q:** Which Gemini registry entries should be added? **A:** [auto-pick] `gemini_flash` (bulk) + `gemini_flash_tool` (tool-use). **Why:** Task title is "Simple Gemini Flash reviewer"; Pro/Lite are explicit future work.
- **Q:** What value should the `provider:` field take in `reviewers.yaml`? **A:** [auto-pick] `gemini`. **Why:** `_reviewer_single.py` resolves `_llm_<provider>` — `provider: gemini` ↔ `_llm_gemini.py`, mirroring `provider: claude` ↔ `_llm_claude.py`.
- **Q:** How should the LLM-error hierarchy be decoupled from `_llm_claude`? **A:** [auto-pick] Extract to a new `_llm_common.py`; both providers re-export; update `_review_*.py` imports. **Why:** `_review_*.py`'s `except LLMError` patterns must catch failures from both providers; sharing the class object is the lowest-overhead way to achieve that.
- **Q:** Should `wiki/config.yaml`'s default reviewer be changed to Gemini? **A:** [auto-pick] No — leave `sonnetmax_tool` as default. **Why:** Gemini Flash is unproven for this codebase; rollout is operator-driven opt-in.
- **Q:** Transport for the gemini CLI call? **A:** [auto-pick] Subprocess via `_subprocess_util.run`. **Why:** Mirrors Claude; no new Python dependency; reuses the existing UTF-8/breadcrumb/timeout infrastructure.
- **Q:** Bulk-mode argv for gemini? **A:** [auto-pick] `gemini -p -o stream-json -m <model> --approval-mode plan -e ""`. **Why:** `-e ""` + `--approval-mode plan` is the supported "no tools, read-only" combination; the deprecated `--allowed-tools` flag is being removed upstream.
- **Q:** Tool-use-mode argv for gemini? **A:** [auto-pick] Same flags as bulk minus `-e ""` (default extensions, read-only). **Why:** Policy-layer read-only enforcement is more robust than a deprecated allow-list flag.
- **Q:** Session-reuse policy? **A:** [auto-pick] Not supported — kwargs accepted for parity, `resume=True` raises `LLMSessionError`. **Why:** Review CLIs never use `resume=True` and implementer is out of scope; mapping gemini's index/UUID semantics is not worth the complexity.
- **Q:** `effort` kwarg handling? **A:** [auto-pick] Accept and ignore — gemini-cli has no effort flag. **Why:** Avoids special-casing in `_reviewer_single.py` dispatch; docstring documents the divergence.
- **Q:** Output parser? **A:** [auto-pick] Defensive stream-JSON parse mirroring `_llm_claude._parse_stream_json`. **Why:** stream-JSON is supported by gemini-cli, defensive parsing tolerates schema drift, retains session_id and rate-limit-detection signal.
- **Q:** Rate-limit detection strategy? **A:** [auto-pick] Substring scan of stdout/stderr for `RESOURCE_EXHAUSTED`, `rate_limit`, `quota`, `429`, `too many requests`. **Why:** Conservative; false positives only trigger longer ERROR-retry backoff (harmless); false negatives lose the typed signal.
- **Q:** Windows PATH handling? **A:** [auto-pick] `cmd /c gemini` prefix on Windows. **Why:** Identical PATH-truncation issue to Claude; verified empirically (`gemini --version` fails in CC's Bash subshell with bare argv, succeeds via `cmd //c gemini`).
- **Q:** Unit-test coverage target? **A:** [auto-pick] Mirror `test-llm-claude.py` — signatures, argv builder, stream-json parser, rate-limit scanner, monkey-patched-subprocess paths. **Why:** Validated structure; comprehensive but self-contained; no live gemini dependency.
- **Q:** Integration smoke test? **A:** [auto-pick] `smoke-llm-gemini.py` mirroring `smoke-llm-claude.py`; SKIP-and-exit-0 when `shutil.which("gemini")` is None; include a negative `resume=True → LLMSessionError` test in place of session reuse. **Why:** Confirms real CLI integration without breaking CI on machines without gemini-cli.
