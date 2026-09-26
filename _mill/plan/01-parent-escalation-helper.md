# Batch: parent-escalation-helper

```yaml
task: Ask the parent session when stuck (parent_thread)
batch: parent-escalation-helper
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-ask-parent.py test-millpy-ask-parent.py
depends-on: []
```

## Batch Scope

Delivers every deterministic piece of the parent escalation: the `status.md` reader for `parent_thread:`, the `_ask_parent` helper module (site table, message rendering, reply parsing, suffix strings), the `millpy-ask-parent.py` CLI with `prepare`/`consume` subcommands, and the `pipeline.parent_escalation_timeout_minutes` config key.
Batch 3's `ask-parent` skill consumes the CLI's two JSON shapes; nothing in this batch touches skill text.
All tests use tempfile fixtures with no real git, wiki, or harness.

## Cards

### Card 1: `_status.read_parent_thread`

- **Context:**
  - `plugins/mill/templates/status-discussing.md`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `read_parent_thread(status_path: Path | str) -> str | None` to `_status.py`, placed immediately after `read_parent_branch`, and add the line `read_parent_thread(status_path) -> str | None` to the module docstring's `Public API:` list immediately after the `read_parent_branch` line.
  - Model it on `read_parent_branch`: coerce with `_as_path(status_path, "read_parent_thread")`, read `read_full(status_path)["yaml"].get("parent_thread")`, return the stripped string when the value is a `str` that is non-empty after `strip()`, else `None`.
    There is no legacy-key fallback.
    Catch `(OSError, ValueError, KeyError, TypeError)` and return `None` (a missing file, a missing/unterminated/malformed yaml block, or a non-dict yaml all end up here — `read_full` raises `ValueError` for those; `OSError` covers an unreadable file).
    Never case-fold the value.
  - Google-style docstring in the same shape as `read_parent_branch`'s: one summary line naming the `parent_thread:` row written by `millpy-spawn.py --parent`, that it names the session that spawned the task, and that it returns `None` on any parse failure.
  - Tests in `test-status.py`: add `read_parent_thread` to the existing `from _status import (...)` list and add a block directly after the existing `# --- read_parent_branch / set_parent_branch ---` block, reusing that block's `_yaml_status(rows)` helper style (assert + `print("PASS: ...")`).
    Cases: `parent_thread: mh:orch` -> `"mh:orch"` (use the lower-case name, per the discussion's name-exactness rule);
    row absent -> `None`;
    `parent_thread: ""` -> `None`;
    `parent_thread: "   "` -> `None`;
    a status file whose yaml fence holds unparseable yaml (e.g. `phase: [unclosed`) -> `None`;
    a path that does not exist -> `None`.
- **Commit:** `feat(status): add read_parent_thread`

### Card 2: `_ask_parent` helper module

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-timestamp.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_ask_parent.py`
  - `plugins/mill/unit_tests/test-ask-parent.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Create `_ask_parent.py` with a module docstring (purpose + `Public API:` list, same style as `_status.py`'s) and these public names.
  - Constants: `REPLY_REL_PATH = "_mill/parent-reply.md"`, `DEFAULT_TIMEOUT_MINUTES = 60`, `ACTIONS = ("retry", "approve", "halt")`, `GUIDANCE_SUFFIX_MAX = 200`.
  - `SITES: dict[str, dict]` — the closed set of converted sites; each value is `{"label": str, "actions": dict[str, str]}` mapping each accepted action to a one-line ASCII description of what it does at that site.
    Use a module constant `_HALT_TEXT = "the run stops here and waits for the operator"` for every `halt` entry.
    Entries (label; non-halt action descriptions):
    `go-batch` ("mill-go per-batch stuck escalation"; retry: "mill-go records your guidance in the batch plan file and re-runs the batch implementer once");
    `go-holistic-cap` ("mill-go holistic review round cap"; approve: "mill-go accepts the holistic review as-is and proceeds to handoff"; retry: "mill-go passes your guidance to the holistic fixer and runs one extra review round");
    `go-handoff-nits` ("mill-go handoff unfixed-nits gate"; retry: "mill-go re-runs the NIT-fix pass once with your guidance");
    `go-handoff-done-gate` ("mill-go handoff done gate"; retry: "mill-go re-dispatches mill-done-gate-fixer once with your guidance and re-runs the done gate");
    `plan-cap` ("mill-plan plan review round cap"; approve: "mill-plan approves the plan with the remaining BLOCKING findings waived"; retry: "mill-plan applies your guidance to the plan files and runs one extra review round");
    `start-cap` ("mill-start --auto discussion review round cap"; approve: "mill-start accepts discussion.md as-is and hands off to mill-plan"; retry: "mill-start applies your guidance to discussion.md and runs one extra review round");
    `quick-gate` ("mill-quick done gate"; retry: "mill-quick applies your guidance as a fix and re-runs the done gate once").
    Every site accepts `halt`; only `go-holistic-cap`, `plan-cap`, `start-cap` accept `approve`.
  - `to_ascii(text: str) -> str`: replace every non-ASCII character with `?` (`text.encode("ascii", "replace").decode("ascii")`).
  - `parse_actions(actions_csv: str, site: str | None = None) -> list[str]`: split on commas, strip each item, drop empties, keep order, de-duplicate.
    Raise `ValueError` when the result is empty, when any item is not in `ACTIONS`, when `site` is given but not a key of `SITES`, or when `site` is given and an item is not in `SITES[site]["actions"]`.
  - `timeout_minutes(cfg: dict) -> int`: read `(cfg.get("pipeline") or {}).get("parent_escalation_timeout_minutes", DEFAULT_TIMEOUT_MINUTES)`; `None` means the default; coerce with `int()`, and fall back to `DEFAULT_TIMEOUT_MINUTES` when `int()` raises `TypeError`/`ValueError`.
  - `reply_path(worktree_root: Path) -> Path`: return `_paths.resolve_task_path(worktree_root, REPLY_REL_PATH)`.
  - `unreachable_suffix(parent_thread: str) -> str`: return `f" (parent_thread {parent_thread} unreachable)"` passed through `to_ascii`.
  - `halt_suffix(guidance: str) -> str`: take the first non-blank line of `guidance`, strip it, `to_ascii` it, truncate to `GUIDANCE_SUFFIX_MAX` characters, return `f" -- parent: {line}"`; return `""` when `guidance` has no non-blank line.
  - `build_message(*, slug: str, site: str, reason: str, worktree_root: Path, reply_file: Path, actions: list[str], giveup_utc: str) -> str`: plain-ASCII message (pass the whole result through `to_ascii`; replace newlines inside `reason` with spaces first).
    Lines, in order: `[mill] Task <slug> is about to halt and asks you (its parent session) for a decision.`;
    `Site: <site> (<SITES[site]["label"]>)`;
    `Blocked reason: <reason>`;
    `Worktree: <worktree_root>`;
    `Reply file: <reply_file>`;
    `Answer by <giveup_utc> UTC; after that the task halts for the operator.`;
    a blank line; `Accepted actions:`; one `- <action>: <description>` line per entry of `actions`, descriptions from `SITES[site]["actions"]`;
    a blank line; `Reply by writing the reply file in one operation, with this exact shape:`; then the literal lines of a fenced yaml block (three backticks + `yaml`, `action: <one of: <comma-joined actions>>`, three backticks), followed by `<free-text guidance for the task: what to change, or why to stop>`.
    The message must be self-describing: the parent needs no mill skill to answer.
  - `prepare(*, status_path: Path, worktree_root: Path, cfg: dict, slug: str, site: str, reason: str, actions: list[str], now: datetime | None = None) -> dict`:
    (1) resolve `reply_file = reply_path(worktree_root)` and delete it if present (`unlink(missing_ok=True)`) — always, before any early return, so a late reply from an earlier escalation never leaks into this one;
    (2) `minutes = timeout_minutes(cfg)`; when `minutes <= 0` return `{"escalate": False, "reason": "disabled"}`;
    (3) `parent = _status.read_parent_thread(status_path)`; when `None` return `{"escalate": False, "reason": "no parent_thread"}`;
    (4) `giveup_s = minutes * 60`; `giveup_utc = ((now or datetime.now(timezone.utc)) + timedelta(seconds=giveup_s)).strftime("%Y-%m-%dT%H:%M:%SZ")`;
    (5) return `{"escalate": True, "parent_thread": parent, "reply_path": str(reply_file), "giveup_s": giveup_s, "message": build_message(...), "unreachable_suffix": unreachable_suffix(parent)}`.
    `parent_thread` is returned verbatim (never case-folded).
  - `consume(reply_file: Path, actions: list[str]) -> dict` returning `{"action": str, "guidance": str, "halt_suffix": str}`:
    missing file -> `{"action": "halt", "guidance": "", "halt_suffix": ""}`;
    otherwise read the text (UTF-8, `errors="replace"`), then delete the file (`unlink(missing_ok=True)`) before parsing, so it is deleted on every path.
    Find the first fenced yaml block with a regex (a line of three backticks + `yaml`, body, a closing line of three backticks); `yaml.safe_load` its body.
    `guidance` is the text after the closing fence, stripped; when there is no yaml block, `guidance` is the whole text stripped.
    `action` is the parsed dict's `action` value, stripped and lower-cased, when the block parsed to a dict whose `action` is a string; otherwise `"halt"`.
    An `action` not in `actions` becomes `"halt"`.
    `halt_suffix` is `halt_suffix(guidance)` when the final action is `"halt"`, else `""`.
    `yaml.YAMLError` during parsing means `"halt"`, never an exception.
  - Tests in `test-ask-parent.py`, following `test-timestamp.py`'s shape (`HUB`/`sys.path` bootstrap, a `main() -> int` of assert + `print("PASS: ...")` blocks, `sys.exit(main())`), with fixtures under `tempfile.TemporaryDirectory()`: a fake worktree holding `_mill/status.md` written in the same yaml-fence + `## Timeline` text-fence shape `_status.read_full` parses, with and without a `parent_thread: mh:orch` row.
    Cover: `prepare` with no `parent_thread` row -> `{"escalate": False, "reason": "no parent_thread"}`;
    `prepare` with `cfg = {"pipeline": {"parent_escalation_timeout_minutes": 0}}` -> `reason: "disabled"`;
    `prepare` with `cfg = {}` -> `giveup_s == 3600`;
    a stale `_mill/parent-reply.md` is deleted by `prepare` on both the escalate and the non-escalate path;
    the `prepare` message contains the slug, the site id, the reason, the reply path, every accepted action, and is ASCII (`message.isascii()`), including when the reason contains a non-ASCII character;
    `giveup_utc` in the message equals `now + giveup_s` for a fixed `now`;
    `consume` for each of `retry`, `approve`, `halt` when accepted;
    an action outside the passed list -> `halt`;
    missing file -> `halt` with empty guidance;
    a file with no yaml block, a block with invalid yaml, and a block without `action:` -> `halt`;
    guidance text after the block is returned stripped;
    the file no longer exists after `consume`;
    `halt_suffix` truncates to 200 characters and uses only the first non-blank line;
    `unreachable_suffix("mh:orch") == " (parent_thread mh:orch unreachable)"`;
    `parse_actions` rejects an unknown action, an empty list, an unknown site, and `approve` for `go-batch`.
- **Commit:** `feat(ask-parent): add _ask_parent helper module`

### Card 3: `millpy-ask-parent.py` CLI

- **Context:**
  - `plugins/mill/scripts/_ask_parent.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/millpy-builder-lock.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-ask-parent.py`
  - `plugins/mill/unit_tests/test-millpy-ask-parent.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Create `millpy-ask-parent.py` with a module docstring in `millpy-builder-lock.py`'s style (one-line purpose, `Subcommands:` list, exit codes) and `main(argv=None) -> int` using `argparse` subparsers (`dest="command", required=True`), same structure as `millpy-builder-lock.py`'s `main`.
  - `prepare --site <site-id> --reason <text> --actions <comma-list>` (all three required): resolve `git_root = _paths.resolve_git_root()`, `worktree_root = _paths.resolve_hub_path()`, `cfg = _config.load_config(worktree_root, git_root)`, `status_path = _paths.status_path(worktree_root, cfg)`, `slug = _status.read_slug(status_path)`, `actions = _ask_parent.parse_actions(args.actions, args.site)`, then print `json.dumps(_ask_parent.prepare(...))` as one line and return 0.
  - `consume --actions <comma-list>` (required): resolve `worktree_root = _paths.resolve_hub_path()`, `actions = _ask_parent.parse_actions(args.actions)`, print `json.dumps(_ask_parent.consume(_ask_parent.reply_path(worktree_root), actions))` as one line and return 0.
  - A `ValueError` from `parse_actions` (or from `_paths.status_path`'s `KeyError` on a config without `paths.status_md`) prints one ASCII line to stderr and returns 1 with nothing on stdout.
  - `json.dumps` keeps its default `ensure_ascii=True`, so stdout stays ASCII.
  - End the file with `if __name__ == "__main__": sys.exit(main())`.
  - Tests in `test-millpy-ask-parent.py`: load the script via `importlib.util.spec_from_file_location("millpy_ask_parent", <path to millpy-ask-parent.py>)` + `module_from_spec` + `spec.loader.exec_module` (the hyphenated filename cannot be imported directly), use the `test-timestamp.py` `main() -> int` shape, and patch `millpy_ask_parent._paths.resolve_git_root`, `millpy_ask_parent._paths.resolve_hub_path` (both returning the tempdir worktree) and `millpy_ask_parent._config.load_config` (returning a dict with `paths.status_md: _mill/status.md` plus a `pipeline` section) with `unittest.mock.patch.object`; capture stdout with `contextlib.redirect_stdout`.
    Cover: `prepare` with `parent_thread: mh:orch` prints one JSON line with `escalate: true`, `parent_thread == "mh:orch"`, `reply_path` ending in `_mill/parent-reply.md`, and the slug in `message`;
    `prepare` without the row prints `escalate: false`;
    `prepare --actions approve,halt --site go-batch` returns 1 with empty stdout;
    `consume --actions retry,halt` after writing a reply file with `action: retry` prints `action: "retry"` and removes the file;
    `consume` with no reply file prints `action: "halt"`;
    stdout is ASCII in every case.
- **Commit:** `feat(ask-parent): add millpy-ask-parent.py prepare/consume CLI`

### Card 4: `pipeline.parent_escalation_timeout_minutes` config key

- **Context:**
  - `plugins/mill/scripts/_ask_parent.py`
- **Edits:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/unit_tests/test-ask-parent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Bootstrap note (why this `mill-config.yaml` change is safe mid-flight): the key is new, nothing outside this task reads it, and its only consumer, `_ask_parent.timeout_minutes`, returns `DEFAULT_TIMEOUT_MINUTES` (60) when it is absent — so a task running on the old hub config and a task running on the new one behave identically.
  - In both `mill-config.yaml` (hub) and `plugins/mill/templates/mill-config.yaml`, add under `pipeline:` directly after the `entry_wait_timeout_minutes: 240` line, matching that line's indentation and inline-comment style: `parent_escalation_timeout_minutes: 60  # minutes an autonomous skill waits for its parent_thread session's reply before halting; 0 disables parent escalation`.
    Keep the two files' lines byte-identical.
  - In `test-ask-parent.py`, add a check that loads both yaml files with `yaml.safe_load` (hub file at `HUB / "mill-config.yaml"`, template at `HUB / "plugins" / "mill" / "templates" / "mill-config.yaml"`) and asserts `data["pipeline"]["parent_escalation_timeout_minutes"] == _ask_parent.DEFAULT_TIMEOUT_MINUTES` for both.
- **Commit:** `feat(config): add pipeline.parent_escalation_timeout_minutes`

## Batch Tests

`verify:` runs `test-status.py` (card 1's reader cases alongside the existing status tests), `test-ask-parent.py` (cards 2 and 4: helper logic plus the hub/template config key check) and `test-millpy-ask-parent.py` (card 3: CLI wiring and JSON shapes).
All three use tempfile fixtures; none touches real git, the wiki, or the harness.
