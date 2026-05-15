# Discussion: Wrap `claude -p` via psmux to use subscription instead of API credits

```yaml
task: Wrap claude -p via psmux to use subscription instead of API credits
slug: claude-p-wrapper
status: discussing
parent: main
```

## Problem

Mill uses `claude -p` (headless print mode) for every reviewer and implementer
spawn. On a Claude Max subscription, `claude -p` calls bill against API credits,
not against the subscription -- with three parallel `mill-go` sessions running,
$200/month of API credits is consumed in roughly a day. Interactive `claude`
sessions (no `-p` flag) are covered by the subscription. The goal is to route
mill's programmatic calls through subscription billing by automating an
interactive `claude` session via `psmux`, returning text-in / text-out so the
existing Python LLM-provider layer can call it as a drop-in replacement for
`claude -p`.

**Why now:** the cost burn is daily and ongoing. The subscription is already
paid. Operator (the user) has already confirmed in the Anthropic dashboard that
interactive `claude` draws against the subscription -- the billing premise is
not in question.

This task is scoped as a **spike**. Goal: produce a working standalone Python
wrapper, exercise it against representative mill-style prompts, and write a
go/no-go report. **No changes** to `_llm_claude.py`, reviewer modules, prompt
templates, or wiki configs in this task -- those land in a follow-up task once
the spike says go.

## Scope

**In:**
- A new standalone Python script `plugins/mill/scripts/millpy-claude-sub.py`
  that replaces `claude -p` invocations end-to-end: takes a prompt on stdin,
  returns Claude's response text on stdout, returns a one-line JSON metadata
  envelope on stderr (`session_id`, `duration_s`, `mode`).
- Three invocation modes: `bulk` (Claude launched with `--tools ""`), `tool-use`
  (Claude launched with `--allowedTools "Read,Grep,Glob"`), `implementer`
  (Claude launched with `--allowedTools "Read,Edit,Write,Bash,Grep,Glob,Skill"`).
  Mode is a CLI flag (`--mode bulk|tool-use|implementer`); the tool list is
  hardcoded per mode and is NOT a caller-supplied parameter.
- Pass-through CLI flags that map to the corresponding `_llm_claude._build_argv`
  flags: `--model <name>`, `--effort <low|medium|high|xhigh|max>` (optional),
  `--session-id <uuid>` (optional; if omitted the wrapper generates one and
  passes it to `claude --session-id` at launch so the returned id is real),
  `--system-prompt <path>` (optional; reads the system prompt from the file).
  `--resume <id>` is OUT (see `## Out`).
- A pure-Python output parser in `plugins/mill/scripts/_psmux_capture.py` that
  takes a capture-pane text blob plus the sentinel string and returns the
  extracted response. Fully unit-testable against fixtures, no psmux needed.
- A `psmux`-driver module `plugins/mill/scripts/_psmux.py` that wraps the small
  set of psmux commands the wrapper uses (`new-session`, `load-buffer`,
  `paste-buffer`, `send-keys`, `capture-pane`, `kill-session`). Thin shim over
  `subprocess.run`; isolates the subprocess calls from the main script for
  testability.
- Unit tests for the parser (`plugins/mill/unit_tests/test-psmux-capture.py`)
  with fixtures covering the cases observed in the PoC (clean response,
  whitespace-compressed line, "Cogitated for Ns" status text between prompt
  echo and response, sentinel mid-response in a quoted block, sentinel never
  appears -- must time out, response longer than the visible pane requiring
  scrollback retrieval).
- An integration test `plugins/mill/integration_tests/test-claude-psmux.py`
  that actually drives psmux + claude end-to-end with a tiny prompt in each of
  the three modes. Skipped automatically when `psmux` or `claude` is not on
  PATH; not part of `unit_tests/run-all.py`.
- A go/no-go report at `_mill/spike-report.md` (committed on the task branch,
  not in the wiki). Records: PoC outcomes, observed limitations, recommended
  follow-up scope, blockers (if any). Decision-grade, not narrative.

**Out:**
- Any modification to `plugins/mill/scripts/_llm_claude.py`. The wrapper exists
  alongside it and is exercised via the integration test only. Wiring it into
  `_llm_claude` is the follow-up task's job.
