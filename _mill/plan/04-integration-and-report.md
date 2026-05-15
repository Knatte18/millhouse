# Batch: integration-and-report

```yaml
task: Wrap claude -p via psmux to use subscription instead of API credits
batch: integration-and-report
number: 4
cards: 2
verify: python -m py_compile plugins/mill/integration_tests/test-claude-psmux.py
depends-on: [3]
```

## Batch Scope

This batch delivers the manually-invoked integration
test (`integration_tests/test-claude-psmux.py`) that exercises the
wrapper end-to-end against real psmux + claude, plus the spike's
go/no-go report (`_mill/spike-report.md`) that the operator fills in
after running the integration test and confirming subscription billing
in the Anthropic dashboard. Neither artifact runs in CI nor in
`unit_tests/run-all.py` -- both require a live `claude` session and an
operator with dashboard access.

**Batch-local decisions:**
- The integration test skips with a clear stderr message and exits 0
  if any of `psmux`, `claude`, `pwsh` is missing from PATH. Skip is
  not failure; absence on a CI runner is expected.
- The spike report is a markdown skeleton with operator-fillable
  checkboxes. The implementer cannot tick the boxes -- the report
  records what the implementer KNOWS from discussion.md plus what the
  operator must verify.


## Cards

### Card 10: integration test for wrapper end-to-end

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_psmux.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/integration_tests/smoke-llm-claude.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-claude-psmux.py`
- **Deletes:** none
- **Requirements:** Module docstring matching `smoke-llm-claude.py`'s
  shape: one-line purpose ("End-to-end integration test for
  millpy-claude-sub.py against real psmux + claude. Local-dev only.").
  Constants `HUB`, `SCRIPTS`, `SCRATCH` resolved via
  `Path(__file__).resolve().parent.parent.parent.parent` per the
  existing pattern. `sys.path.insert(0, str(SCRIPTS))`. Imports:
  `import shutil`, `import subprocess`, `import json`, `import sys`,
  `import _psmux`. SKIP guards (call before any test runs): if
  `shutil.which("psmux")` is None, print `[skip] psmux not on PATH` to
  stderr, return 0. Same for `claude` and `pwsh`. Three test functions:
  - `test_bulk()`: spawn
    `subprocess.run([sys.executable, str(SCRIPTS / "millpy-claude-sub.py"),
    "--mode", "bulk", "--model", "claude-sonnet-4-6"], input="Reply with
    the single word PONG and nothing else.", capture_output=True,
    text=True, timeout=400)`. Assert `result.returncode == 0`. Assert
    `"PONG" in result.stdout`. Assert `"MILL_BEGIN_" not in result.stdout
    and "MILL_END_" not in result.stdout`. Parse the LAST non-empty line
    of `result.stderr` as JSON; assert `"session_id"`, `"duration_s"`,
    `"mode"` keys exist; assert `parsed["mode"] == "bulk"`.
  - `test_tool_use()`: same pattern with `--mode tool-use` and prompt
    `"List the names of the files in the current directory using the
    Glob tool, then briefly summarise."`. Assert returncode 0,
    response non-empty, response mentions at least one file present in
    `os.listdir(HUB)` (e.g. `"plugins" in result.stdout`). JSON envelope
    asserts as before with `mode == "tool-use"`. Timeout 700s.
  - `test_implementer()`: same pattern with `--mode implementer` and
    prompt `"Use the Bash tool to run exactly: echo
    __INTEGRATION_OK__"`. Assert returncode 0, `"__INTEGRATION_OK__"
    in result.stdout`. JSON envelope asserts with `mode == "implementer"`.
    Timeout 1900s. **This is also the regression guard for
    `--allowedTools` pre-grant semantics** -- a future Claude CLI
    version that re-introduces per-Bash permission prompts will fail
    this test by timing out.
  After EACH test, also assert (cleanup verification): `_psmux.list_sessions()`
  contains no session whose name starts with `mill-`; no
  `wrapper-*-prompt.txt` files remain in `SCRATCH` (use
  `glob.glob` or `Path.glob`).
  `def main() -> int` runner: invoke each test function, count
  failures, print `[OK] <name>` / `[FAIL] <name>: <exception>` to
  stderr, return 0 on all-pass else 1. `if __name__ == "__main__":
  sys.exit(main())`. ASCII only.
