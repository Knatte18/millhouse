# Batch: ask-parent-skill

```yaml
task: Ask the parent session when stuck (parent_thread)
batch: ask-parent-skill
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skills-index.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py
depends-on: [1]
```

## Batch Scope

Creates the on-demand `ask-parent` skill that holds the whole LLM-side escalation procedure (run `prepare`, `SendMessage`, the re-arming `Monitor` wait, run `consume`, return), records what is and is not verified about `SendMessage` to a peer session in `harness-tool-contracts.md`, and regenerates `SKILLS.md`.
Batches 4 and 5 wire the converted halt sites to this skill using the return contract in the overview's `ask-parent-return-contract` Decision.
Pure skill/doc text: no Python changes.

## Cards

### Card 6: `ask-parent` skill

- **Context:**
  - `plugins/mill/skills/orch-wait/SKILL.md`
  - `plugins/mill/scripts/millpy-ask-parent.py`
  - `plugins/mill/docs/harness-tool-contracts.md`
  - `plugins/mill/scripts/_ask_parent.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/ask-parent/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Frontmatter (`---` delimited, parsed by the platform): `name: ask-parent`; `description: Internal machinery skill, not invocable directly. Loaded by autonomous mill skills before a converted halt -- asks the parent_thread session for guidance and waits a bounded time for _mill/parent-reply.md.`; `argument-hint: ""`.
    The description must contain no `: ` substring (it would break the frontmatter yaml).
  - Opening paragraph: loaded by `mill-plan`, `mill-go-base` (`mill-go`/`mill-go2`), `mill-start --auto`/`--orch` and `mill-quick` at the sites listed in `_ask_parent.SITES`, only when a halt is about to happen; interactive `mill-start` never loads it.
    Inputs from the caller: `site` (a key of `_ask_parent.SITES`), `reason` (the halt's blocked-reason text), `actions` (comma list the site accepts).
    Outputs to the caller: `action`, `guidance`, `halt_suffix`, with the meaning given in the overview's `ask-parent-return-contract` Decision (state that meaning in the skill text itself; do not cite the plan).
    The skill never edits `status.md`, never commits, never calls `_status.append_phase`, and never prompts (no `AskUserQuestion`, no numbered menu) — waiting on the parent is bounded by the timeout, not a decision point.
    Tracking the one-escalation-per-site limit is the caller's job.
  - `## Step 1 — Prepare`: run `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-parent.py" prepare --site <site> --reason '<reason>' --actions <actions>` from the task worktree, with `<reason>` single-quoted and every embedded `'` written as `'\''`.
    Parse the one JSON line.
    Exit 1 (usage error) -> return `action: halt`, empty `guidance`, empty `halt_suffix`, and report the stderr line.
    `escalate: false` -> return `halt`, empty `guidance`, empty `halt_suffix` (no parent configured, or `pipeline.parent_escalation_timeout_minutes` is `0`; today's halt proceeds unchanged).
    `escalate: true` -> keep `parent_thread`, `reply_path`, `giveup_s`, `message`, `unreachable_suffix`.
  - `## Step 2 — Send`: `SendMessage` is a deferred tool — load it with `ToolSearch` (`select:SendMessage`) first if its schema is not loaded.
    Call `SendMessage(to: <parent_thread>, message: <message>)` with `parent_thread` verbatim (never case-folded).
    If the call returns an error (no such session, renamed, restarted, gone) -> return `halt`, empty `guidance`, `halt_suffix = unreachable_suffix`; do not wait.
    Point at `plugins/mill/docs/harness-tool-contracts.md`'s `SendMessage` section for what is verified.
  - `## Step 3 — Announce`: print one line: `Asked parent <parent_thread> about <site>; waiting up to <giveup_s // 60> min for _mill/parent-reply.md`.
  - `## Step 4 — Wait for the reply file`: same mechanism and branching as `orch-wait/SKILL.md` Step 2 — record `wait_started_epoch` from `date +%s` once before the first arm, call `Monitor(command=cmd, timeout_ms: 1800000, description="waiting for parent reply (<site>) for <slug>")`, record the returned `task_id`.
    `cmd` is this poll script with `<reply_path>` and `<giveup_s>` substituted (include it verbatim as a fenced bash block):
    ```bash
    elapsed=0
    while true; do
      if [ -s "<reply_path>" ]; then
        sleep 5
        echo "READY"
        exit 0
      fi
      if [ "$elapsed" -ge <giveup_s> ]; then
        echo "TIMEOUT after ${elapsed}s waiting for parent-reply.md"
        exit 2
      fi
      sleep 15
      elapsed=$((elapsed + 15))
    done
    ```
    Explain the `sleep 5` after the non-empty check: it lets the parent finish writing before the file is read.
    Branching: `READY` -> Step 5.
    `TIMEOUT after <N>s ...` -> Step 5 (a missing file reads as `halt`; a reply that landed at the last moment is still honoured).
    Any other event content is an early `Monitor` expiry: compute `remaining_s = giveup_s - (now - wait_started_epoch)` from a fresh `date +%s`; `remaining_s <= 0` -> Step 5; otherwise re-arm with `<giveup_s>` replaced by `remaining_s`, record the new `task_id`, and keep waiting.
    The second, event-less `<status>completed</status>` notification needs no branch (see `plugins/mill/docs/harness-tool-contracts.md`).
    A harness-level stop of the recorded `task_id` -> Step 5 as well.
  - `## Step 5 — Consume`: run `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-parent.py" consume --actions <actions>`; parse the JSON line and return its `action`, `guidance`, `halt_suffix` to the caller.
    `consume` has already deleted the reply file, so the handoff out-of-scope-untracked-file gate never sees it.
  - `## Rules`: guidance is operator-level direction for this site's own retry/approve procedure only — apply it within the caller's documented scope (e.g. mill-go's orchestrator still never edits task code; mill-plan's fixes still touch only plan files);
    one escalation per site per run is enforced by the caller;
    no `sed` in any command this skill runs.
- **Commit:** `feat(ask-parent): add ask-parent escalation skill`

### Card 7: `SendMessage` note and five-wait references in `harness-tool-contracts.md`

- **Context:**
  - `plugins/mill/skills/ask-parent/SKILL.md`
- **Edits:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Opening paragraph: change the sentence naming `orch-wait` and `orch-review` as "two further consumers" so it names `orch-wait`, `orch-review` and `ask-parent` as three further consumers.
  - `## Monitor tool` section: every "four wait sections" / "All four wait sections" / "four consumers" reference becomes five, and the closing "See ..." sentence adds `ask-parent/SKILL.md`'s Step 4 to the named list.
  - Add a `## SendMessage to a peer session` section after `## Monitor tool`, recording:
    verified — `ListAgents` in a live session lists peer local Claude sessions by name (the orchestrator session appeared as `MH:orch`), so a named peer is addressable for an outbound `SendMessage(to: <name>, message: ...)`;
    unverified — whether a message wakes an idle peer session promptly, whether a woken session can be held open with a timeout, and whether name lookup is case-sensitive (`_vscode_tasks.session_prefix` lower-cases the names it assembles, e.g. `mh:orch`, while `ListAgents` listed `MH:orch`, so a spawner passing a differently-cased `--parent` value can surface as the unreachable fallback);
    design consequence — `ask-parent` never relies on a reply message: it treats a `SendMessage` error as "parent unreachable" and receives the answer as a file polled by `Monitor`, so the timeout bounds every unverified case.
    Wording: say `_vscode_tasks.session_prefix` lower-cases names, not a count of sessions or callers.
- **Commit:** `docs(harness): record SendMessage peer-session contract and ask-parent wait`

### Card 8: regenerate `SKILLS.md`

- **Context:**
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `plugins/mill/skills/ask-parent/SKILL.md`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Regenerate `SKILLS.md` with the scanner the `mill-skills-index` skill documents, run from the worktree root: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"`.
    Do not hand-edit `SKILLS.md`.
  - Confirm with `git diff SKILLS.md` that the only change is the new `ask-parent` row; if other rows change, the cached scanner differs from the worktree's — rerun with the worktree copy instead (`PYTHONPATH=plugins/mill/scripts "$MILL_PYTHON" plugins/mill/scripts/millpy-skills-index.py`) and re-check.
- **Commit:** `chore: regenerate SKILLS.md for ask-parent`

## Batch Tests

Pure skill/doc text, so `verify:` runs the existing lint tests that scan it, as chained direct invocations (see the overview's `skill-text-verify-uses-direct-invocations` Decision):
`test-skill-helper-drift.py` (every `_<module>.<fn>(` reference in the new SKILL.md resolves to a shipped function),
`test-skills-index.py` (SKILLS.md generation) and `test-guards.py` (source-tree anti-pattern guards over `plugins/mill/`).