- Any modification to reviewer modules (`_review_*.py`, `_reviewer_*.py`),
  prompt templates (`plugins/mill/templates/*.md`), or wiki configs.
- The reviewer-naming refactor (`sonnet` = with tools, `sonnet_bulk` = without)
  -- separate task. Touches every wiki/config.yaml that names a reviewer.
- Multi-provider equivalents (a Gemini-on-subscription wrapper, etc.). Same
  pattern would generalise but is not in this scope; nothing in `_llm_gemini.py`
  changes.
- Session-resume across calls. The wrapper does NOT support `--resume <id>`;
  every call spawns a fresh psmux session and tears it down. The session_id
  returned is for traceability only, not for re-entry. Resume support is
  follow-up work.
- Rate-limit detection equivalent to `_llm_claude._scan_rate_limit`. The wrapper
  surfaces non-zero exits as generic errors; classification is follow-up work.
- Stream-json output / partial-message streaming back to the caller. The
  wrapper is text-only.
- Pre-warmed psmux session pooling. Boot is ~6-8s per call; that overhead is
  accepted for the spike. Pool optimisation is follow-up if it bites in
  practice.
- Any installation work for `psmux` or `pwsh`. Both are operator prerequisites
  and are already installed (verified in this session: `psmux 3.3.4` at
  `C:\Code\tools\psmux\psmux.exe`; `pwsh 7.6.1` at
  `%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe`).

## Decisions

### Wrapper is text-in / text-out, not file-IO

- Decision: The wrapper signature mirrors `claude -p` exactly: prompt on stdin,
  response on stdout. It does NOT instruct interactive `claude` to write its
  response to a file via tool access.
- Rationale: Provider symmetry. `_llm_gemini.py`, `_llm_ollama.*` etc. don't
  rely on tool access -- they're text-completion APIs. The mill provider
  abstraction (`run_bulk` / `run_tool_use` / `run_implementer`) is text-in /
  text-out across the board. A file-IO Claude wrapper would diverge from that
  contract and force every caller to special-case the Claude path. Reviewer
  modules already own the file-write step today (review file, fixer report);
  that stays unchanged.
- Rejected: Have interactive `claude` use Write tool to drop the response into
  a known path; wrapper returns only the path. Cleaner under-the-hood for
  Claude but breaks the cross-provider contract.

### Bulk mode is a first-class peer of tool-use mode, not a degraded fallback

- Decision: The wrapper exposes `bulk` and `tool-use` reviewer modes as equal
  citizens. `bulk` launches `claude --tools ""` (no tool access at all);
  `tool-use` launches `claude --allowedTools "Read,Grep,Glob"`.
- Rationale: Operator experience with Gemini reviewers running in tool-use
  mode -- the model issued so many tool calls per review that the turn count
  exhausted the session before producing a verdict. `bulk` (where the wrapper
  caller pre-concatenates all relevant files into the prompt) is the workaround,
  and it must remain a fully-supported path through any new wrapper. Bulk is
  not "tool-use without tools"; it's a different review strategy.
- Rejected: `tool-use` only, push bulk to a follow-up. Would block any reviewer
  config currently using a `_bulk` reviewer name.

### Mode-implicit tool-set; caller does NOT pick `--allowedTools`

- Decision: The mode flag (`--mode bulk|tool-use|implementer`) deterministically
  selects the tool list. Callers cannot override the tool set for a given mode.
- Rationale: Operator stated this directly: "I think it should be obvious which
  tools are needed for review. Not something I need to think about." Each mode
  has one canonical tool set, identical to what `_llm_claude.run_bulk` /
  `run_tool_use` / `run_implementer` already encode. Centralising the choice
  eliminates a configuration knob that would inevitably drift.
- Rejected: Expose `--allowedTools` as a CLI flag for callers to set. Adds a
  knob with no current consumer, breaks symmetry with mode-named API surface.

### Use `paste-buffer` (via `load-buffer -b`) for prompt delivery, NOT `send-keys`

- Decision: The wrapper writes the prompt to a temporary file, runs
  `psmux load-buffer -b <name> <file>`, then `psmux paste-buffer -t <session> -b <name>`,
  then `psmux send-keys -t <session> Enter` to submit. `send-keys` is used ONLY
  for control keys (Enter, Esc), never for prompt body content.
