# Discussion: Ask the parent session when stuck (parent_thread)

```yaml
task: Ask the parent session when stuck (parent_thread)
slug: parent-thread-escalation
status: discussing
parent_branch: main
```

## Problem

When an autonomous mill skill (`mill-plan`, `mill-go`, `mill-start --auto`/`--orch`, `mill-quick`) hits a blocker its own self-resolve step cannot clear, it records `phase: blocked` and halts.
The task then sits until a human notices, even when the task was spawned by an orchestrator session that is running right now and could unblock it in one sentence.

`status-parent-fields` (merged, commit `d082aca4`) added an optional `parent_thread:` row to `status.md`, written by `millpy-spawn.py --parent <name>`.
It names the session that spawned the task (for example `MH:orch`).
Nothing reads it yet.
This task makes the autonomous skills ask that session for guidance before halting, wait a bounded time for the answer, and fall back to today's halt when there is no parent, the parent is unreachable, or it does not answer in time.

## Scope

**In:**

- `_status.read_parent_thread(status_path) -> str | None`.
- A new helper module `plugins/mill/scripts/_ask_parent.py` and CLI `plugins/mill/scripts/millpy-ask-parent.py` with `prepare` and `consume` subcommands (see Decisions).
- A new on-demand skill `plugins/mill/skills/ask-parent/SKILL.md` holding the whole escalation procedure (send, wait, consume, branch).
- New config key `pipeline.parent_escalation_timeout_minutes` in both the hub `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml`.
- Wiring the escalation into the converted halt sites listed under the `converted-sites` Decision.
- A short "SendMessage to a peer session" note in `plugins/mill/docs/harness-tool-contracts.md` recording what is and is not verified.
- Regenerating root `SKILLS.md` for the new skill (the `mill-skills-index` skill).
- Unit tests for the new helper, CLI, and status reader.

**Out:**

- Interactive `mill-start` (no flag).
  A human is present in that session's own terminal;
  its questions keep going to that human, never to the parent.
- Escalating routine choices.
  Under `--auto`/`--orch`, Phase: Discuss keeps auto-picking option 1;
  mill-plan and mill-go keep their existing self-resolve steps.
  Only a would-be halt escalates.
- A parent-side companion skill.
  The message sent to the parent is self-describing (see `message-shape`);
  the parent answers by writing one file.
- Infrastructure / precondition halts (see the user-only list in `converted-sites`).
- `millpy-spawn.py` / `mill-spawn` changes: `--parent` already exists.
  Making orchestrators (mill-pool, orch sessions) pass `--parent` is a separate concern.
- `mill-go2`-specific text: it loads `mill-go-base`, so it inherits the mill-go-base wiring with no separate edit.

## Decisions

### interactive-stays-user-only

- Decision: escalation to the parent applies only to autonomous runs: `mill-plan`, `mill-go`/`mill-go2` (via `mill-go-base`), `mill-start --auto`/`--orch`, and `mill-quick`.
  Interactive `mill-start` is unchanged.
- Rationale: the brief's fallback "ask the user directly, exactly as today" already describes the interactive path;
  an interactive session has a human at its own prompt, and forwarding their questions to another session would bypass them.
  The autonomous skills never ask a question today (they auto-pick or self-resolve), so the only place a parent adds value is a halt.
- Rejected: routing every `mill-start` interview question to the parent when `parent_thread` is set — floods the orchestrator and duplicates the `--orch` mechanism, which already covers "orchestrator reviews the discussion".

### wait-mechanism

- Decision: the question goes out with `SendMessage(to: <parent_thread>, message: ...)`.
  The answer comes back as a file, `<worktree_root>/_mill/parent-reply.md`, which the child waits for with a `Monitor` file-exists poll, using the same re-arming pattern as `orch-wait` Step 2 (record `wait_started_epoch`, `timeout_ms: 1800000`, re-arm on an event-less expiry with the remaining budget, `READY` / `TIMEOUT after <N>s ...` lines).
