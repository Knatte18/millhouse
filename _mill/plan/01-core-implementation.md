# Batch: Core implementation

```yaml
task: Replace psmux marker protocol with idle-prompt detection
batch: Core implementation
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch delivers the two production-code changes: a full rewrite of `_psmux_capture.py` with a new single-argument `extract_response(snapshot)` API, and targeted edits to `millpy-claude-sub.py` that remove all marker-generation code, add `_wait_for_idle_stable`, and replace the old Step 11 marker-polling loop with idle-prompt stability detection. Card 1 (the module rewrite) must be committed before Card 2 (the caller update), but both are implemented in this batch. The external interface this batch exposes — `extract_response(snapshot: str) -> str` and `_wait_for_idle_stable(session_name, timeout_s)` — is consumed by Batch 2 tests.

Batch-local decisions: `_wait_for_idle_stable` uses the same `POLL_INTERVAL_S` and `capture_pane(session_name, alternate=True)` call pattern as the existing `_wait_for_idle_prompt`. The `snapshot_b` capture in the new Step 11 is a direct `_psmux.capture_pane(session_name, alternate=True)` call after `_wait_for_idle_stable` returns True.

## Cards

### Card 1: Rewrite `_psmux_capture.py`

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Edits:**
  - `plugins/mill/scripts/_psmux_capture.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the entire content of `_psmux_capture.py` with a module containing exactly two public symbols — `MarkerNotFoundError` and `extract_response` — per the following spec:

  1. Keep `class MarkerNotFoundError(Exception)` with its name unchanged.
  2. Replace the old three-argument `extract_response(capture_text, begin_marker, end_marker)` with a one-argument `extract_response(snapshot: str) -> str`.
  3. Algorithm inside `extract_response`:
     - Split `snapshot` on `"\n"`.
     - Find the index of the **last** line whose `.strip()` starts with `"❯"` — call it `idle_idx`. If no such line exists, raise `MarkerNotFoundError("idle char not found in snapshot")`.
     - Working backwards from `idle_idx - 1` to 0, find the first line whose `.strip()` starts with `"● "` (bullet + space, 2 chars) — call it `bullet_idx`. If no such line exists, raise `MarkerNotFoundError("bullet prefix not found before idle char in snapshot")`.
     - Extract `lines[bullet_idx:idle_idx]`.
     - Strip `"● "` (exactly 2 chars) from `lines[bullet_idx].strip()` to get the first response line (i.e. `lines[bullet_idx].strip()[2:]`).
     - Reassemble: first response line followed by `lines[bullet_idx+1:idle_idx]` verbatim, joined with `"\n"`.
     - Return the result stripped of leading/trailing whitespace (`.strip()`).
  4. Remove the module-level docstring mentioning the dual-marker protocol. Write a short replacement docstring describing the new idle-prompt extraction approach.
  5. No other functions or classes. No `from __future__ import annotations` is required but may be kept for consistency.

- **Commit:** `refactor(psmux-capture): replace marker protocol with idle-prompt extraction`

### Card 2: Update `millpy-claude-sub.py`

- **Context:**
  - `plugins/mill/scripts/_psmux_capture.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the following targeted edits to `millpy-claude-sub.py`:

  1. **Remove `import secrets`** (line 17). No other imports change.

  2. **Simplify Step 2**: Keep `session_name = args.psmux_session if args.psmux_session is not None else f"mill-{uuid.uuid4().hex[:8]}"`. Delete the two lines that generate `begin_marker` and `end_marker`. Update the step comment to `# Step 2: Generate session name`.

  3. **Delete Step 3 entirely**: Remove the block that builds `footer` and `full_prompt`. Delete the comment `# Step 3: Append dual-marker footer to prompt`.

  4. **Update Step 4**: Change `prompt_path.write_text(full_prompt, ...)` to `prompt_path.write_text(prompt_body, ...)`.

  5. **Add `_wait_for_idle_stable` function** immediately after `_wait_for_idle_prompt`. Signature and body:
     ```python
     def _wait_for_idle_stable(session_name: str, timeout_s: float) -> bool:
         """Return True when idle char appears in two consecutive captures 1s apart."""
         idle_prompt = "❯"
         start = time.monotonic()
         prev_idle = False
         while True:
             try:
                 capture = _psmux.capture_pane(session_name, alternate=True)
                 curr_idle = any(
                     line.strip().startswith(idle_prompt)
                     for line in capture.splitlines()
                 )
             except _psmux.PsmuxError:
                 curr_idle = False
             if prev_idle and curr_idle:
                 return True
             prev_idle = curr_idle
             if time.monotonic() - start >= timeout_s:
                 return False
             time.sleep(POLL_INTERVAL_S)
     ```

  6. **Replace Step 11 entirely**: Delete the old `while True:` polling loop (which calls `extract_response(capture, begin_marker, end_marker)` and catches `MarkerNotFoundError`). Replace with:
     ```python
     # Step 11: Wait for stable idle prompt, then capture and extract response
     start = time.monotonic()
     if not _wait_for_idle_stable(session_name, RESPONSE_POLL_TIMEOUT_S[args.mode]):
         elapsed = time.monotonic() - start
         raise RuntimeError(
             f"response-poll timeout: mode={args.mode} elapsed={elapsed:.1f}s"
         )
     snapshot_b = _psmux.capture_pane(session_name, alternate=True)
     elapsed = time.monotonic() - start
     response = _psmux_capture.extract_response(snapshot_b)
     print(response, end="")
     print(
         json.dumps({
             "session_id": args.session_id,
             "duration_s": round(elapsed, 2),
             "mode": args.mode
         }),
         file=sys.stderr
     )
     # Success-path cleanup: kill session only if not keeping alive
     if not args.keep_alive:
         try:
             _psmux.kill_session(session_name)
         except _psmux.PsmuxError:
             pass
     else:
         print(
             f"[millpy-claude-sub] keepalive: leaving psmux session {session_name} running",
             file=sys.stderr
         )
     return 0
     ```
     Do NOT add a try/except around `_psmux_capture.extract_response(snapshot_b)` — let `MarkerNotFoundError` propagate to the outer `except Exception as exc:` handler.

  7. **`_wait_for_marker_in_pane` stays**: Do not delete this function. It is used in Step 7 for the CLAUDE_READY check.

- **Commit:** `refactor(claude-sub): replace marker-polling loop with idle-prompt stability detection`

## Batch Tests

`verify: null` — the existing `test-psmux-capture.py` and `test-claude-sub.py` still use the old three-argument API and will fail after Batch 1. Tests are fully updated in Batch 2. The batch can be manually spot-checked by importing `_psmux_capture` and confirming `extract_response` accepts a single positional argument.