- Rationale: Verified empirically in this session's PoC. Raw `send-keys` of a
  124-char prompt dropped the substring ` End ` between two adjacent words --
  five characters lost silently. `paste-buffer` of the same string round-tripped
  losslessly. `send-keys` races the Claude TUI's input handler; the buffer-paste
  path delivers atomically.
- Rejected: send-keys with `-l` (literal) or per-character pacing. Too
  fragile; paste-buffer is the standard tmux/psmux idiom for multi-line content.

### Sentinel = `MILL_DONE_<rand>`; per-call randomised suffix

- Decision: Each invocation generates a sentinel of the form
  `MILL_DONE_<8-hex-chars>` (e.g. `MILL_DONE_ba509639`) and appends an
  instruction to the prompt: `End your final reply with the literal text
  MILL_DONE_xxxxxxxx on its own line.` The wrapper polls capture-pane for
  the sentinel on its own line.
- Rationale: A fixed `<<<MILL_DONE>>>` could collide if a prompt contains
  source code or transcripts that quote it; a per-call random suffix
  eliminates collision risk for the lifetime of the session. Verified in PoC
  -- random suffix appears verbatim in the response.
- Rejected: Fixed sentinel (collision risk); no sentinel and rely solely on
  the empty `❯` prompt line returning to idle (less reliable: TUI may briefly
  redraw to idle between Claude's output chunks).

### Dual idle signal: sentinel-on-own-line AND idle prompt

- Decision: The wrapper considers Claude "done" only when BOTH conditions
  hold in a `capture-pane` snapshot: (a) the sentinel string appears on a
  line by itself (after stripping leading/trailing whitespace), AND (b) the
  most recent `❯ ` input-prompt line is empty (no in-progress text).
- Rationale: Sentinel-only could fire before Claude has fully finalised its
  output (rare, but the TUI can render the sentinel and then a follow-up
  status line). Idle-prompt-only is unreliable because the TUI briefly
  re-renders the empty prompt between streamed output chunks. Both together
  is a strong signal.
- Rejected: Sentinel-only (fragile under streaming); file-existence (would
  require the file-IO design we explicitly rejected above).

### Per-call psmux session, UUID-suffixed name, torn down after each call

- Decision: Each wrapper invocation generates `session_name = f"mill-{uuid4().hex[:8]}"`,
  creates a new psmux session with that name, runs the prompt, then
  `psmux kill-session -t <session_name>`. Session lifecycle = one wrapper call.
  Cleanup runs in a `finally` block so a failing call still tears down its
  session.
- Rationale: Mill spawns multiple reviewers and implementers in parallel
  (mill-go fans out batches; review CLI scripts may run concurrently with
  each other). Sessions must not collide. UUID suffixing guarantees
  uniqueness; per-call lifecycle keeps the model simple and prevents
  cross-call state leak. Boot overhead (~6-8s/call) is accepted for the
  spike; pooling is follow-up work if it bites.
- Rejected: Single shared session reused across calls (collides under
  parallelism, requires reset-between-calls protocol Claude TUI does not
  cleanly expose); pre-warmed session pool (premature, complicates lifecycle).

### Standalone CLI script, not a Python module imported by `_llm_claude.py`

- Decision: The wrapper ships as `plugins/mill/scripts/millpy-claude-sub.py`,
  invoked as a subprocess. `_llm_claude.py` is NOT modified in this task.
- Rationale: The spike's purpose is to validate the wrapper works in
  isolation. Keeping it as a standalone script means the integration test
  exercises the exact contract a follow-up task will use to wire it into
  `_llm_claude.py`. It also keeps the surface area small enough to grade.
- Rejected: Land as `_claude_psmux.py` module called in-process by
  `_llm_claude.py`. Tighter coupling and harder to grade as a spike artifact.

### `--system-prompt` accepts a FILE PATH, not a literal string

- Decision: `--system-prompt <path>` takes a path to a file containing the
  system prompt; the wrapper passes the file's contents to `claude --system-prompt`
  via the `claude` flag of the same name (which itself takes a string).
- Rationale: Mill prompts are kilobytes. A literal-string CLI argument hits
  Windows's command-line length cap (~8K) and shell-quoting hell. A file
  path is robust and matches the prompt-stdin pattern.
- Rejected: Accept the system prompt as a literal string argument. Breaks
  on long prompts.

## Technical context

**Existing code mill-plan must understand before writing the plan:**

- `plugins/mill/scripts/_llm_claude.py` -- the LLM-provider wrapper around
  `claude -p`. Defines the public API (`run_bulk` / `run_tool_use` /
  `run_implementer`) the new wrapper mirrors at the CLI level. Read
  `_build_argv` for the flag layout the new wrapper must produce when
  launching interactive `claude`. Note `_scan_rate_limit` (out of scope but
  worth knowing exists) and `_parse_stream_json` (irrelevant -- interactive
  mode does not emit stream-json).
- `plugins/mill/scripts/_subprocess_util.py` -- the project's subprocess
  helper. The new `_psmux.py` shim should use this for all psmux subprocess
  calls so logging is consistent with the rest of mill (timeouts, stderr
  echo, etc.).
- `plugins/mill/scripts/_paths.py` -- path resolution. The wrapper writes
  its temporary prompt file to `<git_root>/.scratch/wrapper-<uuid>-prompt.txt`
  via `_paths.resolve_git_root()` to find the cwd's git root. (Per
  `mill:conversation`, never write to `/tmp/` or `$env:TEMP`.)
