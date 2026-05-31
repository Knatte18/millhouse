# psmux + claude TUI behavior -- empirical findings

Observed 2026-05-31. Session: `replace-claude-p-with-psmux`.
Terminal: `psmux new-session -x 220 -y 60 -- C:/Code/tools/powershell7/pwsh.exe`
Claude version: 2.1.158, Sonnet 4.6.

---

## Shell startup

`psmux new-session -- pwsh` resolves `pwsh` via PATH. On this machine,
`C:\Users\hanf\AppData\Local\Microsoft\WindowsApps\pwsh.exe` is a 0-byte App
Execution Alias stub. The session spawns but the shell is dead. Any `send-keys`
go into a dead pane; `_wait_for_marker_in_pane` polls until timeout (60s) and
returns False -- which causes the hang described in the proposal.

Working path: `C:/Code/tools/powershell7/pwsh.exe`.

Fix: add `llm.claude.psmux.shell_path` config key (default `pwsh`).

---

## Boot / idle screen layout (60-row terminal)

```
 ▐▛███▜▌   Claude Code v2.1.158
▝▜█████▛▘  Sonnet 4.6 with high effort · Claude Max
  ▘▘ ▝▝    C:\...

────────────────────────────────────────────────────────────────────────────────
❯ Try "fix lint errors"
────────────────────────────────────────────────────────────────────────────────
  ? for shortcuts · ← for agents
```

Key markers:
- `❯` input prompt is ALWAYS present in the separator sandwich -- at boot,
  during processing, and when idle. Do NOT use `❯` as an idle signal.
- Status bar (last line): `? for shortcuts · ← for agents` when idle.

---

## Processing screen layout

```
❯ <submitted message text>

✽ Concocting…(6s · ↓261 tokens)
 ⎿  Tip: Ask Claude to create a todo list...

────────────────────────────────────────────────────────────────────────────────
❯
────────────────────────────────────────────────────────────────────────────────
esc to interrupt
```

Key markers:
- Spinner line: `✽ Verb…(Xs · ↓N tokens)` or `· Verb…(...)`. Spinner character
  alternates `✽` / `·`; verb varies (`Concocting`, `Hashing`, `Crunching`,
  `Brewing`, etc.).
- `⎿  Tip: ...` line always appears below the spinner.
- Status bar: `esc to interrupt`.
- `❯` is still present in the separator sandwich (empty, no text).

The current `_wait_for_idle_stable` checks for ANY line starting with `❯`. Since
`❯` is present in all states, this function ALWAYS returns True on the second
poll -- it never actually waits for the response to finish.

---

## Idle screen layout (after response)

```
❯ <submitted message text>

● <response text line 1>
<response continues...>

✻ Verb for Ns

────────────────────────────────────────────────────────────────────────────────
❯
────────────────────────────────────────────────────────────────────────────────
  ? for shortcuts · ← for agents
```

Key markers:
- `● ` (bullet + space): prefix on the FIRST line of Claude's response.
- Completion marker: `✻ Verb for Ns` where Verb varies (`Cogitated`,
  `Crunched`, `Brewed`, `Churned`, `Cooked`, etc.).
- Separator line: a row of `─` characters (`─`).
- Status bar: `? for shortcuts · ← for agents`.

Occasionally the TUI fills the input area with an auto-suggested follow-up:
```
────────────────────────────────────────────────────────────────────────────────
❯ show an example using a generator as a context manager
────────────────────────────────────────────────────────────────────────────────
```
This happens after some responses. It means session reuse must CLEAR the
input area before submitting the next prompt (send Escape or Ctrl+C).

---

## Reliable idle detection

Replace `_wait_for_idle_prompt` and `_wait_for_idle_stable` with status-bar checks:

```python
def _is_idle(capture: str) -> bool:
    """Return True if the capture shows the idle status bar."""
    for line in capture.splitlines():
        if "for shortcuts" in line:
            return True
    return False

def _is_processing(capture: str) -> bool:
    """Return True if the capture shows the processing status bar."""
    for line in capture.splitlines():
        if "esc to interrupt" in line or "esctointerrupt" in line:
            return True
    return False
```

Two-phase response wait:

1. After sending prompt, wait up to ~10s for `_is_processing()` to become True.
   (Guards against reading a stale capture before the spinner appears.)
2. Then wait (with long timeout) for `_is_idle()` to become True for two
   consecutive polls 1s apart.

Both phases use `capture_pane(..., alternate=True)`. No `-S` scrollback needed
for alternate screen -- psmux always returns exactly `rows` lines for it.

Boot wait (`_wait_for_idle_prompt`): same `_is_idle()` check works, since the
boot screen shows `? for shortcuts` immediately.

---

## Response extraction

Current `extract_response` in `_psmux_capture.py` finds the LAST `❯` line
as the upper boundary and searches backwards for the LAST `● ` as the lower
boundary. This correctly identifies the most recent response.

Problem: the extracted slice includes trailing garbage:
- `✻ Verb for Ns` (completion marker)
- Separator line (`────────...`)

Fix: after finding `bullet_idx`, walk forward but stop before the first
separator line or `✻ ` line. Concretely: the end of response content is the
last line (going forward from `bullet_idx`) that does NOT start with `✻` and
is NOT a separator (all `─` chars).

Alternatively: walk backwards from `idle_idx`, skip separator and `✻` lines,
use the first non-skip line as `content_end_idx`.

---

## Multi-line prompt submission (bracketed paste)

Verified working:

```
psmux load-buffer -b p <windows-path-to-prompt-file>
psmux send-keys -l -t <session> $'\e[200~'
psmux paste-buffer -t <session> -b p
psmux send-keys -l -t <session> $'\e[201~'
sleep 1
psmux send-keys -t <session> Enter
```

