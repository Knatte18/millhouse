# Discussion: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
task: 'Unify ask-parent into ask-thread: ask any named session, default parent'
slug: ask-thread-skill
status: discussing
parent_branch: main
```

## Problem

`ask-parent` lets an autonomous mill skill ask its `parent_thread` session for a retry/approve/halt decision before it halts.
Two things are missing.
A session cannot ask an arbitrary named session, only its parent.
Nothing lets a session route its ordinary questions (the ones it would otherwise put to the operator) to another session.
The operator wants one skill for "ask another thread": `ask-thread`, invocable directly as `/ask-thread [thread-name]`, and still loaded automatically before halts exactly as `ask-parent` is today.
There must not be two skills doing the same thing.

The current reply channel is file-only (`_mill/parent-reply.md`, polled by `Monitor`), because it was unverified whether a `SendMessage` wakes an idle peer.
The operator wants the reply to be one message back, with a file as an optional attachment for long answers, while the timeout still bounds every unverified delivery case.

## Scope

**In:**

- Rename skill `plugins/mill/skills/ask-parent/` -> `plugins/mill/skills/ask-thread/`, module `_ask_parent.py` -> `_ask_thread.py`, CLI `millpy-ask-parent.py` -> `millpy-ask-thread.py`, tests `test-ask-parent.py` -> `test-ask-thread.py`, `test-millpy-ask-parent.py` -> `test-millpy-ask-thread.py` (`git mv`, then edit).
- Reply file `_mill/parent-reply.md` -> `_mill/ask-reply.md` (`REPLY_REL_PATH`).
- New direct mode in the skill, script and CLI (open questions, free-text reply).
- Reply-by-message protocol for both modes, with the reply file kept as attachment and safety net.
- Optional `--to <name>` target override and `--reply-to <name>` asker name on `prepare`.
- Update every caller reference: `mill-go-base/SKILL.md`, `mill-go-base/handoff.md`, `mill-go-base/holistic-review.md`, `mill-plan/SKILL.md`, `mill-quick/SKILL.md`, `mill-start/SKILL.md` (skill name `ask-parent` -> `ask-thread`; site ids, reasons, actions and control flow unchanged).
- `plugins/mill/docs/harness-tool-contracts.md`: rename references, record the newly verified `ListAgents` self-name line, rewrite the "Design consequence" bullet for the message-first protocol.
- `SKILLS.md` row for the renamed skill.
- Comment on `pipeline.parent_escalation_timeout_minutes` in `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml` (kept in sync) to say it bounds both modes.

**Out:**

- No `ask-parent` alias (plain rename).
- The config key `pipeline.parent_escalation_timeout_minutes` keeps its name.
- `orch-wait` / `orch-review` (file-based `--orch` flow) unchanged.
- `millpy-spawn.py` / `mill-spawn` / `.vscode/tasks.json` session commands: no flag that turns direct mode on at spawn.
- The halt sites' behaviour: same sites, same `SITES` table, same actions, same one-escalation-per-site bookkeeping in the callers, same `halt_suffix` semantics.
- The target session's side: the target needs no mill skill; the message is self-describing.
- Any mechanism that restarts a target whose context grew large.
- `status.md`'s `parent_thread:` field and `_status.read_parent_thread` (reused as-is).
- Historical `_mill/` files and the git history mentioning `ask-parent`.

## Decisions

### Plain rename, no alias

- Decision: rename everything to `ask-thread` in one commit series; no `ask-parent` stub skill.
- Rationale: the task forbids two skills doing the same thing; every caller is in this repo and is updated in the same task, and a plugin cache refresh (`./update-plugins.sh`) swaps both at once.
- Rejected: a thin `ask-parent` alias for one release — nothing outside the plugin loads it.

### Two entry modes, one mechanism

- Decision: the skill has two sections sharing Steps Prepare / Send / Wait / Consume.
  - **Automatic mode** (inputs `site`, `reason`, `actions`; outputs `action`, `guidance`, `halt_suffix`): loaded by the same callers at the same sites as today.
    Target is always `status.md` `parent_thread`.
    Behaviour matches today's `ask-parent`, except the reply may arrive as a message (next decision).
  - **Direct mode**: `/ask-thread [thread-name]`, invoked by the operator or by another agent.
    Target is `thread-name` when given, else `parent_thread`; neither -> tell the user direct mode cannot start and stop.
    Once invoked, direct mode lasts for the rest of the session (until the session ends or the operator says stop).
    Whenever the session would otherwise ask the operator a question, it instead sends the questions to the target in batches of at most 5.
    "Ask the operator" covers every operator question the agent itself poses: `mill:conversation` numbered-options menus and free-text questions in prose.
    `AskUserQuestion` is listed as covered too, defensively: `mill:conversation` forbids it in mill sessions, but a non-mill skill loaded in the same session may still reach for it.
    Question numbers continue across batches for the whole direct-mode session (batch 2 starts at 6 after a 5-question batch 1), so a reply or later message can refer to any question unambiguously.
    It binds skills loaded before or after `/ask-thread` alike.
    Harness permission prompts are not agent questions and are not covered.
    The rule is an instruction held in the session's context by the loaded `ask-thread` skill; there is no hook, flag or other enforcement mechanism, and the plan must not add one.
    Each question is numbered, carries the asker's recommended answer first, and lists the alternatives (same shape as `mill:conversation`'s numbered-options rule).
    The free-text reply is taken as the decision and the session continues.
    No fixed answer set, no action enum, no `halt_suffix`.
    Direct mode never changes automatic-mode sites: a halt site in the same session still runs automatic mode.
    Under `--auto`/`--orch` a session asks the operator nothing, so direct mode has nothing to route there.
  - Direct-mode fallback (no target, `SendMessage` error, `escalate: false`, or timeout with no reply): ask the operator directly with the same numbered questions.
  - Automatic-mode fallback: unchanged — return `halt` (with `unreachable_suffix` on a send error).
- Rationale: one skill, one send/wait/timeout path; the brief pins both behaviours.
- Rejected: a separate direct-mode skill (two skills for one job).

### Reply protocol: message first, file as attachment and safety net

- Decision:
  - The asker passes its own session name as `--reply-to`.
    It takes it from `ListAgents`' first line, `This session is <name> [<id>] ...` (verified live on 2026-09-26: `This session is mh:ask-thread-skill:start [68784b]`), using the text between `This session is ` and ` [`.
    If `ListAgents` is unavailable or has no such line, `--reply-to` is omitted.
  - The rendered message tells the target: keep the answer short; write the complete reply (the `ask-id` line plus the answer) to the reply file (absolute path given) in one operation, AND send ONE `SendMessage` to `<reply-to>` with the same text (for a long answer the message may instead be the `ask-id` line plus "answered, see <path>").
    The file write is required for every reply, short or long, as long as message wake-up of a waiting asker is unverified: it is the channel the `Monitor` poll can see, so a message that never reaches the asker still ends the wait.
    The message is the reply channel whenever it arrives and ends the wait early.
    Once wake-up is verified live, a later task may make the file optional (attachment-only for long answers) as the brief intends; that is a message-text and SKILL.md change only, since the asker already handles both.
    Without `--reply-to`, the message tells the target to answer by writing the reply file only.
  - Automatic mode: after the `ask-id` line (next bullet), the reply (message or file) carries the same fenced ```` ```yaml ```` `action:` block as today, followed by free-text guidance.
  - **Batch correlation (`ask-id`).** Every `prepare` call generates a fresh `ask_id` (short random hex, e.g. `secrets.token_hex(4)`; `prepare` accepts an explicit `ask_id` for tests) and returns it in its JSON.
    The rendered message shows it and requires every reply — message or file — to have `ask-id: <ask_id>` as its first non-empty line.
    One reply is exactly one message or one file; the first reply carrying the current `ask_id` is the complete answer.
    A message or file without the current `ask_id` (a late reply to an earlier, timed-out batch, a follow-up or split second message, or an unrelated message) is not a reply: the asker ignores it and keeps waiting for the current deadline.
    Messages arriving after the current batch was consumed are ignored the same way, since they cannot carry the next batch's id.
  - The asker waits with the existing `Monitor` poll on the reply file (re-arm and expiry rules unchanged), except that `READY` fires only when the file's first non-empty line is `ask-id: <ask_id>` (poll with `grep -q` on that line instead of `[ -s ]`), so a stale or mismatched file never ends the wait.
  - When a message from the target arrives while waiting: check its first non-empty line for `ask-id: <ask_id>` first.
    No match: ignore it; the `Monitor` keeps running (re-arm per the expiry rules if it has already expired).
    Match: stop the recorded `Monitor` task (`TaskStop`), then — unless the reply file already starts with the matching `ask-id` line (the target used the attachment path; the file wins) — write the message text verbatim to the reply file with the Write tool; then run `consume`.
  - `consume` re-checks the id: a missing file, or one whose first non-empty line is not `ask-id: <ask_id>`, is treated as no reply (automatic mode: `halt`; direct mode: empty reply -> ask the operator).
    The `ask-id` line is stripped before parsing the yaml block (automatic) or returning the text (direct).
  - `READY` / `TIMEOUT` / harness stop from `Monitor`: run `consume` exactly as today.
  - Every path ends in `consume`, which reads and deletes the file, so parsing stays in Python and the file never survives to the handoff untracked-file gate.
- Rationale: whether a `SendMessage` wakes an idle asker is unverified; the file poll plus timeout keeps both modes correct whichever way that turns out, and routing message text through the file keeps one parser.
  The poll can be dropped later if message wake-up is verified.
- Rejected: message-only, including message-only for short replies (a missed message would always burn the full timeout with no alternative channel); file-only (today's behaviour, contradicts the brief); a separate request file the target polls (targets are human-driven sessions, which do not poll).

### Script and CLI shape

- Decision:
  - `_ask_thread.build_message(...)` gains keyword `reply_to: str | None` and an open mode: when `questions` (text) is given instead of `site`/`actions`, it renders a header (asker slug, worktree, deadline, reply instructions) plus the questions verbatim, and no action list or yaml shape.
    The action-list mode keeps today's content, plus the reply-to instructions.
    Output stays plain ASCII via `to_ascii`.
  - `_ask_thread.prepare(...)` gains `target: str | None = None` (overrides `parent_thread`) and `reply_to: str | None = None`; open mode is selected by passing `questions` instead of `site`/`actions`.
    Return key `parent_thread` is renamed `target`, and a new key `ask_id` is added; `escalate: false` reasons are `"disabled"` and `"no target"`.
    `build_message` takes `ask_id` and renders it with the first-line echo instruction in both modes.
    Still deletes a stale reply file first.
  - `_ask_thread.consume(reply_file, ask_id, actions=None)`: verifies and strips the `ask-id` first line (mismatch or missing file = no reply); with `actions` it then behaves as today (no reply -> `halt`); with `actions=None` (open mode) it returns `{"reply": <stripped text>}` (empty string for no reply). It deletes the file on every path.
  - CLI `millpy-ask-thread.py`:
    - `prepare --site <id> --reason <text> --actions <csv> [--reply-to <name>]` (automatic)
    - `prepare --questions-file <path> [--to <name>] [--reply-to <name>]` (direct); `--site`/`--actions` and `--questions-file` are mutually exclusive and one set is required; `--to` is rejected in automatic mode (exit 1).
    - `consume --ask-id <id> --actions <csv>` (automatic) or `consume --ask-id <id> --open` (direct); `--ask-id` always required, `--actions`/`--open` exactly one required.
    - Log/error prefix `[ask-thread]`.
  - The questions file lives at `.scratch/ask-thread-questions.md` in the task worktree; the skill writes it with the Write tool before each batch and it is not committed.
- Rationale: the multi-line question text goes through a file rather than a shell-quoted argument; one module keeps one timeout/stale-file/ASCII path.
- Rejected: the agent composing the direct-mode message itself (loses the shared header, deadline and ASCII guarantees).

### Direct mode requires a mill task worktree

- Decision: direct mode runs only where `status.md` resolves (the reply file lives in `_mill/`, the timeout comes from mill config).
  Outside one, the skill tells the user and stops.
- Rationale: YAGNI; every current asker is a mill task session.
- Rejected: a scratch-dir reply file and default timeout for non-mill repos.

### Target name used verbatim

- Decision: `--to`, the skill argument and `parent_thread` are passed to `SendMessage` verbatim, never case-folded.
  A mismatch surfaces as a `SendMessage` error -> fallback.
- Rationale: case-sensitivity of name lookup is still unverified (task sessions are lower-cased `mh:...`, the orch session is `MH:orch`); guessing a case transform could address the wrong session.
- Rejected: case-folding the name, or retrying with a lower-cased name after a `SendMessage` error (could address a different session).

### Spawn does not switch direct mode on

- Decision: out of scope; the operator or an agent invokes `/ask-thread` in a session.
- Rationale: `millpy-spawn.py` has no `--follow` flag today, and turning direct mode on at launch means changing the generated session commands for every phase; that is a separate feature.
- Rejected: a new `millpy-spawn.py --follow` flag that records a direct-mode marker in `status.md` for sessions to pick up.

### Target context growth

- Decision: no restart mechanism; the message asks the target for short replies and routes long answers into the reply file, which keeps the target's own context small.
- Rejected: a per-target message counter that warns or stops direct mode after N batches (no evidence yet of the limit to pick).

### Delivery tests

- Decision: no automated test of real `SendMessage` delivery (unit tests never touch the harness).
  `harness-tool-contracts.md` keeps "does a message wake an idle peer / a waiting asker" as unverified, and states the protocol is correct either way because of the file poll and timeout.
  The first live use by the operator is the manual check; updating the contract doc from its result is a later edit.
- Rejected: an integration test that drives two real Claude sessions (needs live harness sessions, which the test suites never start).

## Technical context

- Current implementation: `plugins/mill/skills/ask-parent/SKILL.md` (Steps 1-5: prepare, send, announce, Monitor wait on the reply file, consume), `plugins/mill/scripts/_ask_parent.py` (`SITES`, `ACTIONS`, `parse_actions`, `timeout_minutes`, `reply_path`, `unreachable_suffix`, `halt_suffix`, `build_message`, `prepare`, `consume`), `plugins/mill/scripts/millpy-ask-parent.py` (argparse, subcommands `prepare`/`consume`, one JSON line on stdout, exit 1 with a stderr line on `ValueError`/`KeyError`).
- Callers (load the skill by name, pass `site`/`reason`/`actions`): `mill-go-base/SKILL.md` (site `go-batch`), `mill-go-base/handoff.md` (`go-handoff-nits`, `go-handoff-done-gate`), `mill-go-base/holistic-review.md` (`go-holistic-cap`), `mill-plan/SKILL.md` (`plan-cap`, plus two prose mentions), `mill-quick/SKILL.md` (`quick-gate`), `mill-start/SKILL.md` (`start-cap`).
  `grep -rn "ask-parent\|ask_parent\|parent-reply" plugins SKILLS.md` lists every reference; after the task it must return nothing outside `_mill/`.
- `_status.read_parent_thread(status_path)` returns the `parent_thread:` value or `None`.
- `_paths.resolve_task_path(worktree_root, REPLY_REL_PATH)` resolves the reply file; keep using it.
- The skill's Monitor poll script and re-arm rules reference `orch-wait/SKILL.md` Step 2 and `harness-tool-contracts.md`'s Monitor section; the `harness-tool-contracts.md` Monitor section cites `ask-parent/SKILL.md`'s Step 4 — update that citation to the new path and step name.
- `SendMessage`, `TaskStop`, `ListAgents` are deferred or top-level tools; the skill loads `SendMessage`/`TaskStop` via `ToolSearch` (`select:SendMessage,TaskStop`) when their schemas are not loaded.
- New skill frontmatter: `name: ask-thread`, `argument-hint: "[thread-name]"`, a description stating both modes (drop "Internal machinery skill, not invocable directly").
- Session names: `_vscode_tasks.session_prefix` lower-cases task-session names (`mh:<slug>:<phase>`); the hub orch session is `MH:orch`.

## Constraints

- `print()` / CLI output ASCII only (CLAUDE.md).
- No `sed` in any command the skill runs or prompts.
- `${CLAUDE_PLUGIN_ROOT}` literally for script paths in the SKILL.md.
- `mill-config.yaml` hub file and plugin template stay in sync.
- The halt sites keep their exact behaviour; automatic mode must stay a drop-in for `ask-parent`.
- Unit tests: in-memory/tempfile fixtures, no real git/LLM/harness; run via `run-all.py`.

## Testing

- `test-ask-thread.py` (renamed from `test-ask-parent.py`, keep every existing case with names updated) — TDD candidates:
  - `build_message` action mode with and without `reply_to`: reply-to name and "SendMessage" instruction present only when given; reply file path always present.
  - `build_message` open mode: questions text included verbatim (ASCII-folded), no action list, no yaml `action:` shape.
  - `prepare` with `target` overriding `parent_thread`; `target=None` and no `parent_thread` -> `escalate: false, reason: "no target"`; timeout `0` -> `"disabled"`; return key `target`.
  - `prepare` still deletes a stale reply file.
  - `consume` open mode: missing file -> `reply: ""`; matching `ask-id` + content -> stripped text without the id line; file deleted.
  - `consume` id check, both modes: missing `ask-id` line or a different id -> no reply (`halt` / `""`), file deleted.
  - `consume` action mode: existing cases, with the `ask-id` line prepended.
  - `prepare` returns a fresh `ask_id` per call (two calls differ) and the message contains it; an explicit `ask_id` is used verbatim.
- `test-millpy-ask-thread.py` (renamed) — CLI: `prepare --questions-file` happy path and `--to` override; `--to` with `--site` -> exit 1; neither `--site` set nor `--questions-file` -> exit 1; `consume --ask-id <id> --open`; `consume` without `--ask-id` -> exit 1; reply path ends with `_mill/ask-reply.md`.
- Repo-wide check: the grep in Technical context returns nothing outside `_mill/`.

## Q&A log

- **Q:** Keep `ask-parent` as a thin alias for one release? **A:** [auto-pick] No, plain rename. **Why:** the task forbids two skills doing the same thing; all callers are updated in the same task.
- **Q:** How does a reply message reach the asker's parser? **A:** [auto-pick] The asker writes the message text into the reply file (unless the target already wrote it) and runs `consume`. **Why:** one parser, one cleanup path, and the file poll stays as the safety net for unverified wake-up.
- **Q:** Rename `pipeline.parent_escalation_timeout_minutes`? **A:** [auto-pick] Keep the key, update its comment. **Why:** renaming breaks existing hubs' configs for no behaviour gain.
- **Q:** Should spawn be able to switch direct mode on? **A:** [auto-pick] Out of scope. **Why:** no `--follow` flag exists; it means changing generated session commands, a separate feature.
- **Q:** Where does the asker get its own session name? **A:** [auto-pick] `ListAgents`' `This session is <name> [<id>]` line, omitted when absent. **Why:** verified live on 2026-09-26; scripts cannot read it.
- **Q:** Direct mode outside a mill task worktree? **A:** [auto-pick] Not supported. **Why:** the reply file and timeout come from `_mill/` and mill config; every current asker is a task session.
- **Q:** Automated test of real message delivery? **A:** [auto-pick] No; manual check on first live use. **Why:** unit tests never touch the harness, and the protocol is correct either way.
- **Q:** The brief says the reply file is not mandatory, but message wake-up is unverified; must the target still write the file for short replies? **A:** [auto-pick] Yes, the target writes the file and sends the message for every reply until wake-up is verified. **Why:** otherwise a missed short-reply message burns the full timeout; the brief itself defers the safety-net decision to the delivery test.