- `plugins/mill/scripts/_timestamp.py` -- timestamp helpers if the wrapper
  logs to stderr with absolute times.
- `plugins/mill/scripts/_llm_common.py` -- defines `LLMError`,
  `LLMSessionError`, `LLMRateLimitError`. The wrapper exit codes should
  align with these classes' semantics so a future `_llm_claude.py`
  integration can map them: exit 0 = success; exit non-zero = `LLMError`;
  no separate exit code for rate-limit (out of spike scope; surfaces as
  generic non-zero exit with stderr text).

**psmux command vocabulary used by the wrapper (verified in this session):**

| psmux command                                 | Purpose                                          |
|-----------------------------------------------|--------------------------------------------------|
| `new-session -d -s <name> -x 200 -y 50 -- pwsh -NoLogo -NoProfile` | Create detached session with 200x50 pane running pwsh 7. |
| `set-option -t <name> -g history-limit 50000` | Increase pane scrollback so long responses fit. (NOTE: syntax to be verified during implementation; psmux options page may differ from tmux.) |
| `send-keys -t <name> "<text>" Enter`          | Send a short literal command to the pane (used to launch `claude`, not for prompt body). |
| `load-buffer -b <buf> <file>`                 | Load file contents into a named paste buffer.    |
| `paste-buffer -t <name> -b <buf>`             | Paste buffer contents into the active pane (lossless). |
| `send-keys -t <name> Enter`                   | Submit the pasted prompt.                        |
| `capture-pane -t <name> -S -<N> -p`           | Capture last N lines of pane scrollback (incl. content above the visible window) to stdout. ANSI-stripped already. |
| `kill-session -t <name>`                      | Tear down a session.                             |

**Verified Claude CLI flags accepted in interactive (non-`-p`) mode** (from
`claude --help` in this session and the live PoC): `--allowedTools <list>`,
`--tools <list>` (use `""` for none), `--model <name>`, `--effort <level>`,
`--session-id <uuid>`, `--system-prompt <string>`. Flags `--print` (`-p`),
`--output-format`, `--input-format`, `--max-budget-usd` are documented as
"-p only" -- do NOT pass them to interactive sessions.

**Pane size: 200 cols x 50 rows.** The TUI's wrapping behaviour depends on
column count. Wider columns mean fewer wrapped lines mean cleaner parsing.
200 was used in the PoC; do not narrow it.

**Boot time:** Claude TUI takes ~6-8 seconds from `claude` keystroke to
ready-for-input. The wrapper polls capture-pane for the empty `❯ ` input
line as the readiness signal, with a 20-second timeout. Hardcoded timeout
not config-driven for the spike.

**Whitespace fidelity is imperfect.** Verified in PoC: capture-pane
occasionally renders adjacent words without spaces between them
(`PowerShellthreadsweaveasone`). Cause is the TUI's compressed grid render
in some contexts. This is acceptable for review markdown (heading + bullet
structure unaffected) and conversational implementer responses, but it is
NOT a verbatim text channel. Document this prominently in the spike report
so the follow-up integration task makes an informed call about whether to
e.g. ask Claude to wrap responses in fenced code blocks for fidelity.

