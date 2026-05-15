# Review: Wrap claude -p via psmux to use subscription instead of API credits

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: C:\Code\millhouse\wts\claude-p-wrapper\_mill\discussion.md
date: 2026-05-15
```

## Findings

### [GAP] Response-poll timeout not specified

**Section:** `## Constraints` / `## Technical context`
**Issue:** The 20-second boot-readiness timeout and the 30-second per-psmux-command timeout are both named, but no total timeout is stated for the capture-pane polling loop that waits for the sentinel + idle-prompt condition. An implementer-mode task (multi-file editing) can easily run for several minutes; without a bound, the loop is unlimited.
**Fix:** State the maximum wall-clock time the response-ready polling loop will wait before raising a timeout error, as a named constant alongside the existing boot-timeout and psmux-command-timeout knobs.

---

### [GAP] Parser start-of-response boundary undefined

**Section:** `## Scope` (`_psmux_capture.py`) / `## Testing`
**Issue:** The two-argument signature `extract_response(capture_text, sentinel)` has no mechanism for identifying where Claude's response begins vs. the prompt echo that the TUI renders before the response. Fixture 1 (`clean.txt`) implies the echo is stripped ("Expected output: just the response line"), but the heuristic or marker for the start boundary is not defined in the discussion.
**Fix:** Explicitly state the start-of-response delimiter (e.g., the first `●`-prefixed line, the line immediately after the last prompt-echo line, or a TUI status indicator), or add the original prompt text as a third argument to `extract_response` for stripping.

---

### [GAP] System-prompt delivery mechanism unresolved for large content

**Section:** `## Decisions` ("--system-prompt accepts a FILE PATH")
**Issue:** The wrapper reads the file content and passes it to `claude --system-prompt` (which takes a string), but the claude launch command is sent via `send-keys`. For system prompts that are kilobytes, this hits both the Windows CLI length cap (~8 KB) and the send-keys character-dropping issue that motivated paste-buffer for the prompt body—the same problem the file-path decision was supposed to solve at the caller boundary.
**Fix:** Define how the system-prompt content is delivered to the claude launch command when it exceeds a short string: e.g., prepend it to the prompt body (delivered via paste-buffer), use a temp file if the `claude` CLI accepts `@file` syntax, or explicitly cap the supported system-prompt size.

---

## Verdict

GAPS_FOUND  
Three plan-blocking gaps: response-poll timeout, parser start boundary, and system-prompt delivery for large content.