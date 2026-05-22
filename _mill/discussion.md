# Discussion: Replace psmux marker protocol with idle-prompt detection

```yaml
task: Replace psmux marker protocol with idle-prompt detection
slug: psmux-idle-prompt-detection
status: discussing
parent: main
```

## Problem

`millpy-claude-sub.py` wraps an interactive Claude TUI session running in psmux
to route review and implementer calls through a subscription account instead of
API credits. The current protocol injects `MILL_BEGIN_xxx`/`MILL_END_xxx` tokens
into every prompt footer and polls the pane for those tokens to detect when Claude
has finished replying.

Two concrete failures motivated this task: Haiku explicitly identified the footer
as "a prompt injection attempt" and ignored it; and the in-line check for the
begin-marker triggered on the echoed prompt text rather than Claude's response,
causing a `duration_s: 0.0` false positive. Both are patched but point at a deeper
brittleness: the marker protocol depends on Claude faithfully following an injected
instruction while screen-scraping a TUI that may reformat or reorder output.

The idle-prompt character `❯` that the Claude TUI shows between turns is already
used in `_wait_for_idle_prompt` for reuse-check and boot detection. The same
signal is sufficient to detect response completion — no injected text required.

## Scope

**In:**
- Remove footer injection and marker generation from `millpy-claude-sub.py`
- Replace the marker-polling loop (Step 11) with idle-prompt stability detection
  and snapshot-based response extraction
- Rewrite `_psmux_capture.py` with a new `extract_response(snapshot)` API that
  works from the pane snapshot alone — no markers
- Add `_wait_for_idle_stable()` function in `millpy-claude-sub.py`
- Rewrite `test-psmux-capture.py` with inline fixture strings matching the new API
- Update `test-claude-sub.py` mock signatures and success-path test to match the
  new flow; keep reuse/keepalive tests with minimal changes
- Delete all fixture files under `unit_tests/fixtures/psmux-capture/` (all are
  marker-based; none apply to the new extraction)

**Out:**
- Auto-resume on TUI exit (`claude --resume <id>`) — Phase 2 only
- Configurable idle character — hardcoded `❯` for now
- Changes to `_llm_claude.py`, `_psmux.py`, `_llm_common.py`, or any other script
- Changes to `test-llm-claude.py` — it tests `_llm_claude._build_psmux_argv`
  argv shapes which are unaffected
- `MILL_REVIEW_BEGIN`/`MILL_REVIEW_END` markers in `_llm_claude.py` — those
  are orchestrator-log delimiters, not TUI response markers; unaffected

## Decisions

### Extract from snapshot B alone; no snapshot A baseline

- Decision: Extract Claude's response entirely from a single post-response
  snapshot (`snapshot_b`). Do not capture a pre-submit snapshot (`snapshot_a`)
  for alignment or diffing.
- Rationale: The extraction algorithm (find the last `●` before the final `❯`)
  works correctly in a reused session with prior history because it always finds
  the *most recent* response. There is no alignment problem to solve. Capturing
  snapshot A and diffing against it would introduce fragility (fixed-width grid
  reflow, line-count drift) for no benefit.
- Rejected: Snapshot A as line-count baseline — fragile. Snapshot A as
  safety check only — dead code; adds API surface for no coverage benefit.

### Response extraction algorithm

- Decision: Given `snapshot_b` (a `capture_pane` string after stable idle):
  1. Find the last line whose `.strip()` starts with `❯` — that is the new
     input prompt at the end of the response.
  2. Working backwards from that line, find the first line whose `.strip()`
     starts with `● ` — that is the first line of Claude's response.
  3. Extract from that bullet line up to (not including) the idle-char line.
  4. Strip `● ` (2 chars) from the first extracted line's stripped form.
  5. Return the joined lines, stripped of leading/trailing whitespace.
- Rationale: Claude TUI prepends `●` to the first line of every response only
  (not continuation lines). Finding the last `●` before the final `❯` isolates
  the most recent response regardless of session history length.
- Rejected: Filtering all `●`-prefixed lines — only first line has the prefix;
  continuation lines would be lost. Snapshot diff — fragile against grid reflow.

### Stability check: two consecutive idle sightings

- Decision: Add `_wait_for_idle_stable(session_name, timeout_s)` alongside the
  existing `_wait_for_idle_prompt`. It requires `❯` to appear as the leading
  character of some line in two consecutive `capture_pane` calls separated by
  `POLL_INTERVAL_S` (1 second). Returns `True` on stable match, `False` on
  timeout.
- Rationale: Tool-call loops show transient `❯` between steps; a single sighting
  would extract a partial response. The 1s gap between two sightings is sufficient
  to distinguish a complete response from a transient prompt state.
