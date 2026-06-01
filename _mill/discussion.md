# Discussion: Smoke-test the psmux implementer end-to-end

```yaml
task: Smoke-test the psmux implementer end-to-end
slug: smoke-test-psmux
status: discussing
parent: main
```

## Problem

The previous task (`replace-claude-p-with-psmux`, commit baff371f) rewrote the LLM dispatch layer so that `millpy-claude-sub.py` routes prompts through an interactive Claude TUI session via psmux instead of `claude -p`. The code and its tests were written based on empirical observations of the psmux/Claude TUI behavior. Before flipping `via_psmux: true` in `mill-config.yaml` (enabling this path for all mill operations), the implementation must be validated end-to-end.

During exploration, one confirmed bug was found: `_wait_for_idle_prompt` and `_wait_for_idle_stable` both check for `"for shortcuts"` in the alternate-screen capture output. On this machine, psmux delivers the status-bar text with non-ASCII space characters between words. The check uses an ASCII space, so `"for shortcuts"` never matches even when the TUI is idle. This causes every invocation to time out and fail. The debug capture shows `"?forshortcuts??foragents"` where `?` represents non-ASCII chars (decoded with `errors="replace"`) and no ASCII spaces appear between words.

## Scope

**In:**
- Fix `_wait_for_idle_prompt` and `_wait_for_idle_stable` in `millpy-claude-sub.py` (confirmed broken)
- Investigate `extract_response` in `_psmux_capture.py` for the same space-related issue (`"● "` bullet detection) and fix if needed
- Fix silent-failure bug in `test-claude-psmux.py` (exceptions caught without printing — every failure looks identical)
- Extend `test-claude-sub.py` with test scenarios for the no-ASCII-space capture path
- Run the full integration test (`test-claude-psmux.py`) against live psmux/Claude and make all 4 tests pass
- Flip `via_psmux: true` in `mill-config.yaml`

**Out:**
- Changes to `plugins/mill/templates/mill-config.yaml` — new hubs should default to `false` and opt in after local validation
- Changes to `_llm_claude.py` dispatch logic — confirmed correct by existing unit tests
- Changes to `test-llm-claude.py` — psmux argv tests already pass and are correct
- Any streaming / pipe-pane work (out of scope per doc/psmux-tui-behavior.md)

## Decisions

### Idle detection: check `"shortcuts"` not `"for shortcuts"`

- Decision: change `"for shortcuts" in capture` to `"shortcuts" in capture` in both `_wait_for_idle_prompt` and the Phase-2 loop of `_wait_for_idle_stable`.
- Rationale: `"shortcuts"` is the only invariant ASCII substring in the status-bar idle text regardless of how inter-word spaces are encoded. The word "shortcuts" does not appear in processing-screen text or response content. The existing processing-marker code already follows this pattern (`"esctointerrupt"` fallback was added for the same reason).
- Rejected: normalizing Unicode spaces with `re.sub(r'\s+', ' ', capture)` — works but adds regex overhead to every poll; the substring check is simpler and equally robust.

### extract_response bullet detection: defensive match

- Decision: change `bullet_prefix = "● "` to match on just `"●"` (without space), then strip the leading bullet and any following whitespace from the first line.
- Rationale: if psmux uses a non-ASCII space after `●` (as it does in the status bar), `startswith("● ")` would fail to find the response start. Using `startswith("●")` and then `.lstrip()` on the remainder handles both ASCII-space and non-ASCII-space variants without changing behavior on correct input.
- Rejected: leaving it unchanged and hoping it works — the status bar evidence shows non-ASCII spaces are real; the same issue is plausible for response-block punctuation.

### test-claude-psmux.py: surface exceptions

- Decision: in each test function's `except` block, print the exception type and message to stderr before returning 1. Do not re-raise (the test runner catches and reports per-test anyway).
- Rationale: currently every failure is reported as `[FAIL] test_X: test returned non-zero` with zero diagnostic detail. Adding `print(f"[{name}] {type(exc).__name__}: {exc}", file=sys.stderr)` makes failures self-describing.
- Rejected: restructuring tests to not catch at all — would require refactoring the main() runner; not worth it for a smoke-test harness.

### via_psmux flip: hub mill-config.yaml only

- Decision: set `via_psmux: true` in `mill-config.yaml` (hub root). Leave the plugin template at `false`.
- Rationale: psmux viability is machine-specific (requires psmux binary, a working shell path, and a valid Claude TUI). The hub config is the per-machine override; the template is the portable default.
- Rejected: flipping the template — would break setups without psmux.

## Technical context

