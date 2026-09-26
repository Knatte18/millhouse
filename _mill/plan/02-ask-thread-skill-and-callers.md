# Batch: ask-thread-skill-and-callers

```yaml
task: 'Unify ask-parent into ask-thread: ask any named session, default parent'
batch: "ask-thread-skill-and-callers"
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-ask-thread.py test-millpy-ask-thread.py
depends-on: [1]
```

## Rename mechanic

For each `Moves:` pair the implementer MUST:

1. Run `git mv <old> <new>` FIRST, before making any other change to the moved file.
2. Make ONLY surgical edits -- touch only the lines that must change after the move (package or module declaration, imports, identifier retargeting, seam splits).
3. Use a full-file `Creates:` entry only for genuinely new files that have no predecessor.
4. Never write the relocated file from scratch and delete the original -- that breaks git rename history and inflates review diffs.

For the skill file, "surgical" covers the sections the new protocol changes; sections whose behaviour is unchanged (Rules, the Monitor branching) keep their existing text apart from renames.

## Batch Scope

Moves the skill to `ask-thread`, rewrites it for both entry modes and the message-first reply protocol on top of batch 1's CLI, retargets every caller and doc reference, and updates the config comment in both config files.
Pure markdown/yaml-comment batch; the only runnable check is the unit tests from batch 1 (which also assert both config files still carry the default timeout key) plus the repo-wide grep gate in card 7.

## Cards

