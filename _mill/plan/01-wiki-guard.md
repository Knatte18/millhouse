# Batch: wiki-guard

```yaml
task: "plan validator and wiki-guard hook false positives"
batch: "wiki-guard"
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-guard.py
depends-on: []
```

## Batch Scope

Delivers the token-based wiki-guard decision logic as a testable stdlib-only module plus its PreToolUse hook CLI (issue 1161).
Batch 2 consumes the CLI script path when installing the hook.
No batch-local decisions differ from the overview; the detection algorithm, accepted-conservative behaviors, and deny-message text are fixed in the task's discussion.md under the wiki-guard decisions.

## Cards

### Card 1: wiki-guard detection module

- **Context:** none
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_wiki_guard.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create a stdlib-only module (imports limited to `json`, `re`, `shlex`, `os`, `sys`) exposing:
  - Module constant `DENY_REASON`: the exact ASCII string "Mill wiki files are daemon-owned (CLAUDE.md: Mill wiki -- never touched directly). Use the wiki._client API instead of raw shell commands on the wiki junction."
  - `command_touches_wiki(command: str) -> bool`, implemented in this order (authoritative; the numbered discussion steps are out of order):
    1. Strip heredoc bodies: for each heredoc start (`<<`, `<<-`, optionally-quoted tag), drop every following line up to and including the terminator line (tag alone on a line, leading tabs allowed for `<<-`). Keep the text before the heredoc operator on the start line. Text after an unterminated heredoc start is dropped to end of input.
    2. Extract command substitutions: scan the remaining text for `$(` ... balanced `)` spans and backtick ... backtick spans; replace each span with a single placeholder word and recurse `command_touches_wiki` on each extracted inner string. If any recursion returns True the whole result is True. This runs regardless of the echo/printf argument skip in step 5, so an echo whose argument is a substitution that reads the wiki junction is True while a plain-text echo argument is not.
    3. Tokenize the remainder with `shlex.shlex(text, posix=True, punctuation_chars=True)` with `whitespace_split=True`, then split the token stream into simple commands at the tokens `;`, `&&`, `||`, `|`, `&`, and newline-derived separators (feed newlines through as `;` by replacing them before tokenizing). On `ValueError` (unbalanced quotes) fail closed: return `re.search(r"\.wiki\b", command) is not None` on the ORIGINAL command text.
    4. Per simple command, find the command word: skip leading `VAR=value` assignments and the words `sudo`, `env`, `command`; take the basename of the next word.
    5. If the command word is `bash`, `sh`, `zsh`, or `eval`: for `bash|sh|zsh` with a `-c` flag, recurse on the argument after `-c`; for `eval`, recurse on the space-joined remaining arguments. Any True result makes the whole result True. Every other argument of these commands (a script path such as one passed to bash, flags, the arguments after the `-c` string) is still tested by step 8's per-argument rule.
    6. If the command word is `echo` or `printf`: test no argument (all are text).
    7. If the command word is `grep`, `egrep`, `fgrep`, `rg`, `ag`, or `awk`: skip exactly one pattern/program argument and test every other argument. The pattern is the value following `-e`, `--regexp`, `-f`, or `--file` when one of those flags is present (then there is no positional pattern), else the first non-flag argument. An argument starting with `-` is a flag; `--` ends flag parsing. This is a heuristic, not a full option parser.
    8. Otherwise test every argument.
    9. Testing an argument: a token containing whitespace is prose and is not a path (skip it, except that substitutions inside it were already handled in step 2). Otherwise split the token once on `=` and test both the whole token and the right-hand side; a token is a wiki path when, split on `/` and `\`, some component is exactly `.wiki`. So `.wiki`, `.wiki/x`, `../.wiki/x`, `foo/.wiki/x`, `--flag=.wiki/x` are wiki paths while `hub.wiki`, `path/hub.wiki`, and `x.wikipedia` are not.
  - `deny_json(command: str) -> str`: return the empty string when `command_touches_wiki` is False, else the single-line JSON string `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": DENY_REASON}}` built with `json.dumps` (ASCII-only).
  - `hook_main(stdin_text: str) -> str`: parse `stdin_text` as JSON, read `tool_input.command` (string), return `deny_json(command)`. On any parse error, missing key, or non-string command return the empty string (never raise). This is the entry the CLI script calls.
  Accepted-conservative behaviors that must hold and are pinned by the batch's tests: a whitespace-free quoted wiki path argument is denied, and a substitution inside single quotes is still recursed into.
  Example commands (in a fence so they are quoted material, not dependencies):
  ```
  cat .wiki/Home.md            -> True
  git -C .wiki status          -> True
  grep foo .wiki/Home.md       -> True
  echo "path/hub.wiki"         -> False
  grep -rn .wiki plugins       -> False
  ```