- Rejected: Single sighting — false positives during tool-call loops. Single
  sighting with fixed sleep — brittle for slow tool-calls where sleep may not
  cover the gap.

### Keep `_psmux_capture.py`, replace its content

- Decision: Rewrite `_psmux_capture.py` in place. The new public API is:
  - `extract_response(snapshot: str) -> str` — raises `MarkerNotFoundError`
    if `●` or `❯` are absent from `snapshot`
  - `MarkerNotFoundError` — exception class, name preserved
  Keep the module name and exception name unchanged to avoid scatter in imports
  and mocks.
- Rationale: `millpy-claude-sub.py` imports both symbols by name. Keeping the
  names means only the call-site signature changes (`extract_response(snapshot)`
  instead of `extract_response(capture, begin, end)`).
- Rejected: Delete the file and inline extraction in `millpy-claude-sub.py` —
  pure functions in a separate module are easier to unit-test in isolation.
  New file with new name — unnecessary churn in imports.

### Replace fixture files with inline strings in tests

- Decision: Delete all files under `unit_tests/fixtures/psmux-capture/`
  (all nine files are marker-based). Replace the fixture-loading logic in
  `test-psmux-capture.py` with inline multi-line strings. New test cases cover
  the new extraction algorithm.
- Rationale: Inline strings make the test intent obvious without a separate
  file lookup. The old fixtures have no value for the new API.
- Rejected: Reuse fixture files with new content — the new snapshot format is
  short enough to be inline.

## Technical context

### Files changed

| File | Change |
|---|---|
| `plugins/mill/scripts/millpy-claude-sub.py` | Remove marker logic; add `_wait_for_idle_stable`; replace Step 11 |
| `plugins/mill/scripts/_psmux_capture.py` | Full rewrite — new `extract_response(snapshot)` |
| `plugins/mill/unit_tests/test-psmux-capture.py` | Full rewrite — new test cases |
| `plugins/mill/unit_tests/test-claude-sub.py` | Update mock signatures; rewrite S6 (success-path) |
| `plugins/mill/unit_tests/fixtures/psmux-capture/*.txt` | Delete all nine files |

No changes to `_llm_claude.py`, `_psmux.py`, `_llm_common.py`, or any other file.

### Current flow in `millpy-claude-sub.py`

```
Step 1:  Read prompt from stdin
Step 2:  Generate session name + MILL_BEGIN_xxx / MILL_END_xxx markers
Step 3:  Append marker footer to prompt_body → full_prompt
Step 4:  Write full_prompt to .scratch/wrapper-<session>-prompt.txt
Steps 5–9: Create or reuse psmux session, boot/reuse checks
Step 10: Submit via bracketed paste (with markers in prompt)
Step 11: Poll capture_pane in loop until MILL_BEGIN→MILL_END found or timeout
```

### New flow

```
Step 1:  Read prompt from stdin
Step 2:  Generate session name (no markers)
Step 3:  (removed)
Step 4:  Write prompt_body directly to .scratch/wrapper-<session>-prompt.txt
Steps 5–9: unchanged
Step 10: Submit via bracketed paste (no markers in prompt)
Step 11: Call _wait_for_idle_stable(); on timeout raise RuntimeError
         Capture snapshot_b; call _psmux_capture.extract_response(snapshot_b)
```

### `_wait_for_idle_prompt` vs `_wait_for_idle_stable`

`_wait_for_idle_prompt` (existing) — returns on the FIRST `❯` sighting.
Used for: (a) reuse-check before submission, (b) boot-wait after `claude` TUI
launch. Both are single-sighting scenarios — once `❯` appears, the session is
available. Uses `capture_pane(session_name, alternate=True)`.

`_wait_for_idle_stable` (new) — requires `❯` in TWO consecutive captures
separated by `POLL_INTERVAL_S`. Uses `capture_pane(session_name, alternate=True)`
for each poll. Used only for post-response detection. Timeout constant:
`RESPONSE_POLL_TIMEOUT_S[args.mode]` (same dict, same per-mode values as the
current marker-polling loop).

The snapshot_b capture in the new Step 11 also uses `capture_pane(session_name,
alternate=True)`, consistent with every other idle/response detection call in
the file.

### `_psmux_capture.py` — new module structure

```python
class MarkerNotFoundError(Exception):
    """Raised when the expected idle char or bullet prefix is absent."""

def extract_response(snapshot: str) -> str:
    """Extract Claude's most recent response from a post-response pane snapshot.

    Finds the last line starting with the idle char '❯' (the new input
    prompt), then works backwards to find the first line starting with
    '● ' (Claude's response indicator). Returns lines from that bullet line
    to just before the idle line, with '● ' stripped from the first line.

    Raises MarkerNotFoundError if either signal is absent.
    """
```