## Constraints

- **All `print()` and stderr-log strings ASCII only.** Em-dash → ` -- `,
  arrow → ` -> `. CLAUDE.md `## Conventions worth carrying`.
- **Cache-form invocation.** The wrapper script must be runnable as
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-claude-sub.py" ...`.
  No hardcoded `plugins/mill/...` paths in production code paths. Test scripts
  may use the source-tree form per CLAUDE.md.
- **Scratch lives at `<git_root>/.scratch/`**, not `/tmp/`, not under
  `.millhouse/`. Per `mill:conversation` File Writing rules.
- **`finally`-block teardown for psmux sessions.** Any code path that creates
  a session must guarantee `kill-session` runs, even on exception. Leaked
  sessions are silent because they're detached.
- **Cleanup of temp prompt file** in the same `finally`. Matches session
  lifecycle.
- **Subprocess timeouts on every psmux call.** A hung psmux command must not
  block the wrapper indefinitely. Default 30s per psmux command, configurable
  via env var (no wiki/config wiring in this task).
- **No `cd .wiki/` or `cwd=<wiki_path>`.** Wrapper does not touch wiki
  state. Resolves git root via `_paths.resolve_git_root()` for the scratch
  directory only.
- **Tests must not run real `claude`** in `unit_tests/`. The integration
  test that does run real `claude` lives in `integration_tests/` and is
  manually invoked, not part of `run-all.py`. (Per CLAUDE.md repo layout
  pointers.)

## Testing

**Parser unit tests** (`plugins/mill/unit_tests/test-psmux-capture.py`) --
pure-function tests on `_psmux_capture.extract_response(capture_text, sentinel)`.
Each test loads a static fixture from a sibling `fixtures/` directory and
asserts the extracted response. Fixture cases:

1. `clean.txt` -- a simple PoC-style capture with prompt echo, single `●`
   response line, sentinel on its own line, idle prompt at bottom. Expected
   output: just the response line.
2. `multiline.txt` -- a multi-line response (e.g. the haiku PoC). Expected
   output: the full multi-line block, sentinel and idle prompt stripped.
3. `with-status.txt` -- response followed by a `✻ Cogitated for 3s` status
   line before the sentinel. Status line must be stripped.
4. `with-scrollback.txt` -- response longer than 50 lines (simulates
   scrollback retrieval); confirms parser does not truncate.
5. `whitespace-compressed.txt` -- a response line missing a space between
   words (the TUI artifact). Parser passes it through unchanged; the test
   asserts the wrapper does NOT try to "fix" whitespace (operator decision
   in spike report).
6. `quoted-sentinel.txt` -- the sentinel string appears mid-response inside
   a quoted code block, but also at the end on its own line. Parser must
   ignore the mid-block occurrence (because it is not on its own line) and
   detect the trailing one.
7. `no-sentinel.txt` -- sentinel never appears. Parser raises a documented
   exception (`SentinelNotFound`); wrapper translates this to non-zero exit
   with stderr explanation.
8. `empty-prompt-during-output.txt` -- the input `❯ ` line briefly empties
   between output chunks. Parser only fires when both conditions hold;
   regression test for the dual-idle-signal decision. (For unit-test
   purposes this captures the snapshot at the wrong moment; assert that the
   parser reports "not yet done", not a false positive.)

**Driver unit tests** (`plugins/mill/unit_tests/test-psmux-driver.py`) --
mock `_subprocess_util.run` and verify `_psmux.py` builds the right argv
for each helper (`new_session`, `paste_buffer`, etc.). One test per command.
TDD-friendly; write tests first.

**Integration test** (`plugins/mill/integration_tests/test-claude-psmux.py`)
-- manually invoked, skips with a clear message when `psmux` or `claude` is
not on PATH. Three sub-tests:

1. `bulk` mode: prompt = "Reply with the single word PONG and nothing else.
   End your final reply with the literal text <sentinel> on its own line."
   Assert response contains `PONG` and does NOT contain the sentinel.