### Card 4: Move and rewrite the skill as ask-thread with automatic and direct modes

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_ask_thread.py`
  - `plugins/mill/scripts/millpy-ask-thread.py`
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:**
  - `plugins/mill/skills/ask-parent/SKILL.md` -> `plugins/mill/skills/ask-thread/SKILL.md`
- **Requirements:**
  - `git mv` first; the emptied `plugins/mill/skills/ask-parent/` directory must not remain.
  - Frontmatter: `name: ask-thread`, `argument-hint: "[thread-name]"`, and an ASCII `description` stating both modes, e.g. `Ask another Claude session. Automatic mode: loaded by autonomous mill skills before a converted halt, asks the parent_thread session for retry/approve/halt. Direct mode: /ask-thread [thread-name] routes this session's operator questions to that session (default parent_thread). Waits a bounded time for a reply message or _mill/ask-reply.md.` Drop "Internal machinery skill, not invocable directly".
  - Every script call uses `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-thread.py" <subcommand> ...` written literally; no `sed` anywhere.
  - Structure: an intro naming the two modes; "## Automatic mode" (inputs `site`/`reason`/`actions`, outputs `action`/`guidance`/`halt_suffix`, loaded by the same callers and sites as before via `_ask_thread.SITES`, target always `parent_thread`, never edits status.md, never commits, never prompts); "## Direct mode"; then shared steps "## Step 0 — Tools and own name", "## Step 1 — Prepare", "## Step 2 — Send", "## Step 3 — Announce", "## Step 4 — Wait", "## Step 5 — Consume"; then "## Rules".
  - Step 0: load via `ToolSearch` (`select:` listing only the missing ones among `SendMessage`, `ListAgents`, `Monitor`) any whose schema is not loaded. Call `ListAgents`; take `reply_to` from the first line `This session is <name> [<id>] ...` (text between `This session is ` and ` [`). If `ToolSearch` has no match, the call errors, or no such line exists, omit `--reply-to`. Never use `TaskStop`.
  - Step 1 automatic: `prepare --site <site> --reason '<reason>' --actions <actions> [--reply-to '<reply_to>']` (keep today's single-quote escaping note). Exit 1 or `escalate: false` -> return `halt`, empty `guidance`, empty `halt_suffix` (report the stderr line on exit 1). On `escalate: true` keep `target`, `ask_id`, `reply_path`, `giveup_s`, `message`, `unreachable_suffix`.
  - Step 1 direct: write the batch's questions with the Write tool to `.scratch/ask-thread-questions.md` in the task worktree (overwrite; not committed), then `prepare --questions-file .scratch/ask-thread-questions.md --to '<target>' [--reply-to '<reply_to>']`. Exit 1 -> direct-mode fallback.
  - Step 2: `SendMessage(to: <target>, message: <message>)`, `target` verbatim, never case-folded, no retry with another casing. Error -> automatic: `halt` with `halt_suffix = unreachable_suffix`, no wait; direct: fallback.
  - Step 3: one line. Automatic: `Asked <target> about <site>; waiting up to <giveup_s // 60> min for a reply (message or _mill/ask-reply.md)`. Direct: `Asked <target> questions <first>-<last>; waiting up to <giveup_s // 60> min for a reply (message or _mill/ask-reply.md)`.
  - Step 4 poll script (Monitor `timeout_ms: 1800000`, description `waiting for ask-thread reply (<site or direct>) for <slug>`, record `wait_started_epoch` before the first arm and each returned `task_id`), with `<reply_path>`, `<ask_id>`, `<giveup_s>` substituted:

    ```bash
    elapsed=0
    while true; do
      if awk 'NF{print; exit}' "<reply_path>" 2>/dev/null | grep -qxE "ask-id: <ask_id>[[:space:]]*"; then
        sleep 5
        echo "READY"
        exit 0
      fi
      if [ "$elapsed" -ge <giveup_s> ]; then
        echo "TIMEOUT after ${elapsed}s waiting for ask-reply.md"
        exit 2
      fi
      sleep 15
      elapsed=$((elapsed + 15))
    done
    ```

  - Step 4 branching keeps today's rules (READY / TIMEOUT / early expiry re-arm with `remaining_s` / harness stop -> Step 5; event-less completion needs no branch; cite `orch-wait/SKILL.md` Step 2 and the harness contract doc).
  - Step 4 message handling (add): when a message from the target arrives while waiting, check its first non-empty line for `ask-id: <ask_id>`. No match -> ignore it and keep waiting (re-arm per the expiry rules if the Monitor already expired). Match -> unless the reply file's first non-empty line already is the matching `ask-id` line (the file wins), write the message text verbatim to `reply_path` with the Write tool. Never cancel the Monitor; the running poll sees the file on its next tick and ends with `READY` -> Step 5. If no Monitor is armed at that moment, go to Step 5 directly. After Step 5, ignore any later event from an earlier `task_id` of this batch.
  - Step 5: automatic `consume --ask-id <ask_id> --actions <actions>` -> return `action`, `guidance`, `halt_suffix`. Direct `consume --ask-id <ask_id> --open` -> non-empty `reply` is the decision for this batch and the session continues; empty `reply` or exit 1 -> fallback. `consume` deletes the reply file on every path.
  - Direct mode section, covering the discussion.md "Two entry modes, one mechanism" and "Direct mode requires a mill task worktree" decisions:
    - Invocation `/ask-thread [thread-name]` by the operator or another agent. Run `resolve [--to '<thread-name>']` once. Exit 1 -> tell the user direct mode needs a mill task worktree (this includes the hub orch session) and stop. `target: null` -> tell the user direct mode cannot start (no thread name and no `parent_thread`) and stop. Otherwise remember `target`, run Step 0 once, and print one line that direct mode is on and questions go to `<target>`.
    - Lasts for the rest of the session until it ends or the operator says stop; binds skills loaded before or after it.
    - Whenever the session would ask the operator a question (a `mill:conversation` numbered-options menu, a free-text question in prose, or `AskUserQuestion` from a non-mill skill), send the questions to the target instead, in batches of at most 5 (Steps 1-5).
    - Each question is numbered, numbers continue across batches for the whole session, each carries the asker's recommended answer first and lists the alternatives.
    - Harness permission prompts are not covered. There is no hook or flag; the rule lives in this loaded skill only.
    - Automatic-mode halt sites in the same session still run automatic mode. Under `--auto`/`--orch` nothing is asked of the operator, so direct mode routes nothing there.
    - Fallback (prepare exit 1, `SendMessage` error, empty or timed-out reply): ask the operator directly with the same numbered questions.
  - Rules: keep today's guidance-scope and one-escalation-per-site-is-the-caller's-job rules for automatic mode, and the no-`sed` rule.
- **Commit:** `feat(ask-thread): replace ask-parent skill with ask-thread (automatic and direct modes)`

### Card 5: Point every caller at the ask-thread skill

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-quick/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate each reference with `grep -n "ask-parent" <file>` and replace the skill name `ask-parent` with `ask-thread` on those lines only; do not read these large files in full.
  - Site ids, reasons, actions, `parent_escalated_*` flags, `halt_suffix` handling and surrounding control flow stay byte-identical.
  - `mill-plan/SKILL.md` has three references (the Step 6 load plus two prose mentions of asking the parent session); all three change.
- **Commit:** `refactor(mill): load ask-thread instead of ask-parent at halt sites`

### Card 6: Update harness contract doc, SKILLS.md and timeout comments

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/ask-thread/SKILL.md`
- **Edits:**
  - `plugins/mill/docs/harness-tool-contracts.md`
  - `SKILLS.md`
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In the contract doc, rename every `ask-parent` mention to `ask-thread`; the two Monitor-section citations of the old skill's Step 4 become the `ask-thread` Step 4 wait (the step is titled "Step 4 — Wait" in card 4).
  - In its "SendMessage to a peer session" section add a Verified bullet: on 2026-09-26 `ListAgents`' first output line was `This session is <name> [<id>] ...` (e.g. `This session is mh:ask-thread-skill:start [68784b]`), which is how `ask-thread` learns its own name for `--reply-to`.
  - Keep the two Unverified bullets, extending the wake-up one to "a waiting asker" as well as an idle peer.
  - Rewrite the "Design consequence" bullet: `ask-thread` asks the target to reply with one `SendMessage` and always to write the reply file too; a matching reply message is written into the reply file and ends the wait early, while the `Monitor` poll on the file plus the timeout bound every unverified case; a `SendMessage` error is "target unreachable".
  - `SKILLS.md`: replace the `ask-parent` row with an `ask-thread` row linking `plugins/mill/skills/ask-thread/SKILL.md`, whose description cell is the new frontmatter `description` verbatim; keep the row's alphabetical position.
  - Bootstrap note (mill-config.yaml mid-flight safety): the hub config edit is comment-only; no key or value changes, so `_config.load_config` returns an identical dict before and after, and no running or future task (including this one) behaves differently.
  - Change only the trailing comment on `parent_escalation_timeout_minutes`, identically in both config files (key and value untouched), to: `# minutes ask-thread waits for a reply in either mode (automatic halt escalation, direct /ask-thread); 0 disables automatic escalation only, direct mode then waits the 60-minute default`.
- **Commit:** `docs(ask-thread): update harness contract, SKILLS.md and timeout comment`

### Card 7: Repo-wide ask-parent reference gate

- **Context:**
  - `_mill/discussion.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Run `grep -rn "ask-parent\|ask_parent\|parent-reply" plugins SKILLS.md mill-config.yaml` from the worktree root; it must print nothing.
  - Run `git ls-files plugins/mill/skills/ask-parent` and confirm empty output.
  - Any hit is a defect in the card that owns that file (cards 1-6); fix it there, not here.
- **Commit:** none

## Batch Tests

`verify:` reruns batch 1's two test files: the module and CLI the skill now calls, plus `test-ask-thread.py`'s check that both config files still carry `parent_escalation_timeout_minutes` at the default after card 6's comment edit.
The markdown changes have no runnable surface beyond card 7's grep gate.