The input area shows newlines as `\n` in the screen capture (e.g.,
`❯ Line A.\nLine B.\nReply DONE.`), but Claude receives and correctly
processes the content as structured multi-line text.

The bracketed paste START (`\e[200~`) and END (`\e[201~`) must be sent with
`send-keys -l` (literal flag). Without `-l`, psmux tries to interpret them
as key names and they are dropped.

Prompt file must be loaded with a Windows-style path
(`C:\...`) when psmux is running a PowerShell session. POSIX paths
(`/c/...`) fail on Windows.

---

## Parallel sessions

Three simultaneous sessions (`probe-a`, `probe-b`, `probe-c`) each running
their own `claude` TUI: all start and respond independently with no
cross-contamination. No psmux-side limitations observed at 3 sessions.

---

## Terminal size and response length

At 60 rows x 220 cols, a ~300-word response (generator explanation) fits
within the visible alternate screen. The `● ` bullet marker remains visible
when the response is fully rendered.

If responses grow beyond ~50 lines, the `● ` marker will scroll off the
top of the visible area and `extract_response` will raise `MarkerNotFoundError`.
For safety, use at least 100 rows when creating new sessions. Review prompts
can produce long responses.

---

## Alternate screen capture note

`psmux capture-pane -a -S -N -p` with large N does NOT return extra history
for the alternate screen -- it always returns exactly `rows` lines. The `-S`
flag is a no-op for alternate screen. Use `psmux capture-pane -a -p` (no -S).

---

## Config keys needed

In `mill-config.yaml` / template, under `llm.claude.psmux`:

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `via_psmux` | bool | false | Route through psmux instead of `claude -p` |
| `shell_path` | str | `pwsh` | Shell binary for `new_session`. Use full path on Windows where PATH stub is broken. |
| `reuse_idle_timeout_s` | int | 10 | Seconds to wait for existing session to become idle before reuse fails. |

---

## Summary of bugs in current implementation

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| 1 | `millpy-claude-sub.py:213,237` | `shell_argv=["pwsh", ...]` resolves broken PATH stub | Read `shell_path` from config |
| 2 | `millpy-claude-sub.py:115-152` | `_wait_for_idle_prompt` and `_wait_for_idle_stable` use `❯` which is ALWAYS present | Use status bar text instead |
| 3 | `_psmux_capture.py:extract_response` | Extracted text includes `✻ Verb for Ns` and separator line | Stop extraction before separator/`✻` |
| 4 | `millpy-claude-sub.py` | No input-area clear before reuse; auto-suggest text from previous response leaks into next prompt | Send Escape before submitting on reuse path |

---

## Verified non-issues (from proposal's secondary suspects)

- `--tools ""` flag: valid. `millpy-claude-sub.py` uses `["--tools", ""]` for
  bulk mode; the claude CLI accepts both `--tools` and `--allowedTools`.
- Boot sleep (1s after `new_session`): sufficient on this machine even with
  Cortex XDR scanning. `CLAUDE_READY` probe returned within 1s.
- `send_keys("Enter", enter=False)`: sends `psmux send-keys -t session Enter`
  which psmux interprets as the Enter key (special key name, not literal text).
  Confirmed working.
- Unicode `❯` codec: `capture_pane` returns UTF-8 on this machine; `❯`
  compares correctly. No cp1252 issue observed.

---

## pipe-pane: does NOT work on Windows (psmux 3.3.4 / tmux 3.3.4)

`psmux pipe-pane -t session "cat >> logfile"` and the equivalent tmux command
both return exit 0 but pipe no data. Tested with psmux and tmux, with bash
session and pwsh session, with multiple path formats and shell wrappers. Files
are created (0 bytes) or not created at all. This is a known limitation of
Windows ports of tmux -- the pipe mechanism requires OS-level pty forking that
these ports do not fully implement.

**Architectural implication:** streaming output to file via `pipe-pane` is not
available on this machine. The "stream to file then framework reads it"
architecture described in the long-term vision requires an alternative
implementation.

**Working alternative -- polling differ:**
A background Python process polls `capture-pane` every ~0.5s, diffs each
capture against the previous one, and appends genuinely new lines to a log
file. Any downstream consumer (Slack bot, file watcher) tails that file.

```python
# Sketch of polling differ
prev_lines = set()
while True:
    capture = _psmux.capture_pane(session, alternate=True)
    new_lines = [l for l in capture.splitlines() if l.strip() and l not in prev_lines]
    if new_lines:
        with open(logfile, "a") as f:
            f.write("\n".join(new_lines) + "\n")
    prev_lines = set(capture.splitlines())
    time.sleep(0.5)
```

Caveats: does not capture lines that scroll off the visible viewport between
polls; may have ordering issues for rapid output. Suitable for the current
mill use case (responses complete before the next poll cycle) but not for
true real-time streaming.

**Longer-term option:** run the session inside WSL where real tmux `pipe-pane`
works. Then the log file is a genuine VT100 byte stream that requires
ANSI-stripping before use.

---

## capture-pane latency

Measured on this machine (20 consecutive calls, claude TUI active in session):

```
min:  19.6ms
max:  26.9ms
avg:  22.9ms
```

At a 0.5s polling interval, capture-pane overhead is ~4-5% of wall-clock.
Not a bottleneck. A poller daemon running at 500ms intervals is practical.

**Go implementation note:** for the long-term Slack streaming framework, Go
is the right language. One goroutine per psmux session, ticker at 500ms,
`exec.Command("psmux", "capture-pane", ...)`, diff logic, Slack webhook push.
23ms per call is negligible. This is a separate submodule/repo from mill.
