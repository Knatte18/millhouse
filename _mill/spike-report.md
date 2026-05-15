```yaml
task: Wrap claude -p via psmux to use subscription instead of API credits
slug: claude-p-wrapper
status: spike-complete
wrapper: millpy-claude-sub.py
integration_test: plugins/mill/integration_tests/test-claude-psmux.py
```

# Spike report -- claude-p-wrapper

## Premise

Mill uses `claude -p` (headless print mode) for every reviewer and implementer spawn, which bills against API credits rather than the Claude Max subscription. With three parallel mill-go sessions running, API credit consumption exceeds $200 per month despite the subscription already being paid.

Interactive `claude` sessions (without the `-p` flag) are covered by the subscription. The spike validates that automating an interactive `claude` session via `psmux` can serve as a drop-in text-in / text-out replacement for `claude -p`, enabling mill to route all programmatic calls through subscription billing instead.

## PoC findings (verified during mill-start)

- psmux 3.3.4 + pwsh 7.6.1 successfully automate interactive claude sessions
- `claude` command resolves to `~/.local/bin/claude.exe` (real exe, not npm shim)
- `paste-buffer` delivery via `load-buffer -b` round-trips prompts losslessly; `send-keys` dropped ~5 characters on test input
- `capture-pane -p` returns ANSI-stripped text ready for parser consumption
- `capture-pane -S -<N>` retrieves full scrollback; verified at 100 lines in a 30-row pane
- `--allowedTools` pre-grants tool permissions in interactive mode with zero permission prompts per tool call
- `--tools ""` runs cleanly with no permission prompts in bulk mode
- Windows PATH truncation in CC-Bash does NOT propagate into psmux panes; claude resolves correctly without workarounds

## Known limitations

- Whitespace fidelity is imperfect: the TUI occasionally compresses adjacent words (e.g. "PowerShellthreadsweaveasone"); observed in PoC; markdown-structured reviews tolerate it
- Boot overhead ~6-8 seconds per call; no session pooling in spike scope
- Startup auto-skill loading via CLAUDE.md adds a few seconds per call (startup checks run before first prompt)
- No rate-limit detection equivalent to `_llm_claude._scan_rate_limit`; non-zero exits surface as generic errors
- No stream-json or partial-message streaming; text-only response delivery
- No `--resume` support; every call spawns a fresh psmux session

## Recommended follow-up scope

1. Wire `millpy-claude-sub.py` into `_llm_claude.py` behind a config flag (e.g. `llm.claude.use_psmux_wrapper: true`)
2. Sweep `plugins/mill/templates/` to confirm the dual-marker protocol does not collide with any reviewer-template instructions (markers are envelope-only so collision is unlikely, but verify)
3. Reviewer-naming refactor (`sonnet` = with tools default, `sonnet_bulk` = without); discussed during mill-start as a separate task
4. Gemini-on-subscription equivalent if/when it becomes economically interesting (same psmux pattern, different LLM)

## Acceptance (operator)

- [ ] Run integration test: `python plugins/mill/integration_tests/test-claude-psmux.py`
- [ ] All three sub-tests pass (bulk, tool-use, implementer)
- [ ] Anthropic dashboard confirms these test calls show as subscription usage, NOT API credit usage. This is the load-bearing acceptance check.
- [ ] Largest scrollback observed against integration test prompts: ___ lines (record the value)
- [ ] Final go/no-go decision: GO / NO-GO (operator selects and writes follow-up task into Home.md if GO; revises discussion if NO-GO)
