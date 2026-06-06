# Batch: psmux-dispatch

```yaml
task: "Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup"
batch: psmux-dispatch
number: 6
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-claude-sub.py test-llm-claude.py
depends-on: []
```

## Batch Scope

Fixes the psmux dispatch fallback (dormant under the default `agent`
dispatch, but real): the wrapper must not expand the prompt onto the
command line (#428, Windows ~32767-char limit), and the bulk
response-poll must honor the review-layer timeout instead of a hardcoded
300s cap (#433). Touches `millpy-claude-sub.py` and `_llm_claude.py`.

## Cards

### Card 18: Pass prompt via stdin, not the command line

- **Context:**
  - `plugins/mill/scripts/_psmux.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the Step 9 wrapper-script generation, stop expanding
  `$prompt` as a positional command-line argument to `claude`. Instead feed
  the prompt file via stdin redirection / pipe so the prompt never enters
  the process command line (e.g. `Get-Content -Raw '<prompt_file>' | & claude
  <args>`, or `& claude <args> < '<prompt_file>'`). Preserve multi-line
  prompt fidelity and the existing `claude` argument construction
  (`claude_cmd_parts` / `_ps_join`). Keep the launch-log line ASCII-only.
  The generated script must reference the prompt file path, not the prompt
  contents.
- **Commit:** `fix(claude-sub): feed prompt via stdin to avoid Windows cmd-line limit`

### Card 19: Honor review timeout for the bulk response poll

- **Context:**
  - `plugins/mill/scripts/_reviewer_single.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The bulk response-poll cap must not silently truncate a
  correctly-configured long review. Add an optional `--response-poll-timeout`
  (seconds) argument to `millpy-claude-sub.py`; when provided, use it as the
  response-poll timeout instead of the hardcoded
  `RESPONSE_POLL_TIMEOUT_S["bulk"] = 300` (the hardcoded values remain the
  fallback default when the flag is absent). In `_llm_claude.py`, where the
  psmux argv for the claude-sub wrapper is built (the `_build_psmux_argv`
  path), forward the caller-supplied review timeout (the same timeout
  `_reviewer_single.run` receives, e.g. `holistic_timeout`) as
  `--response-poll-timeout` so a 1800s holistic review is not capped at
  300s. ASCII-only.
- **Commit:** `fix(claude-sub): honor review timeout for bulk response poll`

### Card 20: Tests for psmux wrapper + timeout passthrough

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/test-claude-sub.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-claude-sub.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** `test-claude-sub.py`: assert the generated wrapper
  script feeds the prompt via stdin/pipe and does NOT contain the prompt
  expanded as a positional argument (the command line references the prompt
  file, not its contents); assert that when `--response-poll-timeout` is
  passed it overrides the bulk default, and that absent the flag the bulk
  default (300) still applies. `test-llm-claude.py`: assert
  `_build_psmux_argv` includes `--response-poll-timeout <timeout>` carrying
  the caller-supplied review timeout. Follow existing fixture style;
  generate the wrapper without launching `claude` or `psmux`.
- **Commit:** `test(claude-sub): cover stdin prompt feed and timeout passthrough`

## Batch Tests

`verify:` runs `test-claude-sub.py` (wrapper generation + timeout arg) and
`test-llm-claude.py` (argv building). No real `claude`/`psmux` process is
launched; only the generated script text and argv list are asserted.
