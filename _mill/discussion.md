# Discussion: Replace claude -p with psmux-routed LLM dispatch

```yaml
task: Replace claude -p with psmux-routed LLM dispatch
slug: replace-claude-p-with-psmux
status: discussing
parent: main
```

## Problem

Mill currently dispatches all reviewers and implementers via `claude -p`, which
bills against API credits. The goal is to route calls through an interactive
`claude` TUI session running inside psmux so the same work bills against the
Claude Max subscription instead. A config flag `llm.claude.psmux.via_psmux`
and a wrapper script `millpy-claude-sub.py` already exist, but turning the flag
on produces a silent hang with no response and no error. Deadline: 15 June 2026.

The wrapper was written without empirical verification of how the claude TUI
behaves inside psmux. This task fixes the four confirmed bugs found during
hands-on testing (see `doc/psmux-tui-behavior.md`).

## Scope

**In:**
- Fix `millpy-claude-sub.py`: shell path config, idle detection, input-area
  clear on reuse
- Fix `_psmux_capture.py`: `extract_response` strips trailing garbage
- Add `llm.claude.psmux.shell_path` config key to template and hub
  `mill-config.yaml`
- Update unit tests (`test-claude-sub.py`, `test-psmux-capture.py`,
  `test-llm-claude.py`) to cover fixed behaviour
- Update integration test `test-claude-psmux.py` to verify end-to-end

**Out:**
- Flipping `via_psmux: true` as the default in `mill-config.yaml` — done
  manually after local verification, not as part of this task
- The Go-based Slack streaming framework (separate future task)
- WSL / pipe-pane streaming architecture
- One-window-per-repo session model (proposal out-of-scope note)
- `resume()` / dead-session recovery
- Any changes to `_psmux.py` (the driver layer is correct)

## Decisions

### shell-path-config

- **Decision:** Add `llm.claude.psmux.shell_path` string key (default: `pwsh`)
  to both the plugin template (`plugins/mill/templates/mill-config.yaml`) and
  the hub `mill-config.yaml`. `millpy-claude-sub.py` reads this key and passes
  the resolved path as `shell_argv[0]` to `_psmux.new_session`.
- **Rationale:** On this machine `pwsh` on PATH resolves to a 0-byte App
  Execution Alias stub. A full path
  (`C:/Code/tools/powershell7/pwsh.exe`) is required. Making it a config key
  keeps the script portable — machines where `pwsh` resolves correctly use the
  default without any change.
- **Rejected:** Hard-coding the absolute path (not portable). Reading `SHELL`
  env var (unreliable on Windows).

### idle-detection-rewrite

- **Decision:** Replace `_wait_for_idle_prompt` and `_wait_for_idle_stable`
  (both check for `❯` which is present in ALL states) with status-bar checks.
  Idle state: status bar contains `for shortcuts`. Processing state: status bar
  contains `esc to interrupt` (captured as `esctointerrupt` without spaces).
  Use a two-phase wait after prompt submission:
  1. Phase 1: wait up to 10s for processing to START (`esc to interrupt` appears)
  2. Phase 2: wait (long timeout) for processing to END (`for shortcuts` appears
     for two consecutive polls 1s apart)
  Boot wait reuses the same `for shortcuts` check — the boot screen shows it
  immediately.
- **Rationale:** Empirically confirmed: `❯` appears in the separator sandwich
  in all three states (boot, processing, idle). The current function returns
  True on the second poll regardless of state, so responses are read before
  they are written. The status bar is the only reliable state discriminator.
- **Rejected:** Spinner-line absence check (`* ` or `✽ `) — spinner character
  set is unstable across claude versions; status bar is more stable.

### extract-response-strip-trailer

- **Decision:** After locating the `bullet_idx` (`● ` line) and before the
  last `❯` (`idle_idx`), walk backwards from `idle_idx` skipping lines that
  are all `─` characters (separator) or start with `✻ ` (completion marker).
  Use the first non-skip line as `content_end_idx`. Extract
  `lines[bullet_idx:content_end_idx+1]`.
- **Rationale:** Current `extract_response` stops at the last `❯`, including
  `✻ Cooked/Brewed/Crunched for Ns` and the separator line in the returned
  text. These are TUI chrome, not response content, and corrupt the text fed
  to downstream reviewers. Verb varies (`Cogitated`, `Crunched`, `Brewed`,
  `Churned`, `Cooked`, `Concocted` ...) so matching on the verb is fragile;
  matching on `✻ ` prefix is reliable.
- **Rejected:** Stripping by regex on the full result string — harder to get
  right for multi-line responses; the line-walk approach is precise.

### reuse-input-clear

- **Decision:** On the reuse path (named `--psmux-session` already exists and
  is idle), send `Escape` to the pane before submitting the next prompt. This
  clears any auto-suggested follow-up text that the claude TUI may have
  pre-filled in the input area after a previous response.
- **Rationale:** Empirically observed: after some responses the TUI fills the
  `❯` input area with a suggested next prompt (e.g. `❯ show an example using
  a generator as a context manager`). Without clearing, the next submitted
  prompt is appended to that suggestion.
- **Rejected:** Doing nothing and hoping the auto-suggest never appears — it
  does appear, and it corrupts the prompt.

## Technical context

**Relevant files:**