The `idle_char` and `bullet_prefix` values are not parameterised (no kwargs) —
they are implementation constants, not configuration. If a future CC version
changes `❯`, that is a Phase 2 concern.

### Imports removed from `millpy-claude-sub.py`

- `secrets` — was used only for `token_hex(4)` in marker generation
- No other import changes

### `test-claude-sub.py` update scope — definitive list

Tests that never reach Step 10/11 (exit before submission) need no changes:
- **S2** (existing-busy raise) — exits at reuse idle check; no `extract_response` mock
- **S3** (reused session not killed on failure) — same early exit
- **S5** (keep-alive true, error) — boot-wait fails; exits before Step 10
- **S8** (list_sessions raises) — exits immediately

Tests that reach Step 10/11 on the success path need both: (a) a
`_wait_for_idle_stable` mock added and (b) the `extract_response` mock updated
to a 1-arg lambda:
- **S1** (existing-idle short-circuit) — reuse path reaches Step 10/11
- **S4** (keep-alive true, success) — new session; reaches Step 10/11
- **S7** (named-but-missing creates) — new session; reaches Step 10/11
- **S9** (reuse_idle_timeout_s plumbing) — reuse path reaches Step 10/11

**S6** (regression guard, no flags) — full rewrite: remove marker-based
`capture_pane` mock; add `_wait_for_idle_stable` returning True; `capture_pane`
returns a valid snapshot (has `❯` and `● ` lines); `extract_response` returns "ok".

## Constraints

- Python output must be ASCII-only (`print`/`_log`). No `→`, `—`, or Unicode
  non-ASCII on stdout/stderr (Windows cp1252 crashes).
- `_psmux_capture.py` must remain importable by `millpy-claude-sub.py` with the
  same module name and `MarkerNotFoundError` symbol.
- No changes outside the five listed files.

## Testing

### `test-psmux-capture.py` — new test cases (inline strings)

Scenarios to cover:
- **Basic response**: snapshot with `❯`, then `● First line\nSecond line\n❯` —
  verify extraction returns `First line\nSecond line`
- **Multi-line response**: 10+ continuation lines — verify all lines present
- **Bullet-prefix strip**: first line has `●  extra space` form — strip only
  `● ` (2 chars), leave the rest intact
- **Session history**: snapshot with two prior `❯…●…❯` blocks followed by the
  current response — verify only the latest response is returned
- **No bullet prefix**: snapshot has `❯` but no `● ` line — verify
  `MarkerNotFoundError`
- **No idle char**: snapshot has `● Response` but no `❯` — verify
  `MarkerNotFoundError`
- **Whitespace variants**: lines with leading spaces before `❯` or `● ` —
  `.strip()` should still match

### `test-claude-sub.py` — updated/new scenarios

- **S2, S3, S5, S8**: no changes (exit before Step 11; no `extract_response` mock)
- **S1, S4, S7, S9**: update `extract_response` mock to 1-arg lambda; add
  `_wait_for_idle_stable` mock returning True
- **S6**: full rewrite — `_wait_for_idle_stable` returns True; `capture_pane`
  returns valid snapshot with `❯` and `● ` lines; `extract_response` returns "ok"
- **New S10**: `_wait_for_idle_stable` returns False → RuntimeError → exit code 1
- **New S11**: `_wait_for_idle_stable` returns True, `extract_response` raises
  `MarkerNotFoundError` → exit code 1

TDD candidates: `extract_response` (pure function, no mocking needed),
`_wait_for_idle_stable` (mock `_psmux.capture_pane` with a sequence of return
values). Key `_wait_for_idle_stable` scenarios:
- (a) First poll has `❯`, second poll has `❯` → returns True
- (b) First poll has `❯`, second poll has no `❯`, third and fourth polls both
  have `❯` → returns True (transient recovery)
- (c) `❯` never appears in any poll → returns False on timeout

## Q&A log

- **Q:** Where to capture snapshot A (pre-submit baseline)? **A:** No snapshot A — Q2 makes it unnecessary. The last-`●`-before-`❯` algorithm in snapshot B is sufficient without a baseline.
- **Q:** How to extract the response from snapshot B? **A:** Find the last `❯` line, work backwards to the first `● ` line, extract between them, strip `● ` from first line. Does not require snapshot A.
- **Q:** How to detect response completion without markers? **A:** Add `_wait_for_idle_stable` — requires `❯` in two consecutive captures 1s apart. Existing `_wait_for_idle_prompt` (single sighting) unchanged.
- **Q:** Fate of `_psmux_capture.py`? **A:** Rewrite in place. Keep `extract_response` name and `MarkerNotFoundError` name; change signature to single `snapshot` arg.
- **Q:** Phase 2 scope (auto-resume, configurable idle char)? **A:** Out of scope.
