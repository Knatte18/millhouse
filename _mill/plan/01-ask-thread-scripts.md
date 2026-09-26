# Batch: ask-thread-scripts

```yaml
task: 'Unify ask-parent into ask-thread: ask any named session, default parent'
batch: "ask-thread-scripts"
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-ask-thread.py test-millpy-ask-thread.py
depends-on: []
```

## Rename mechanic

For each `Moves:` pair the implementer MUST:

1. Run `git mv <old> <new>` FIRST, before making any other change to the moved file.
2. Make ONLY surgical edits -- touch only the lines that must change after the move (module docstring, imports, identifier retargeting).
3. Use a full-file `Creates:` entry only for genuinely new files that have no predecessor.
4. Never write the relocated file from scratch and delete the original -- that breaks git rename history and inflates review diffs.

## Batch Scope

Renames the escalation helper module, its CLI and both unit tests from `ask-parent` to `ask-thread`, then extends them with the message-first reply protocol (per-batch `ask_id`, `reply_to`), direct (open-question) mode, a `target` override, and the `resolve` entry point.
Batch 2 consumes the CLI surface defined here: `prepare` (automatic: `--site/--reason/--actions [--reply-to]`; direct: `--questions-file [--to] [--reply-to]`), `consume --ask-id <id> (--actions <csv> | --open)`, and `resolve [--to <name>]`, each printing one JSON line.
The skill file still names the old CLI until batch 2 lands; nothing executes it in between (dispatched runs use the plugin cache).

## Cards

### Card 1: Rename ask-parent module, CLI and tests to ask-thread