2. `tool-use` mode: prompt = "List the names of the files in the current
   directory using the Glob tool, then end your reply with <sentinel>."
   Assert response is non-empty and the wrapper exited cleanly.
3. `implementer` mode: prompt = "Use the Bash tool to run `echo
   __INTEGRATION_OK__`, then end with <sentinel>." Assert response contains
   `__INTEGRATION_OK__`.

For each sub-test, also assert: psmux session was killed after the call
(verify via `psmux ls` should not list the session name); the temp prompt
file was cleaned up; the JSON metadata line on stderr is well-formed.

**Manual operator validation** (recorded in `_mill/spike-report.md`):
operator runs the integration test, then opens the Anthropic dashboard and
confirms the test invocations show as **subscription usage**, not API
credit usage. This is the load-bearing acceptance check; the wrapper is
worthless if it still bills as API.

**TDD candidates:** the parser (pure function, fixture-driven, ideal for
TDD) and the `_psmux.py` driver (mock-based, write tests for each command's
argv before implementation).

## Q&A log

- **Q:** Has subscription billing for interactive `claude` been verified?
  **A:** Yes -- operator confirmed in the Anthropic dashboard. Premise locked.
- **Q:** Is `psmux` installed and on PATH? **A:** Verified live in this
  session: `psmux 3.3.4` at `C:\Code\tools\psmux\psmux.exe`, accessible from
  both bash and PowerShell.
- **Q:** Does this need PowerShell 7 (`pwsh`)? **A:** Probably yes for
  reliability inside the psmux pane (the proposal's claim that PS 5.1 will
  not work was Claude Code's own assertion, not Ole's). Operator installed
  `pwsh 7.6.1` during this session. Wrapper launches the pane shell as
  `pwsh -NoLogo -NoProfile`.
- **Q:** Should the Anthropic Agent SDK on subscription be evaluated as an
  alternative? **A:** No -- the SDK is API-billed, not subscription-billed.
  Rejected.
- **Q:** Should the wrapper return Claude's text, or have Claude write its
  output to a file via Write tool? **A:** Return text. Cross-provider
  symmetry (Gemini, Ollama have no tool access) requires text-in / text-out.
  Reviewer modules continue to own file-writing.
- **Q:** Is bulk mode a degraded fallback or a first-class peer of tool-use
  mode? **A:** First-class peer. Operator hit Gemini-tool-storm crashes
  (too many tool-call turns exhausted the session) and built bulk mode as
  the workaround; bulk must remain fully supported.
- **Q:** Does the caller specify `--allowedTools`? **A:** No. The mode flag
  (`bulk`/`tool-use`/`implementer`) deterministically selects the tool set;
  caller cannot override.
- **Q:** Is the reviewer-naming refactor (`sonnet` with tools as default,
  `sonnet_bulk` without) part of this task? **A:** No -- separate follow-up
  task. Touches every wiki/config.yaml that names a reviewer.
- **Q:** Does `paste-buffer` deliver prompts losslessly where `send-keys`
  loses characters? **A:** Verified live -- the same 124-char prompt that
  send-keys mangled (dropped ` End `) round-tripped cleanly via `load-buffer`
  + `paste-buffer`. Decision locked.
- **Q:** Does psmux retain scrollback for capture? **A:** Verified live --
  `capture-pane -S -200 -p` retrieved all 100 lines of a 100-line emission.
  The wrapper will set a high `history-limit` at session creation and
  capture with `-S -50000`.
- **Q:** Does interactive `claude` accept `--allowedTools` and `--tools ""`?
  **A:** Yes. Verified via `claude --help` output and a live `claude
  --tools ""` launch in psmux that responded cleanly with no permission
  prompts. The full mill set of CLI flags (`--allowedTools`, `--tools`,
  `--model`, `--effort`, `--session-id`, `--resume`, `--system-prompt`) is
  available in interactive mode.
- **Q:** Is the wrapper standalone or imported by `_llm_claude.py` in this
  task? **A:** Standalone -- ships as `millpy-claude-sub.py`, exercised via
  the integration test. `_llm_claude.py` is untouched. Wiring is
  follow-up work.
- **Q:** What's the spike's pass criterion? **A:** All three integration
  sub-tests pass on operator's machine, AND the operator confirms
  subscription billing in the Anthropic dashboard for those calls.