**Key files:**
- `plugins/mill/scripts/millpy-claude-sub.py` — the psmux wrapper; contains `_wait_for_idle_prompt` and `_wait_for_idle_stable` (both need fixing)
- `plugins/mill/scripts/_psmux.py` — psmux subprocess driver; `capture_pane(alternate=True)` returns the TUI alt-screen
- `plugins/mill/scripts/_psmux_capture.py` — pure-function response extractor; `extract_response(snapshot)` searches for `❯` (idle prompt), `●` (response start), `✻` (completion marker), `─` (separator)
- `plugins/mill/unit_tests/test-claude-sub.py` — unit tests for `millpy-claude-sub.py`; has `_wait_for_idle_stable` scenario tests (a)-(e) using mock captures with `"? for shortcuts"` (ASCII spaces) — needs new scenarios with `"?forshortcuts"` (no ASCII spaces)
- `plugins/mill/unit_tests/test-psmux-capture.py` — pure-function tests for `extract_response`; should get a new test for `"● "` (non-breaking space after bullet)
- `plugins/mill/integration_tests/test-claude-psmux.py` — live integration test; 4 tests (bulk, tool-use, implementer, keep-alive-reuse); currently all fail silently
- `mill-config.yaml` (hub root) — contains `llm.claude.psmux.via_psmux: false` and `llm.claude.psmux.shell_path: "C:/Code/tools/powershell7/pwsh.exe"`

**Non-ASCII-space root cause:** psmux's alternate-screen capture on Windows emits inter-word spaces in the status bar as non-ASCII Unicode spaces (e.g., U+00A0 or similar). When the subprocess stdout is read with `encoding="utf-8", errors="replace"`, those chars become `�` (U+FFFD, printed as `?`). Python string literals like `"for shortcuts"` contain U+0020 (ASCII space), so the `in` check fails. The ASCII text itself (`forshortcuts`, `foragents`, letter-only words) is preserved correctly.

**Existing unit tests (all passing as of exploration):** `test-claude-sub.py` (13 PASS), `test-psmux-capture.py` (10 OK). Both handle their own sys.path setup so `PYTHONPATH=` (empty) is the correct verify form.

**Integration test run form:** `PYTHONPATH= "$MILL_PYTHON" plugins/mill/integration_tests/test-claude-psmux.py` — the test sets its own sys.path. Requires psmux and claude binaries; both confirmed present. Expected wall-clock: ~5-10 min for all 4 modes.

**`❯` and `✻` are unaffected:** the debug ASCII-encode showed `??Try` before the suggestion text — `??` = `❯` + a non-ASCII space. `❯` itself decodes as U+276F (correct) since psmux outputs valid UTF-8 for that character; the space after is non-ASCII but irrelevant to the `startswith("❯")` check. Same reasoning applies to `✻` (U+273B) and `─` (U+2500).

## Constraints

- All verify commands must start with `PYTHONPATH= ` (empty, not set to scripts dir) — the test files set sys.path themselves.
- No changes outside `plugins/mill/scripts/`, `plugins/mill/unit_tests/`, `plugins/mill/integration_tests/`, and `mill-config.yaml`.
- `_subprocess_util.run` encoding (`utf-8`, `errors="replace"`) must not be changed — it is correct; the issue is in the marker strings, not the decoder.

## Testing

**Unit (automated, run on every change):**
- `test-claude-sub.py`: add scenarios (f) and (g) — mock capture returns `"forshortcuts"` (no ASCII space); verify `_wait_for_idle_prompt` returns `True` and `_wait_for_idle_stable` returns `True`. Add scenario (h) — mock capture returns `"esc to interrupt"` then `"shortcuts"` to verify Phase-1 → Phase-2 transition with new marker. Existing scenarios (a)-(e) must still pass (they use ASCII-space captures, which contain `"shortcuts"` as a substring).
- `test-psmux-capture.py`: add Test 11 — snapshot with `"● First line"` (non-breaking space after bullet); verify `extract_response` returns `"First line"`. Add Test 12 — snapshot with `"● First line"` (ASCII space, regression guard); verify it still works.

**Integration (live, final gate):**
- `test-claude-psmux.py` — all 4 tests must pass: `test_bulk`, `test_tool_use`, `test_implementer`, `test_keep_alive_reuse`. These run real Claude through real psmux. Timeouts are 400s (bulk/reuse) and 1900s (implementer).

**Config validation:**
- After flipping `via_psmux: true`, run `test_bulk` again in isolation (or the full suite) to confirm psmux still works end-to-end. Note: `test-claude-psmux.py` invokes `millpy-claude-sub.py` directly; dispatch routing through `_llm_claude._invoke` is separately covered by the existing `test-llm-claude.py` unit tests.

## Q&A log

- **Q:** What is the scope — fix the existing integration test, write a new harness, or run a live mill task as validation? **A:** Fix bugs and make the existing test-claude-psmux.py pass. That is the gate.
- **Q:** The `"?forshortcuts"` detection issue — encoding bug or status-bar text change? **A:** Encoding: non-ASCII spaces in psmux alt-screen capture. Confirmed by inspecting the debug output — ASCII letters are preserved, spaces adjacent to non-ASCII chars are not.
- **Q:** Should the integration test silently swallowing exceptions be fixed? **A:** Yes, fix as part of this task.
- **Q:** Flip via_psmux in hub config or template? **A:** Hub config only (`mill-config.yaml` at repo root). Template stays false.