- **Context:**
  - `_mill/discussion.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:**
  - `plugins/mill/scripts/_ask_parent.py` -> `plugins/mill/scripts/_ask_thread.py`
  - `plugins/mill/scripts/millpy-ask-parent.py` -> `plugins/mill/scripts/millpy-ask-thread.py`
  - `plugins/mill/unit_tests/test-ask-parent.py` -> `plugins/mill/unit_tests/test-ask-thread.py`
  - `plugins/mill/unit_tests/test-millpy-ask-parent.py` -> `plugins/mill/unit_tests/test-millpy-ask-thread.py`
- **Requirements:**
  - `git mv` all four files first, then make only these edits.
  - In `_ask_thread.py`: set `REPLY_REL_PATH = "_mill/ask-reply.md"`; in the module docstring replace the ``ask-parent`` skill name with ``ask-thread``.
  - In `millpy-ask-thread.py`: `import _ask_thread` instead of `import _ask_parent`, retarget every `_ask_parent.` reference to `_ask_thread.`, change the stderr prefix `[ask-parent]` to `[ask-thread]`, and update the docstring's file and skill names.
  - In `test-ask-thread.py`: `import _ask_thread`, retarget every `_ask_parent.` reference, update the docstring and the final "All ... unit tests passed." line.
  - In `test-millpy-ask-thread.py`: load `millpy-ask-thread.py` via `spec_from_file_location` under module name `millpy_ask_thread`, rename the module variable `millpy_ask_parent` to `millpy_ask_thread`, and change both `parent-reply.md` literals to `ask-reply.md`; update the docstring and final line.
  - No behaviour change in this card; both test files pass unchanged in substance.
- **Commit:** `refactor(ask-thread): rename ask-parent module, CLI and tests to ask-thread`

### Card 2: Add ask-id, reply-to, target and open mode to _ask_thread

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/millpy-ask-thread.py`
- **Edits:**
  - `plugins/mill/scripts/_ask_thread.py`
  - `plugins/mill/unit_tests/test-ask-thread.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Write the new tests in `test-ask-thread.py` first (TDD), then implement.
  - Add `import secrets`. Add `new_ask_id() -> str` returning `secrets.token_hex(4)`, and `ask_id_line(ask_id: str) -> str` returning `f"ask-id: {ask_id}"`.
  - `build_message(*, slug, worktree_root, reply_file, giveup_utc, ask_id, reply_to=None, site=None, reason=None, actions=None, questions=None) -> str`:
    - Action mode (`site`, `reason`, `actions` given, `questions` None): keep today's header lines and "Accepted actions:" list unchanged.
    - Open mode (`questions` given, `site`/`actions` None): header `[mill] Task {slug} has questions for you and waits for your answer.`, then `Worktree:`, `Reply file:`, and `Answer by {giveup_utc} UTC; after that the task asks its operator instead.`, a blank line, `Questions:`, then the `questions` text verbatim; no action list, no yaml `action:` shape.
    - Raise `ValueError` when neither or both mode inputs are given.
    - Both modes then render the reply instructions: the reply's first non-empty line must be `ask-id: <ask_id>` (render it literally with the real id); keep the answer short.
    - With `reply_to`: write the complete reply (the `ask-id` line plus the answer) to the reply file in one operation, AND send ONE `SendMessage` to `<reply_to>` with the same text; for a long answer the message may instead be the `ask-id` line plus `answered, see <reply_file>`. The rendered text must contain the literal word `SendMessage` and the `reply_to` name.
    - Without `reply_to`: answer by writing the reply file only, in one operation; the text must not contain `SendMessage`.
    - Reply shape shown: action mode = `ask-id:` line, then the existing fenced yaml `action: <one of: ...>` block, then free-text guidance; open mode = `ask-id:` line, then the answers by question number.
    - Output stays ASCII via `to_ascii`.
  - `prepare(*, status_path, worktree_root, cfg, slug, site=None, reason=None, actions=None, questions=None, target=None, reply_to=None, ask_id=None, now=None) -> dict`:
    - Still deletes a stale reply file first, on every path.
    - Action mode (site/actions given): `timeout_minutes(cfg) <= 0` -> `{"escalate": False, "reason": "disabled"}` (unchanged).
    - Open mode (questions given): never disabled; when `timeout_minutes(cfg) <= 0` use `DEFAULT_TIMEOUT_MINUTES`.
    - Resolved target = `target` when given, else `_status.read_parent_thread(status_path)`; `None` -> `{"escalate": False, "reason": "no target"}` (replaces today's `"no parent_thread"`).
    - `ask_id` defaults to `new_ask_id()`; an explicit value is used verbatim.
    - Escalate return keys: `escalate`, `target` (renamed from `parent_thread`), `ask_id`, `reply_path`, `giveup_s`, `message`, `unreachable_suffix` (still `unreachable_suffix(<target>)`).
  - `consume(reply_file, ask_id, actions=None) -> dict`:
    - Missing file -> no reply.
    - Otherwise read, delete the file (every path), and find the first non-empty line; it matches when `line.rstrip() == ask_id_line(ask_id)` (leading whitespace not stripped; overview Decision `ask-id-line-match-rule`). No match -> no reply.
    - On match, the body is the text after that line.
    - With `actions`: parse the body exactly as today's action parsing; no reply -> `{"action": "halt", "guidance": "", "halt_suffix": ""}`.
    - With `actions=None`: return `{"reply": body.strip()}`; no reply -> `{"reply": ""}`.
  - Update the module docstring's Public API list for the new and changed signatures.
  - Tests to add or adapt in `test-ask-thread.py` (keep every existing case, prepending the `ask-id` line to existing `consume` fixtures and passing `ask_id`):
    - `build_message` action mode with and without `reply_to` (name and `SendMessage` present only when given; reply file path and `ask-id: <id>` always present).
    - `build_message` open mode: questions included verbatim (non-ASCII folded to `?`), no `- approve:` list, no `action:` line.
    - `prepare`: `target` overrides `parent_thread`; no target and no `parent_thread` -> `"no target"`; timeout `0` -> `"disabled"` in action mode but open mode escalates with `giveup_s == DEFAULT_TIMEOUT_MINUTES * 60`; return key `target`; stale file deleted; two calls without `ask_id` return different ids and each message contains its id; explicit `ask_id` used verbatim.
    - `consume` open mode: missing file -> `{"reply": ""}`; matching id + content -> stripped text without the id line; file deleted.
    - `consume` both modes: missing id line or a different id -> no reply (`halt` / `""`), file deleted; a matching id line with trailing spaces still matches.
  - The CLI in `millpy-ask-thread.py` is updated by card 3; do not edit it in this card.
- **Commit:** `feat(ask-thread): add ask-id correlation, reply-to, target override and open mode`

### Card 3: Extend millpy-ask-thread CLI for direct mode, ask-id and resolve

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_ask_thread.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-ask-thread.py`
  - `plugins/mill/unit_tests/test-millpy-ask-thread.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Write the new CLI tests first (TDD), then implement.
  - No argparse `required=True` on the options below, and no mutually-exclusive argparse groups: every usage error is raised as `ValueError` inside `main` so it maps to exit 1 with one `[ask-thread] ...` stderr line and nothing on stdout (argparse's own exit 2 must not be reachable for these cases).
  - `prepare` options: `--site`, `--reason`, `--actions`, `--questions-file`, `--to`, `--reply-to`.
    - Automatic: `--site`, `--reason`, `--actions` all given, `--questions-file` absent; `--to` given -> `ValueError`. Calls `_ask_thread.prepare(... site=, reason=, actions=parse_actions(actions, site), reply_to=)`.
    - Direct: `--questions-file` given and none of `--site`/`--reason`/`--actions`; reads the file as UTF-8 and calls `_ask_thread.prepare(... questions=<text>, target=<--to or None>, reply_to=)`.
    - Any other combination -> `ValueError`.
  - `consume` options: `--ask-id` (missing -> `ValueError`), `--actions`, `--open` (store_true); exactly one of `--actions`/`--open` else `ValueError`. Calls `_ask_thread.consume(_ask_thread.reply_path(worktree_root), ask_id, actions_or_None)`.
  - New `resolve` subcommand with option `--to`: resolves `git_root`, `worktree_root`, `cfg` and `status_path` exactly as `prepare` does; raises `ValueError("not a mill task worktree: no status.md at <path>")` when `status_path` does not exist; otherwise prints `{"target": <--to, else _status.read_parent_thread(status_path), else null>}`.
  - Catch `OSError` alongside `ValueError`/`KeyError` in the exit-1 handler (unreadable questions file, missing config).
  - Update the module docstring's subcommand list.
  - Tests in `test-millpy-ask-thread.py` (keep existing cases, adapted: `data["target"]`, `consume` now passes `--ask-id` and writes the `ask-id:` line into the reply fixture):
    - `prepare --questions-file <tmp file>` happy path (escalates, message contains the questions, JSON has `ask_id`) and with `--to other` (`target == "other"`).
    - `--to` with `--site` -> exit 1, empty stdout.
    - `--questions-file` naming a nonexistent file -> exit 1, empty stdout (the `OSError` branch).
    - neither the `--site` set nor `--questions-file` -> exit 1.
    - `consume --ask-id <id> --open` returns the reply text and deletes the file.
    - `consume` without `--ask-id` -> exit 1; with both `--actions` and `--open` -> exit 1.
    - `reply_path` ends with `_mill/ask-reply.md`.
    - `resolve`: with `parent_thread` -> `mh:orch`; `--to x` -> `x`; no `parent_thread` -> `null`; a root without `_mill/status.md` -> exit 1.
- **Commit:** `feat(ask-thread): CLI direct mode, ask-id consume and resolve subcommand`

## Batch Tests

`verify:` runs `test-ask-thread.py` (module: message rendering, prepare, consume, config default) and `test-millpy-ask-thread.py` (CLI argument handling, JSON output, exit codes).
Both are pure tempfile fixtures with no git, LLM or harness.