- **Commit:** `feat(wiki-guard): token-based wiki junction guard module`

### Card 2: wiki-guard hook CLI

- **Context:**
  - `plugins/mill/scripts/_wiki_guard.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-wiki-guard.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create a thin executable CLI following the repo's other millpy CLI shape (module docstring, `from __future__ import annotations`, `main() -> int`, `if __name__ == "__main__": sys.exit(main())`). `main` reads all of standard input, calls `hook_main` from `_wiki_guard`, prints the returned string with `print(result)` only when it is non-empty, and always returns 0 (a hook error must never crash the tool call). Import only `sys` and `_wiki_guard`; ASCII-only output. Add a one-line comment that this script is a Claude Code PreToolUse hook installed by mill-setup and is not a user-invocable skill.
- **Commit:** `feat(wiki-guard): PreToolUse hook CLI`

### Card 3: wiki-guard tests

- **Context:**
  - `plugins/mill/scripts/_wiki_guard.py`
  - `plugins/mill/scripts/millpy-wiki-guard.py`
  - `plugins/mill/unit_tests/test-plan-validate-indent-drift-line.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-guard.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create a standalone unit test file in the style of `test-plan-validate-indent-drift-line.py` (sys.path insert of the scripts directory relative to `HUB`, plain `def test_*` functions using assertions, a `main() -> int` runner that prints failures to stderr and returns 1 on any failure, `sys.exit(main())`). Import `_wiki_guard`. Cover:
  - True: `grep foo` with the junction path argument, `grep -r foo` with the junction as directory, `cat`, `git -C`, `cd ... && ls`, `ls ../` with the junction, `bash -c` wrapping a junction read, `echo $(cat <junction path>)`, and an unbalanced-quote command containing the junction name (fail-closed fallback).
  - False: grep whose pattern is the bare junction name, the quoted junction name, and the backslash-escaped junction name (each with a plain directory as path), `grep -e` form, `echo` of the bare junction name, `echo "path/hub.wiki"`, `gh issue create --body "error at /x/hub.wiki"`, `gh issue create --body` with prose that mentions the junction path with spaces around it, a heredoc whose body contains the junction name (`cat > .scratch/x.md <<'EOF'` form), and `grep foo file.txt`.
  - Accepted-conservative pinned as True: `cp x` with a quoted whitespace-free junction path destination, and a single-quoted substitution reading the junction passed to a non-echo command.
  - CLI-level via `hook_main`: JSON with a junction-touching command yields JSON that parses with `permissionDecision == "deny"` and `permissionDecisionReason == DENY_REASON`; a benign command yields the empty string; malformed JSON, a missing `tool_input`, and a non-string command each yield the empty string. Also run the script once through `subprocess.run([sys.executable, <script path>], input=..., capture_output=True, text=True)` to confirm exit code 0 and matching stdout for one deny and one benign payload.
  Build each junction-bearing command string in the test with string concatenation or a module constant (for example `J = "." + "wiki"`) so the test source itself stays readable; any form is acceptable.
- **Commit:** `test(wiki-guard): cover token-based guard and hook CLI`

## Batch Tests

`verify:` runs only `test-wiki-guard.py` through `run-all.py --only`, the sole test file this batch creates; nothing else imports the new modules yet.