- **Commit:** `test(mill): add claude-psmux integration test`

### Card 11: spike go/no-go report

- **Context:**
  - `_mill/discussion.md`
- **Edits:** none
- **Creates:**
  - `_mill/spike-report.md`
- **Deletes:** none
- **Requirements:** Markdown report. Top-of-file fenced ```yaml metadata
  block (per `mill:markdown` skill convention) with keys `task`, `slug`,
  `status: spike-complete`, `wrapper`, `integration_test`. After the
  metadata block, sections in order:
  - `# Spike report -- claude-p-wrapper`
  - `## Premise` -- two short paragraphs: the billing motivation
    (subscription not API), the operator-confirmed fact that
    interactive `claude` draws against subscription, and the goal of a
    text-in / text-out wrapper that drops in for `claude -p`.
  - `## PoC findings (verified during mill-start)` -- bulleted list
    capturing the verifications recorded in `_mill/discussion.md`'s Q&A
    log: psmux 3.3.4 + pwsh 7.6.1 working; `claude` resolves to
    `~/.local/bin/claude.exe` (real exe, not npm shim); `paste-buffer`
    delivers prompts losslessly where `send-keys` dropped 5 chars on
    the same input; `capture-pane -p` returns ANSI-stripped text;
    `capture-pane -S -<N>` retrieves full scrollback (verified at 100
    lines in 30-row pane); `--allowedTools` pre-grants in interactive
    mode with zero permission prompts; `--tools ""` runs cleanly with
    no permission prompts; CC-Bash's WindowsApps PATH truncation does
    NOT propagate into psmux panes.
  - `## Known limitations` -- bulleted list:
    (a) whitespace fidelity is imperfect (TUI compresses adjacent
    words occasionally; observed in PoC; markdown-structured reviews
    tolerate it); (b) ~6-8s boot per call (no session pooling in spike
    scope); (c) startup auto-skill loading via CLAUDE.md adds a few
    seconds per call; (d) no rate-limit detection equivalent to
    `_llm_claude._scan_rate_limit`; (e) no stream-json or
    partial-message streaming; (f) no `--resume` support.
  - `## Recommended follow-up scope` -- numbered list:
    (1) wire `millpy-claude-sub.py` into `_llm_claude.py` behind a
    config flag (e.g. `llm.claude.use_psmux_wrapper: true`);
    (2) sweep `plugins/mill/templates/` to confirm the dual-marker
    protocol does not collide with any reviewer-template instructions
    (markers are envelope-only so collision is unlikely, but verify);
    (3) reviewer-naming refactor (`sonnet` = with tools default,
    `sonnet_bulk` = without) discussed during mill-start as a separate
    task; (4) Gemini-on-subscription equivalent if/when it becomes
    economically interesting (same psmux pattern, different LLM).
  - `## Acceptance (operator)` -- markdown checkbox list (with
    `- [ ]` syntax; do NOT pre-tick):
    - `[ ] Run integration test: ...command per
      plugins/mill/integration_tests/test-claude-psmux.py module
      docstring...`
    - `[ ] All three sub-tests pass (bulk, tool-use, implementer)`
    - `[ ] Anthropic dashboard confirms these test calls show as
      subscription usage, NOT API credit usage. This is the
      load-bearing acceptance check.`
    - `[ ] Largest scrollback observed against integration test
      prompts: ___ lines (record the value)`
    - `[ ] Final go/no-go decision: GO / NO-GO (operator selects and
      writes follow-up task into Home.md if GO; revises discussion
      if NO-GO)`
  All ASCII in headings and prose (markdown content). UTF-8 encoded.
  No HTML. The report is self-contained -- a reader who has not seen
  the discussion file should understand the spike outcome from this
  report alone (cross-references to discussion.md are fine but not
  required for comprehension).
- **Commit:** `docs(mill): write claude-p-wrapper spike report`

## Batch Tests

`verify` for this batch is `python -m py_compile
plugins/mill/integration_tests/test-claude-psmux.py` -- a syntax check
only, since the integration test itself requires a live `claude`
session and an operator with Anthropic dashboard access. The spike
report is a markdown document with no runnable surface; its content is
not test-verified in CI. The `## Acceptance (operator)` checklist in
the report is the gate that converts the spike to a GO/NO-GO decision.