- Rationale: whether a `SendMessage` wakes an idle child session, and whether a woken child can be held open with a timeout, is unverified;
  the `Monitor` file poll is verified in four existing waits and gives the timeout for free.
  `ListAgents` in a live session confirmed that peer local sessions are addressable by name (`MH:orch` is listed as a peer of this task's session), so the outbound direction works.
  If the parent is busy or idle and the message is not processed promptly, the timeout covers it.
- Rejected: reply via `SendMessage` back to the child — needs the child's own session name (auto-derived, e.g. `parent-thread-escalation-d6`, not predictable from the slug), and gives no timeout.
  Rejected: file-only (no message) — the parent would have to poll every child worktree.

### timeout-config

- Decision: new key `pipeline.parent_escalation_timeout_minutes`, default `60` when absent.
  `0` disables escalation entirely: every converted site halts exactly as today without sending anything.
  Read the same way `pipeline.entry_wait_timeout_minutes` is read.
  Add it next to `entry_wait_timeout_minutes` in both the hub `mill-config.yaml` and the plugin template, with a one-line comment.
- Rationale: "autonomous means no menu" — an unattended run must always terminate;
  a timeout that expires falls back to today's halt.
  60 minutes is long enough for an orchestrator mid-turn to get to it and short enough that a dead parent does not park a task for the 4-hour entry-wait budget.
- Rejected: reusing `entry_wait_timeout_minutes` — different semantics (upstream-skill wait vs. human-ish reply).

### unreachable-parent

- Decision: fall back to today's halt, with no wait, when any of these hold:
  `parent_thread` is unset or empty;
  the timeout config is `0`;
  `SendMessage` returns an error (session renamed, restarted, or gone).
  On the `SendMessage` error case the halt's `blocked_reason` gets the suffix ` (parent_thread <name> unreachable)` so the operator sees why no one was asked.
  A reply that arrives after the timeout is ignored;
  `prepare` deletes any leftover `parent-reply.md` before the next escalation.
- Rationale: matches the brief ("fall back to asking the user");
  for an autonomous skill, the halt message plus `blocked` status is how it asks the user.
- Rejected: pre-checking with `ListAgents` — the `SendMessage` result is the authoritative check, and a pre-check adds a race without removing the need to handle the send error.
- Name exactness: `parent_thread` is sent verbatim, never case-folded.
  The spawner must pass `--parent` the exact live session name as `ListAgents` prints it.
  Whether `SendMessage` name lookup is case-sensitive is unverified;
  `_vscode_tasks.session_prefix` lower-cases the names it assembles (`mh:orch`), while `ListAgents` in this task's session listed the orchestrator as `MH:orch`, so a case mismatch between what a spawner passes and the live name is possible and surfaces as the unreachable fallback.
  Record this in the `harness-tool-contracts.md` note.
  Unit tests use a lower-case name (`mh:orch`).

### reply-format

- Decision: `parent-reply.md` is markdown with a fenced ` ```yaml ` block carrying `action: <retry | approve | halt>`, followed by free-text guidance.
  Each converted site declares which actions it accepts (see `converted-sites`).
  A missing file at timeout, an unparseable block, or an action the site does not accept is treated as `halt`.
  On `halt`, the parent's guidance text (first line, truncated to 200 chars) is appended to `blocked_reason` as ` -- parent: <text>`.
  The file is ephemeral: `consume` deletes it after reading, and it is never committed.
- Rationale: a closed action set keeps the child's branching mechanical;
  the guidance body carries the judgment the parent adds.
  Treating anything malformed as `halt` makes the safe outcome the default.
- Rejected: free-text-only replies — the child would have to infer intent, and a wrong inference auto-approves work.

### message-shape

- Decision: the message sent to the parent is rendered by `prepare`, plain ASCII, and carries: slug; skill and site (e.g. `mill-go batch <name>`); the blocked reason; the absolute worktree path; the absolute reply path; the accepted actions with one line each on what they do at this site; the give-up time in UTC; and the exact reply format (the yaml block plus guidance).
- Rationale: the parent needs no mill skill loaded to answer — it may be a human-driven orchestrator session.
- Rejected: a parent-side skill (like `orch-review`) — more surface for a one-file reply.

### helper-and-cli

- Decision: mechanise the deterministic parts in `_ask_parent.py` + `millpy-ask-parent.py` (turn-reduction initiative):
  - `prepare --site <site-id> --reason <text> --actions <comma-list>`: resolves paths/config via `_paths`/`_config`, reads `parent_thread` via `_status.read_parent_thread`, reads the timeout, deletes a stale `parent-reply.md`, and prints one JSON line:
    `{"escalate": true, "parent_thread": ..., "reply_path": ..., "giveup_s": ..., "message": ...}` or `{"escalate": false, "reason": "no parent_thread" | "disabled"}`.
  - `consume --actions <comma-list>`: reads and deletes `parent-reply.md`, prints `{"action": "retry" | "approve" | "halt", "guidance": "<text>"}` applying the `reply-format` fallback rules (missing file -> `halt` with empty guidance).
  The LLM-side steps (calling `SendMessage`, arming `Monitor`, applying guidance) live in the `ask-parent` skill.
- Rationale: `SendMessage` and `Monitor` are harness tools and cannot be called from a script;
  everything else is pure logic and unit-testable.
  Paths resolve through `_paths.py` per the repo's path invariants;
  stdout is ASCII only.
- Rejected: inlining the procedure into each skill — six copies drift.

### ask-parent-skill

- Decision: new skill `plugins/mill/skills/ask-parent/SKILL.md` ("conditional mechanics get their own skill").
  Each converted site says: "before halting, load the `ask-parent` skill with site `<id>`, reason `<text>`, actions `<list>`; branch on its result".
  The skill's steps: run `prepare`;
  if `escalate` is false, return `halt` (with the unreachable suffix only for a send error);
  call `SendMessage`;
  on error return `halt` with the unreachable suffix;
  report `"Asked parent <name> about <site>; waiting up to <N> min for _mill/parent-reply.md"`;
  run the `Monitor` wait;
  run `consume`;
  return the action and guidance to the caller.
  The skill never edits `status.md` itself — the caller owns status writes and commits.
  Frontmatter marks it internal (not user-invocable), like `orch-wait`.
- Rationale: one procedure, loaded only when a halt is imminent, so it costs nothing on the happy path.
- Rejected: a longer name like `parent-thread-escalation` — keep skill names short.

### escalate-before-recording-block

- Decision: at each converted site, the escalation runs before the site's `set_blocked` / `set_batch_field(..., "blocked")` / commit, so `retry` and `approve` have nothing to undo.
  Where the current text records the block first and then jumps to a shared funnel (mill-go-base's per-stuck-type bullets all set batch state `blocked` then "go to *Blocked*"), restructure so the bullets compute `blocked_reason` and go to *Blocked*, and *Blocked* runs the escalation first, then records state.
  No `_status.append_phase` call happens during the wait: `append_phase` overwrites `phase:`, which entry gates read.
  The `handoff.md` halts (`go-handoff-gate`) never call `set_blocked`;
  they call `_notify.notify(...)` then `millpy-builder-lock.py release`, then halt.
  There the escalation runs before that notify + release pair, and the builder lock stays held for the whole wait (the lock is per-worktree, so holding it blocks nothing else).
  The same ordering applies at *Blocked* in mill-go-base: escalate first, then notify, release the lock, and tell the user only when the halt proceeds.
- Rationale: keeps `status.md` consistent if the session dies mid-wait (it still reads as the pre-halt phase and a re-run resumes normally).
- Rejected: record `blocked` first and flip it back on `retry` — a crash mid-wait leaves a block that the parent already cleared.

### one-escalation-per-site

- Decision: each converted site escalates at most once per failure site per run: once per batch in mill-go, once per review loop in mill-plan/mill-start/holistic review, once per run in mill-quick.
  If the retried or re-reviewed step fails again, the site halts as today without asking again.
- Rationale: bounds parent traffic and guarantees termination.
- Rejected: unlimited escalations — an unhelpful parent could loop a task forever.

### converted-sites

- Decision: these sites escalate;
  every other halt stays user-only (unchanged).

  | Site id | Location | Accepted actions | Effect of `retry` / `approve` |
  |---|---|---|---|
  | `go-batch` | `mill-go-base/SKILL.md` `### Blocked` (covers every `### Stuck escalation` branch: infrastructure after re-fire, transient, incomplete, verify/logic after self-resolve) | `retry`, `halt` | `retry`: apply the guidance (plan-file edits, a `## Prior failure` bullet quoting the guidance), append phase `parent-guided-retry`, commit, re-fire the implementer for the batch under the same re-dispatch rules as the existing verify/logic self-resolve re-fire (fresh session; for `incomplete`, the `start_sha`-preserving resume path instead). mill-go-base has no `Commit: none` idempotency guard today, so a re-fire can repeat an uncommitted external action exactly as the self-resolve re-fire can; this task inherits that behaviour and adds no guard. |
  | `go-holistic-cap` | `mill-go-base/holistic-review.md` round-cap exhausted with `auto_approve_on_cap: false` | `approve`, `retry`, `halt` | `approve`: run the same terminal actions the `auto_approve_on_cap: true` branch runs, with commit-message suffix `(approved by parent)`. `retry`: one extra holistic round with the guidance passed to the fixer. |
  | `go-handoff-gate` | `mill-go-base/handoff.md` done-gate still `blocked` after the one fixer dispatch, and the "unfixed nits" halt | `retry`, `halt` | `retry`: dispatch the fixer once more with the guidance, then re-run the gate. |
  | `plan-cap` | `mill-plan/SKILL.md` step 6 max-rounds escape (the `"max-rounds exhausted"` block) | `approve`, `retry`, `halt` | Reuse mill-plan's own in-session override procedures (Phase: Plan Review), treating the parent's reply as the live operator instruction they already accept. `approve`: run the "Live operator waiver of step 6" implicit-approve-at-cap path (direct-`Edit` `approved: true` in `plan/00-overview.md`, commit, push, Handoff), with the commit-message parenthetical reading `(parent waived remaining BLOCKINGs at round cap)` so the audit trail names who waived. It does not re-enter through the Entry step 4 `--approve` pre-check, whose `phase == "blocked"` / `"max-rounds exhausted"` conditions do not hold because the block is not yet recorded. `retry`: apply the guidance to the plan files first, then bind `operator_max_review_rounds = <current effective cap> + 1` per "Live operator-raised round-cap override" (its precedence over `max_review_rounds` / `local_max_review_rounds` and its `--max-rounds <operator_max_review_rounds>` threading through every prepare/finalize and Step 3.5 retry site apply unchanged) and continue the loop. |
  | `start-cap` | `mill-start/SKILL.md` `--auto`/`--orch` non-progress cap branch with `auto_approve_on_cap: false` | `approve`, `retry`, `halt` | `approve`: the same terminal actions as the `auto_approve_on_cap: true` branch, commit-message suffix `(approved by parent)`. `retry`: one extra round with the guidance applied to `discussion.md` first, passing `--max-rounds <current round + 1>` with the same threading mill-start's own "Auto mode non-progress-extension round" uses (the extension round may already have been spent, so the cap is computed from the current round, not `max_review_rounds`). |
  | `quick-gate` | `mill-quick/SKILL.md` done-gate failure | `retry`, `halt` | `retry`: apply the guidance as a fix, commit, re-run the done gate once. |

  User-only (unchanged): marker / slug / wiki-status / lock-busy / phase-gate preconditions;
  `CLAUDE_PLUGIN_ROOT` and config-source checks;
  entry-gate timeouts;
  `orch-wait` and `orch-review` timeouts (the parent is the party that did not answer);
  every ERROR-only, usage-error, rate-limit, and dead-worker (`millpy-bg` `"dead"`) halt;
  `plan-validate non-progress`;
  the handoff dirty-tree and out-of-scope-untracked-file gates (deleting or committing files on a remote session's say-so is not worth the risk).
- Rationale: escalate where judgment can unblock (logic, cap exhaustion, failing gates);
  keep infrastructure and precondition failures with the human, since a parent session cannot fix a logout, a rate limit, or a misconfigured worktree.
- Rejected: converting every halt — floods the parent with things it cannot fix.

## Technical context

- `status.md` fields: `plugins/mill/scripts/_status.py`.
  `read_parent_branch` (around line 949) is the model for `read_parent_thread`: read via `read_full(status_path)["yaml"]`, return the stripped string or `None` on any parse failure.
  `render_initial` writes `parent_thread:` (quoted via `quote_scalar`) only when set.
  `append_phase` overwrites `phase:` and clears `blocked_reason` on non-`blocked` phases;
  `set_blocked(status_path, reason, *, timestamp)` is the task-level halt;
  batch-level halts use `set_batch_field(..., "blocked_reason", ...)` + `append_phase(..., "blocked", ...)`.
- `millpy-spawn.py --parent <name>` writes the row;
  control characters are rejected there.
  Session names come from `_vscode_tasks.build_command` (`claude -n "<prefix>:<phase>"`), but a session launched another way carries an auto-derived name, so the child's own name is not predictable — hence file-based replies.
- `orch-wait/SKILL.md` Step 2 is the reference implementation of the re-arming `Monitor` file wait, including the event-branching rules and the two-notification contract in `plugins/mill/docs/harness-tool-contracts.md`.
- mill-go-base `### Stuck escalation` and `### Blocked` are in `plugins/mill/skills/mill-go-base/SKILL.md`;
  holistic-review cap handling is near the end of `plugins/mill/skills/mill-go-base/holistic-review.md` (the `auto_approve_on_cap` branch);
  handoff gates are in `plugins/mill/skills/mill-go-base/handoff.md` (the "unfixed nits" halt and the done-gate `result: blocked` fixer dispatch).
- mill-plan step 6 "Max-rounds escape" and the `--approve` re-entry procedure (Entry step 4) are in `plugins/mill/skills/mill-plan/SKILL.md`.
- mill-start's `--auto` non-progress cap branch is in the "Phase: Discussion Review — `--auto` changes" bullet list of `plugins/mill/skills/mill-start/SKILL.md`.
- mill-quick's done-gate failure path is its step that calls `_status.set_blocked(status_path, f"done gate failed: ...")`.
- `_notify.notify` is fired by existing halts;
  keep those calls, firing them only when the halt proceeds.
- Script invocation form: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-ask-parent.py" ...`.
- Tree-guard: `parent-reply.md` is untracked and short-lived;
  `_treeguard.check_and_restore` restores only git-reported deleted tracked paths, so it does not interfere.
  The handoff out-of-scope-untracked-file gate must not trip on it: `consume` deletes it before any gate runs, and `prepare` deletes stale copies.
- Root `SKILLS.md` is generated from SKILL.md frontmatter via the `mill-skills-index` skill.

## Constraints

- No hub-root `CONSTRAINTS.md` exists.
- CLAUDE.md hard constraints apply: `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths;
  all path resolution through `_paths.py`;
  ASCII-only `print()` output;
  hub `mill-config.yaml` and plugin template stay in sync;
  no `sed` in any skill text or generated prompt;
  generated markdown uses fenced yaml, not frontmatter (`SKILL.md` frontmatter excepted).
- Autonomous skills must always terminate without operator input (the timeout guarantees this).

## Testing

- `_status.read_parent_thread` (TDD): present, absent, empty/whitespace, unparseable yaml, missing file.
- `_ask_parent` / `millpy-ask-parent.py` (TDD), tempfile fixtures with a fake worktree + `status.md` + config, no real git or harness:
  - `prepare`: no `parent_thread` -> `escalate: false`;
    timeout `0` -> `escalate: false, reason: disabled`;
    default timeout when the key is absent;
    stale `parent-reply.md` is deleted;
    message contains slug, site, reason, reply path, accepted actions, and is ASCII.
  - `consume`: each valid action;
    action not in the site's accepted list -> `halt`;
    missing file -> `halt`;
    malformed/missing yaml block -> `halt`;
    guidance extracted;
    file deleted after read.
- Config: the new key exists in both `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml` (extend the existing hub/template sync test if one exists).
- Skill wiring is prose;
  no automated test beyond any existing skill-text lint.
  Verify command for new tests follows the `PYTHONPATH= uv run --project plugins/mill ...` form.

## Q&A log

- **Q:** Does escalation apply to interactive `mill-start`? **A:** [auto-pick] No, autonomous runs only. **Why:** a human is already at that session's prompt; the brief's fallback describes today's interactive path.
- **Q:** How does the child receive the parent's answer? **A:** [auto-pick] `SendMessage` out, reply file `_mill/parent-reply.md` polled by `Monitor`. **Why:** the only verified wait-with-timeout mechanism; child session names are not predictable, so reply-by-message is unreliable.
- **Q:** What timeout, and can it be disabled? **A:** [auto-pick] New `pipeline.parent_escalation_timeout_minutes`, default 60, `0` disables. **Why:** bounded autonomous runs; a switch for repos that want today's behaviour.
- **Q:** What if `parent_thread` names a session that no longer exists? **A:** [auto-pick] Halt as today, with ` (parent_thread <name> unreachable)` appended to `blocked_reason`. **Why:** the `SendMessage` error is authoritative; the suffix tells the operator no one was asked.
- **Q:** How is the reply structured? **A:** [auto-pick] Fenced yaml `action: retry|approve|halt` plus free-text guidance; anything malformed or not accepted by the site means `halt`. **Why:** mechanical branching with a safe default.
- **Q:** Which halt sites convert? **A:** [auto-pick] The six in the `converted-sites` table; infrastructure/precondition halts stay user-only. **Why:** a parent can unblock judgment failures, not logouts or rate limits.
- **Q:** How many escalations per failure? **A:** [auto-pick] One per site per run. **Why:** guarantees termination and bounds parent traffic.
- **Q:** Is a parent-side skill needed? **A:** [auto-pick] No; the message is self-describing. **Why:** YAGNI; the parent may be a human-driven session.
