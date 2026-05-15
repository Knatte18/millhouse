Now I have enough source context to write the review.

# Review: Wrap claude -p via psmux to use subscription instead of API credits

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: C:\Code\millhouse\wts\claude-p-wrapper\_mill\discussion.md
date: 2026-05-15
```

## Findings

### [GAP] Windows PATH: `claude.cmd` not reachable inside psmux pane
**Section:** Technical context / psmux command vocabulary
**Issue:** `_llm_claude.py:39-57` documents that `%LOCALAPPDATA%\Microsoft\WindowsApps` (where `claude.cmd` lives) is stripped from the PATH that Python inherits in CC subprocess environments, and solves it with `cmd /c claude`. The psmux wrapper inherits the same truncated PATH; psmux then starts `pwsh -NoLogo -NoProfile` with that inherited environment, so `send-keys "claude ..." Enter` will fail to find `claude.cmd` inside the pane. The discussion references `_build_argv` as authoritative for flag layout but does not extend the same PATH analysis to the pane-level invocation. The PoC verification ("responded cleanly") doesn't state whether it was run from within CC's Bash tool or from a standalone terminal, so it may not have reproduced the truncated-PATH scenario.
**Fix:** Specify how `claude` is launched inside the pane on Windows — either via `cmd /c claude` as the sent command, via explicit `claude.cmd` path, or confirm with evidence that the PoC reproduced the CC subprocess PATH environment and the issue does not manifest.

### [NOTE] `set-option` history-limit syntax unverified
**Section:** Technical context, psmux command vocabulary table
**Issue:** The table row for `set-option -t <name> -g history-limit 50000` already flags "syntax to be verified during implementation; psmux options page may differ from tmux." No fallback strategy is stated if the command is unsupported.
**Fix:** Add a sentence stating that if `set-option` is unsupported the implementation should fall back to accepting psmux's default scrollback, and document the default observed during PoC.

### [NOTE] `--allowedTools` pre-grant semantics not verified for implementer mode
**Section:** Q&A log (allowedTools question)
**Issue:** The Q&A confirms `--tools ""` (no tools, bulk) launched in psmux "responded cleanly with no permission prompts," which is trivially true — no tools means no prompts. For implementer mode (`--allowedTools Read,Edit,Write,Bash,Grep,Glob,Skill`), it is not stated whether interactive Claude treats `--allowedTools` as pre-granting those tools (suppressing per-operation prompts) or still prompts before each Bash/Write/Edit use. A stalled permission prompt inside the psmux pane would silently block the wrapper until the timeout fires.
**Fix:** State explicitly whether `--allowedTools` in interactive mode suppresses per-operation prompts, and cite the verification (or note it as a first-step PoC check in the integration test).

## Verdict

GAPS_FOUND
One concrete, source-grounded PATH issue must be resolved before the plan can specify the pane-level `claude` invocation on Windows.