- `plugins/mill/scripts/millpy-claude-sub.py` — the psmux wrapper. Contains
  the broken idle detection functions (`_wait_for_idle_prompt` lines 115-133,
  `_wait_for_idle_stable` lines 133-152) and the reuse path (lines 195-219).
  Shell path is hardcoded at lines 213 and 237 as `["pwsh", "-NoLogo",
  "-NoProfile"]`.
- `plugins/mill/scripts/_psmux_capture.py` — `extract_response` function.
  The fix is in the boundary calculation (lines 34-66).
- `plugins/mill/scripts/_psmux.py` — psmux driver. No changes needed.
- `plugins/mill/scripts/_llm_claude.py` — `_invoke` dispatches to
  `millpy-claude-sub.py` when `_get_via_psmux_flag()` is True. No changes
  needed to this layer.
- `plugins/mill/templates/mill-config.yaml` line 105-107 — add `shell_path`
  under `llm.claude.psmux`.
- `mill-config.yaml` lines 10-11 — add `shell_path` under `llm.claude.psmux`.

**Config loading in millpy-claude-sub.py:**
`_resolve_reuse_idle_timeout_s()` (lines 155-167) shows the existing pattern
for reading psmux config: `_config.load_config(_paths.resolve_hub_path(),
_paths.resolve_hub_path())`. Use the same pattern for `shell_path`.

**TUI screen layout (from `doc/psmux-tui-behavior.md`):**
```
[boot/idle]
────────────────────────────────────────
❯ [input or placeholder]
────────────────────────────────────────
  ? for shortcuts · ← for agents        <- IDLE signal

[processing]
✽ Verb…(Xs · ↓N tokens)
 ⎿  Tip: ...
────────────────────────────────────────
❯
────────────────────────────────────────
esc to interrupt                         <- PROCESSING signal

[after response]
● [response text]
✻ Verb for Ns                            <- strip this
────────────────────────────────────────  <- stop extraction here
❯ [next input or auto-suggest]
────────────────────────────────────────
  ? for shortcuts · ← for agents
```

**Multi-line prompt submission:** bracketed paste works.
```
psmux load-buffer -b p <WINDOWS-PATH>
psmux send-keys -l -t session $'\e[200~'
psmux paste-buffer -t session -b p
psmux send-keys -l -t session $'\e[201~'
sleep 1
psmux send-keys -t session Enter
```
File path to `load-buffer` must be Windows-style (`C:\...`), not POSIX
(`/c/...`), because the path is used inside a PowerShell session.

**Session naming:** `millpy-claude-sub.py` already generates
`mill-{session_id[:12]}` names for keep-alive sessions. No change needed.

**Parallel sessions:** tested with 3 simultaneous sessions — no interference.

**Terminal dimensions:** `rows=50` in current code. The 300-word generator
response (longest tested) fit within 60 rows at 220 columns. Keep rows at
60 or higher to avoid `● ` marker scrolling off-screen for long responses.
Current `new_session` calls use `rows=50` — bump to 100 for safety.

## Testing

**`test-psmux-capture.py`** — add cases for:
- Response with `✻ Verb for Ns` line before separator is stripped from result
- Response with separator line stripped
- Auto-suggest text in `❯ <text>` does not appear in extracted result
- Existing passing tests must remain green

**`test-claude-sub.py`** — update / add:
- Boot idle detection uses `for shortcuts` status bar check, not `❯`
- Processing detection uses `esc to interrupt` check
- Two-phase wait: phase 1 waits for processing start, phase 2 for end
- Reuse path sends Escape before prompt submission
- `shell_path` config key is read and passed to `new_session`
- Existing S1-S11 tests updated where idle-detection mock changes

**`test-llm-claude.py`** — existing psmux branch tests (K1-K5, Tests 2-10)
should remain green without change. Add one test confirming `_invoke` passes
`cwd` correctly on the psmux path.

**Integration test `test-claude-psmux.py`** — existing bulk/tool-use/
implementer tests should pass once the primary bug (shell path) is fixed.
Add a keep-alive reuse test: first call with `--psmux-session mill-test-reuse
--keep-alive`, second call to same session, verify response correct and no
auto-suggest contamination.

**Manual verification before enabling `via_psmux: true`:**
Run a full mill-go review cycle (`millpy-review-discussion.py`) with
`via_psmux: true` set in `config.local.yaml`. Confirm verdict is valid.

## Q&A log

- **Q:** Flip `via_psmux: true` as new default in `mill-config.yaml`? **A:** No — test locally first; flip manually after verification.
- **Q:** How does the TUI signal idle vs processing? **A:** Status bar: `? for shortcuts` = idle, `esc to interrupt` = processing. `❯` is present in all states and cannot be used.
- **Q:** Does bracketed paste work for multi-line prompts? **A:** Yes — content arrives at Claude correctly. Newlines display as `\n` in TUI capture but Claude processes them as structured text.
- **Q:** Does `--tools ""` work? **A:** Yes, both `--tools` and `--allowedTools` are accepted by the claude CLI.
- **Q:** Is 1s boot sleep enough? **A:** Yes, confirmed on this machine even with Cortex XDR.
- **Q:** pipe-pane for streaming to Slack? **A:** Does not work on Windows (psmux 3.3.4, tmux 3.3.4) — stub only. Future streaming architecture is a separate Go-based submodule; out of scope here.
