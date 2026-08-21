---
name: mill-go-base
description: Internal machinery skill, not invocable directly. Loaded by /mill-go and /mill-go2, which bind the variant contract this skill reads.
---

# mill-go-base

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are the **Builder** — a lean orchestrator.
You coordinate per-batch implementation but never read card bodies or diffs yourself.
The **Implementer** (spawned per batch) reads its own batch file, implements cards, runs `verify:`, and fixes on receive-review.
You read only `status.md`, the Batch Index DAG in `00-overview.md`,
and the fenced yaml verdict block of each code review.
Keeping your context lean is the whole point — Builder cost is a rounding error next to the Implementer and code-reviewer calls.

## Entry

**Variant binding and driver preamble.**
This block runs before Step 0, because Step 0's halt string is itself one of the parameterized
`[<VARIANT_LABEL>]` prefixes below, so `VARIANT_LABEL` must be bound before Step 0 is reached.

This skill is never invoked directly. A variant skill loads it and binds `VARIANT_LABEL` in that
variant's own `## Variant binding` block. Read the variant's `## Variant binding` block, bind
`VARIANT_LABEL` to the value declared there, and substitute that value for every `<VARIANT_LABEL>`
token in this file. If no variant loaded this skill, or the loading variant declares no
`VARIANT_LABEL`, halt with the literal message
`[mill-go-base] HALT: mill-go-base is not invocable directly -- run /mill-go or /mill-go2.`

Override point B: treat your variant's `## Driver preamble` text as if written here, ahead of
everything below; if your variant declared no such section, halt — this skill is not invocable
directly. A variant whose `## Driver preamble` section contains only `(none)` has declared the
section and contributes no text; that is not a halt.

**Step 0: Verify `CLAUDE_PLUGIN_ROOT`.**

```bash
[ -n "${CLAUDE_PLUGIN_ROOT}" ] || { echo "[<VARIANT_LABEL>] HALT: CLAUDE_PLUGIN_ROOT is not set" >&2; exit 1; }
```

**Path variable rule:** All Bash tool calls in this skill use `${CLAUDE_PLUGIN_ROOT}` directly — it is an environment variable already present in the shell.
Do NOT read or memorize its value.
Write the variable reference;
the shell expands it at runtime.
The full absolute path must never appear in a command string.

**Step 0b: Load `mill:conversation`.**
Load the `mill:conversation` skill via the Skill tool, unconditionally, immediately after Step 0 and before any other Entry step or phase. mill-go no longer surfaces any operator-facing prompt (the former `### Stuck escalation` prompts and the holistic-rounds-exhausted prompt are now unconditional self-resolve-then-escalate or halt paths — see `### Stuck escalation` and `plugins/mill/skills/mill-go-base/holistic-review.md`);
this skill is loaded defensively in case a future addition needs its numbered-options convention.

1. Read the task slug: `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`.
   On `MarkerError` → halt with `str(e)` (the exception's own message). `signature: _marker.slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str`
2. Resolve the wiki path: `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())`.
3. Load config — load `mill-config.yaml` from the hub root, merged with `.millhouse/config.local.yaml`, via `_review_common.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path() / ".millhouse")`.
   Read these keys:
   - `pipeline.auto_merge` — whether to invoke mill-finalize after success.
   - `pipeline.auto_report` — whether to auto-fire mill-self-report at end-of-work. mill-go fires it at `plugins/mill/skills/mill-go-base/handoff.md` step 6, AFTER any `/mill-merge` invocation in step 5 — including after PR-pending halts.
     See step 6 for the explicit "do not treat PR-pending as termination" rule.
   - `pipeline.entry_wait` — master on/off switch for the entry-gate blocking wait (default `true` if the key is absent).
   - `pipeline.entry_wait_timeout_minutes` — give-up timeout in minutes for the entry-gate wait (default `240` if the key is absent).
   - `roles.code-review.batch.rounds` — max review rounds per batch.
   - `roles.code-review.batch.min_rounds` — floor: the per-batch review loop may not terminate on APPROVE before this round (default `1` when absent). See "Convergence gate" under `### 3. Code Review loop` below.
   - `roles.code-review.holistic.rounds` — max holistic review rounds (parallel cap for the holistic scope, default 1).
   - `roles.code-review.holistic.min_rounds` — floor: the holistic review loop may not terminate on APPROVE before this round (default `1` when absent). See "Convergence gate" in `plugins/mill/skills/mill-go-base/holistic-review.md`.
   - `roles.implementer.self_fix_rounds` — passed to the implementer brief.
   - `roles.code-review.holistic.reviewer` — if non-null, run one holistic code review after all batches approve.
   - `roles.code-review.batch.reviewer` — if null (or rounds: 0), skip per-batch code review for all batches.
4. Acquire the builder lock:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" acquire <slug>
   ```
   On exit code 1: surface the stderr message and halt — a second mill-go will corrupt state. 4.5.
   **Path Setup.** `worktree_root` is not yet set in prior steps;
   `slug` is in scope from step 1 and `cfg` was loaded in step 3.
   Derive:
   ```python
   git_root       = _paths.resolve_git_root()
   container_path = _paths.resolve_container_path(git_root)
   worktree_root  = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)
   status_path   = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])
   plan_dir      = _paths.resolve_task_path(worktree_root, cfg['paths']['plan_dir'])
   overview_path = plan_dir / "00-overview.md"
   reviews_dir   = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])
   task_dir      = status_path.parent  # absolute; compute_terminal_dirt relativizes internally
   ```
   Use these variables for all subsequent path references.
   Exception: the cleanliness snapshot path `_mill/.cleanliness-snapshot-<batch_name>.txt` keeps its `_mill/` literal — `millpy-implement.py` writes it unconditionally to `_mill/` and is out of scope.
5. **Entry phase gate.**
   Before reading `status_path`, guard against the merge-interrupted state where `_mill/status.md` has been removed by mill-merge's cleanup commit but teardown did not complete -- mirrors mill-merge's own Step 5 fallback.
   Wiki daemon errors are caught explicitly so a daemon outage surfaces a readable message instead of a raw traceback.
   ```python
   if not status_path.exists():
       import sys
       from wiki import _client
       from wiki import WikiStartupError, WikiProtocolError
       import _phase_gate
       try:
           task = _client.get_task(wiki_path, slug)
       except (WikiStartupError, WikiProtocolError) as e:
           print(f"_mill/status.md absent and wiki daemon unavailable: {e} -- inspect manually.", file=sys.stderr)
           raise SystemExit(1)
       print(_phase_gate.absent_status_halt_message(task, slug), file=sys.stderr)
       raise SystemExit(1)
   ```

   Inspect the phase:
   ```python
   status = _status.read_full(status_path)
   phase = status["yaml"]["phase"]
   blocked_reason = status["yaml"].get("blocked_reason")
   ```
   `signature: _status.read_full(status_path: Path) -> {"yaml": dict, "timeline": list[str]}`

   | phase | action |
   | --- | --- |
   | `planned` | fresh run — continue to Prepare |
   | `implementing` / `reviewing` / `fixing`, or matching the widened batch-scoped set (see "### Mid-execution phase-gate widening" below) | resume or routed continuation — see subsection |
   | `blocked` | surface `blocked_reason` from status.md and halt |
   | `discussed` / `discussing` / `planning`, or matching `^plan-review-r\d+$` / `^plan-fix-r\d+$` / `^discussion-fix-r\d+$` / `^discussion-gap-fix-r\d+$` | wait for `phase: planned` (see "Entry-gate wait for upstream mill-plan" below) if `pipeline.entry_wait` is true; otherwise tell user to finish mill-plan and halt |
   | `done` | tell user the task is complete; suggest `/mill-finalize` if auto-merge was off |
   | any other | surface + halt |

### Mid-execution phase-gate widening

Whenever the phase-table lookup above lands on the widened `implementing`/`reviewing`/`fixing` row, compute the match to determine which of the seven branches fired:

```python
matched = _phase_wait.matches_wait_trigger(
    phase,
    {"implementing", "reviewing", "fixing", "self-resolved-verify-logic", "holistic-approved"},
    [r"^approved-.*$", r"^reviewing-.*-r\d+$", r"^fixing-.*-r\d+$", r"^holistic-reviewing$"],
)
```

`matched` is always `True` here — the table row above is defined by this same predicate, so this call only distinguishes which branch fired.
Route on the current `phase` value:

- `implementing` / `reviewing` / `fixing` (bare, unsuffixed) — route to `## Resume` (`plugins/mill/skills/mill-go-base/resume.md`), unchanged from today.
- `reviewing-{batch_name}-rN` / `fixing-{batch_name}-rN` — route to `## Resume` (`plugins/mill/skills/mill-go-base/resume.md`).
  That batch's `state` in `## Batches` genuinely is `reviewing`/`fixing`, so Resume's step 1 (locate the entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`) matches it unchanged.
- `approved-{batch_name}` — fires *between* batches: the just-finished batch is `state: approved`, every other batch is either already `approved` or still `pending`, so no batch entry is `running`/`reviewing`/`fixing` and Resume's (`plugins/mill/skills/mill-go-base/resume.md`) step 1 has nothing to match.
  **Liveness check first.** Starting a batch's implementer (dispatching, setting `state: running`, recording `start_sha`/`implementer_session`) does not call `_status.append_phase`, so an interruption right after dispatching the next batch can leave `phase:` on-disk still reading `approved-{batch_name}` even though the next batch is genuinely mid-implementation. Before applying the assumption above, call `_status.read_batches(status_path)` and check whether any entry's `state` is `running`, `reviewing`, or `fixing`. If one is found, route to `## Resume` (`plugins/mill/skills/mill-go-base/resume.md`) instead — its step 1 will correctly locate and resume that batch.
  Only when no entry is non-terminal does the following apply, unchanged:
  Route instead to `## Execute — sequential loop`, continuing from the next `pending` batch in `order` — the same continuation the normal in-flow path already takes after a batch approves.
  **Edge case:** if the just-approved batch was the last one in `order` (zero `pending` batches remain), route to `## Holistic code review` (`plugins/mill/skills/mill-go-base/holistic-review.md`) instead, mirroring the normal in-flow transition from the end of the Execute loop into that section.
- `holistic-reviewing` — fires *after all* batches are `approved`, entirely outside the per-batch `## Batches` state machine.
  Route directly to `## Holistic code review` (`plugins/mill/skills/mill-go-base/holistic-review.md`);
  its own step 1 crash-recovery scan already handles resuming a specific round.
  Do not route through `## Resume` (`plugins/mill/skills/mill-go-base/resume.md`) at all.
- `self-resolved-verify-logic` — this literal phase string is appended at two call sites with identical text: the per-batch Stuck escalation section's verify/logic branch,
  and the verify/logic branch in `plugins/mill/skills/mill-go-base/holistic-review.md`.
  So `phase` alone cannot disambiguate which occurrence fired.
  Read `_status.read_batches(status_path)`: if any entry's `state` is `running`, `reviewing`, or `fixing`, this is the per-batch occurrence — route to `## Resume` (`plugins/mill/skills/mill-go-base/resume.md`; the self-resolve step only edits plan/batch files and records an audit-trail phase;
  it never changes `state`, so Resume's step 1 still finds the batch).
  If every entry's `state` is `approved`, this is the holistic occurrence (holistic self-resolve only happens after every batch is already approved) — route directly to `## Holistic code review` (`plugins/mill/skills/mill-go-base/holistic-review.md`), mirroring the `holistic-reviewing` row's routing.
- `holistic-approved` — fires immediately before "Proceed to Handoff", after all holistic-review/NIT-fix work is already complete.
  Route directly to `## Handoff` (`plugins/mill/skills/mill-go-base/handoff.md`) — re-entering Handoff is idempotent (flip Home.md, invoke mill-finalize, invoke mill-self-report), whereas routing to `## Resume` (`plugins/mill/skills/mill-go-base/resume.md`) would find no non-terminal batch to act on.

### Entry-gate wait for upstream mill-plan

Whenever the phase-table lookup above lands on the widened `discussed`/`discussing`/`planning`/`plan-review-r{N}`/`plan-fix-r{N}`/`discussion-fix-r{N}`/`discussion-gap-fix-r{N}` row, run this procedure instead of jumping straight to its listed action:

**The phase-table match is authoritative — do not second-guess it.**
Do not inspect `discussion.md`, `_mill/reviews/`, or any other artifact to judge whether the current phase "looks like" an abandoned or still-in-progress mill-start run, and do not conclude the operator invoked the wrong skill by mistake or present a menu of alternatives (e.g. "resume mill-start instead of waiting").
The upstream stage may well be actively progressing, or already correctly waiting, in a separate concurrent thread — that is normal multi-thread usage, not an error to flag.
Whenever `matched` is `True`, enter the wait unconditionally;
do not branch on which upstream skill "should" logically run next.

- Compute the match:
  ```python
  matched = _phase_wait.matches_wait_trigger(
      phase,
      {"discussed", "discussing", "planning"},
      [r"^plan-review-r\d+$", r"^plan-fix-r\d+$", r"^discussion-fix-r\d+$", r"^discussion-gap-fix-r\d+$"],
  )
  ```
- Read `entry_wait = (cfg.get("pipeline") or {}).get("entry_wait", True)`.
- **If `matched` is `True` and `entry_wait` is `True`:**
  - Read `timeout_minutes = (cfg.get("pipeline") or {}).get("entry_wait_timeout_minutes", 240)` and compute `giveup_s = timeout_minutes * 60`.
  - Build the command: `cmd = _phase_wait.build_wait_command(status_path, "planned", 10, giveup_s)`.
  - State one sentence to the user: waiting for the upstream mill-plan run to reach `phase: planned`.
  - Call the `Monitor` tool with `command=cmd`, `persistent: true`, `description` naming the slug and the target phase (e.g. "waiting for phase: planned (mill-plan handoff) for `<slug>`").
    Do not set a `timeout_ms` value distinct from the default — `persistent: true` makes it irrelevant, matching the existing "Waiting is never a decision point" convention already documented for Agent-mode dispatch elsewhere in this file: state what is being waited for, then wait, with no `AskUserQuestion` or free-text prompt in between.
  - **Record the `task_id` the `Monitor` tool call returns** in a local Builder variable and retain it for the duration of this wait (mirrors the existing "record the `agentId`" step in "## Agent-mode dispatch" above).
  - Wait for the `<task-notification>`.
    A `Monitor` run of this poll script delivers exactly one per-line event notification (the single `READY` / `TIMEOUT after ...` line the script echoes before exiting, carried in that notification's `<event>` tag), immediately followed by a second, separate terminal notification (`<status>completed</status>`, no `<event>` tag) once the script's process actually exits — this two-notification shape (confirmed by a live spike during this task's plan review, not assumed from the Agent tool's differently-shaped single-result notification) is expected and requires no special handling: act on the first notification's `<event>` content;
    the second, event-less completion notification for the same `task_id` carries no further information and needs no separate branch.
    See `plugins/mill/docs/harness-tool-contracts.md` for this contract's canonical write-up.
    Branch on the `<event>` content:
    - **`READY`** — re-run this Entry phase gate step from its top: re-read `status_path` via `_status.read_full` fresh, and re-evaluate the whole phase table again from scratch (do not assume `planned` is now the phase and jump straight to Prepare;
      a fresh read could in principle still show something else if the upstream state changed again in the interim).
      Note that the upstream `status.md` may have passed through `phase: blocked` and back before reaching `planned` — the wait does not treat upstream `blocked` as terminal (see `_phase_wait.build_wait_command`), so this is expected and requires no special handling here either.
    - **`TIMEOUT after <N>s waiting for phase: planned`** — halt with a message stating that the configured give-up period (`pipeline.entry_wait_timeout_minutes`) elapsed without mill-plan reaching `phase: planned`,
      and that the operator should check on the upstream mill-plan session (it may be abandoned, still legitimately working past the give-up window, or never started) and re-run `/mill-go` to re-arm the wait if it is in fact still in progress.
  - **If the wait itself is stopped/interrupted at the harness level** (a `TaskStop` or equivalent operator-level cancellation of the recorded `task_id`, rather than one of the three outcomes above): treat it like any other harness-level stop elsewhere in this file — no automatic retry.
    Halt with a short message telling the operator the wait was cancelled and that re-running `/mill-go` will re-evaluate the phase (proceeding immediately if it has since become ready, or re-arming the wait if not).
- **If `matched` is `True` but `entry_wait` is `False`:** fall back to the table's original action — tell the user to finish mill-plan and halt.
  Disabling `pipeline.entry_wait` narrows only the *action* (wait vs. halt), never the phase *classification* itself: even with the switch off, a phase of `plan-review-r{N}` / `plan-fix-r{N}` still reaches this same halt message (rather than falling through to the table's generic "any other" row) — this is a deliberate, narrow improvement to the halt path's message accuracy, independent of whether waiting is enabled.
- **If `matched` is `False`:** this phase value does not match the widened set at all;
  fall through to the remaining phase-table rows unchanged (this case does not actually occur for any value in `{discussed, discussing, planning}` plus the two regexes, since those are exactly what the match set covers — stated for completeness only).

6. Read the plan overview from `overview_path`.
   Confirm `approved: true` in the frontmatter.
   Extract the Batch Index via `_plan_dag.extract_batch_index(overview_text)`, validate via `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`, then compute `order = _plan_dag.topo_order(batches)`. `signature: _plan_dag.extract_batch_index(overview_text: str) -> list[dict]` `signature: _plan_dag.validate(batches: list[dict], batch_files: list[str]) -> None` `signature: _plan_dag.topo_order(batches: list[dict]) -> list[str]`

> If mill-go is interrupted mid-run, re-run `/mill-go` — it will auto-reclaim the builder lock for the same task (stale-self-lock detection is built in).

## Prepare

On a fresh run only (no `## Batches` section in status.md):

- `_status.init_batches(status_path, order)` — seeds every batch at `state: pending`. `signature: _status.init_batches(status_path: Path, names: list[str]) -> None`
- `_status.append_phase(status_path, "implementing", _timestamp.now_utc_iso())`. `signature: _status.append_phase(status_path: Path, phase: str, timestamp: str) -> None` `signature: _timestamp.now_utc_iso() -> str`
- Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: prepare for {slug}"`.

## Execute — sequential loop

For each batch in `order`:

## Agent-mode dispatch

> See `plugins/mill/docs/harness-tool-contracts.md` for the confirmed `Agent` tool notification/return-shape contract this section is built on.

This three-step pattern applies at every dispatch point:

1. **Run prepare stage:** Invoke the CLI with `--stage prepare` and the standard arguments (see each subsection for the exact CLI invocation).
   Parse the returned JSON line to extract:
   - `brief_path`: absolute file path to the rendered brief
   - `subagent_type`: `"mill:mill-implementer"` or `"mill:mill-reviewer"`, or one of their six `-medium`/`-high`/`-max` tier-suffixed variants (e.g. `"mill:mill-reviewer-high"`) when the resolved alias's `effort` field is `"medium"`, `"high"`, or `"max"` — computed by `_agent_dispatch.resolve_subagent_type`, the single site every envelope-construction call site (implement/fix/merge-in via `emit_prepare`, and each of the three review CLIs) routes through.
   - `model`: Agent-tool tier (`"sonnet"`, `"opus"`, or `"haiku"`)

   Also extract from the envelope: `session_id` (string or null), `round` (integer), `start_sha` (string or null -- present only when the CLI emits it, e.g. fix and implementer CLIs), `effort` (string or null -- present only when the resolved spec has a non-null effort tier, e.g. `"high"`), and `output_path` (absolute path string -- present only on the three review CLIs' envelopes;
   used verbatim as `--agent-output` in step 5, never re-derived).

2. **Call Agent tool:**

   Override point A: consult your variant's `## Dispatch overrides` for this role; if it declares
   one, follow it instead of the default `Agent()` call below. The role for the current dispatch is
   the one named by the calling subsection (implementer, fixer, reviewer, or merge-in). A variant
   whose `## Dispatch overrides` section contains only `(none)` declares no override for any role,
   and the default `Agent()` call below applies unchanged.

   Invoke the Agent tool with:
   - `subagent_type`: the value from step 1
   - `model`: the value from step 1
   - `prompt`: `"Read this file and follow the instructions exactly: <brief_path>"`

   The Agent tool launches a **background** subagent and returns immediately with a message such as "Async agent launched..." — the subagent's final output is NOT available at call time.
   **Record the `agentId` the Agent tool returns in that launch message and retain it for the duration of this batch** (a local Builder variable, e.g. `agent_id`).
   Also **record the `model` value actually passed to this Agent tool call into a local Builder variable** — ordinarily identical to the envelope's `model` field from step 1, copied through unchanged;
   it only differs when the operator explicitly instructs a different tier for this specific dispatch.
   This recorded value is consumed by a later batch's step-6 edit.
   The Agent tool call still takes only `subagent_type`, `model`, `prompt`, and optionally `isolation` — there is no separate `effort` parameter — but the envelope's `subagent_type` value (from step 1) already encodes the resolved alias's `effort` tier as a suffix, resolved once by `_agent_dispatch.resolve_subagent_type` at envelope-construction time.
   Forwarding an effort tier means dispatching to one of the six per-tier agent-definition files under `plugins/mill/agents/` (`mill-reviewer-medium.md`/`-high.md`/`-max.md`, `mill-implementer-medium.md`/`-high.md`/`-max.md`), each of which pins a fixed `effort:` in its own frontmatter — not passing effort as a call parameter. `effort` remains present in the envelope for audit visibility, in addition to now driving `subagent_type`.
   This `agentId` is the harness runtime handle for the live subagent — it is what `SendMessage` addresses to warm-resume the same session (see the `incomplete` recovery in step 5).
   It is **distinct from** the brief `session_id` / `implementer_session` recorded in status.md: those identify the LLM conversation for finalize and cleanup, not the harness worker.
   Today's text treats dispatch as fire-and-forget;
   the `incomplete` recovery below depends on this handle still being in scope.

   **Reviewer-dispatch-only: record a wall-clock start stamp.**
   This applies to reviewer dispatches only — implementer, fixer, and merge-in dispatches record
   nothing here, since reviewer cost visibility is this feature's whole scope.
   Immediately before this `Agent()` call, run `date +%s` in the Bash tool and hold the value in a
   local variable, e.g. `review_start_epoch`.
   Once the terminal `<task-notification>` for this `agentId` is accepted (see step 4 below), run
   `date +%s` again and hold the difference as `review_elapsed_s = <second reading> - review_start_epoch`.

   The orchestrator must then **wait for the completion `<task-notification>`** from that background agent.
   For an **implementer, fixer, or merge-in** dispatch, read the subagent's final message from the notification payload — that text feeds both step 3's classification and step 4's capture, unchanged.
   For a **reviewer** dispatch, step 4 is skipped (the reviewer already wrote its own output file — see step 4 below), so the payload feeds **step 3's classification only**.

   A background agent is a **detached worker** that can be stopped or interrupted independently of the orchestrator.
   If the `<task-notification>` indicates the subagent was stopped or interrupted (rather than completing normally), route it through step 3's recovery paths below — implementer, reviewer, and fixer notifications are all checked with a one-shot liveness probe before being treated as terminal (for implementer, the probe gates only the stopped/interrupted trigger;
   a clean turn-exhaustion stop still routes straight to Clean mid-work stop, unprobed — see step 3(b)).

3. **Recover from raw API errors and interruptions:** Classify the notification (or the inline tool return on immediate failure) into one of three cases:

   **(a) Raw API/infrastructure errors — key on the error marker alone.**
   If the notification message contains a raw API/infrastructure error marker (text like `API Error` / `Internal server error`), classify it as `stuck_type: transient` and re-dispatch once immediately using a fresh brief and session (no `--resume`).
   Key on that marker **alone** — the old heuristic's other negative signals ("roughly 0 tokens, no `MILL_REVIEW` block and no `status` JSON") no longer discriminate anything: under the reviewer-skipped-capture contract (step 4 below), a **successful** reviewer payload is now *also* exactly ~0 tokens with no `MILL_REVIEW` block, since the reviewer's chat reply is just a one-line ack.
   This applies to implementer, reviewer, and fixer Agent dispatches.
   On a second consecutive raw API error: implementer, fixer, and reviewer dispatches all escalate per the "Stuck escalation" section.
   There is no live agent to probe in this case, so it is unaffected by the liveness probe in (c) below.

   **Reviewer duration summation on re-dispatch.**
   For a **reviewer** dispatch specifically, a transient re-dispatch under this branch keeps the
   earlier attempt's `review_elapsed_s` and adds the fresh dispatch's own `review_elapsed_s` to it —
   the round genuinely cost both attempts, so the value passed at step 6 is the sum, never just the
   latest attempt's reading.

   **Deliberately no ack predicate.**
   This classification does not branch on whether a clean reviewer payload happens to be a `WROTE <path>` ack versus some other short text — do not add a prefix-match branch for it.
   Ack and non-ack clean payloads both fall through to `finalize` (step 5), which distinguishes success from a missing report by the **presence of the `.out.md` file** — a stronger signal than parsing chat text, and one the orchestrator gets for free from the finalize CLI.
   The ack exists so a human reading the transcript can confirm the reviewer finished;
   it must not become a branch condition here.

   **(b) Notification for an implementer dispatch — split by trigger.**
   Two distinct triggers both land on an implementer dispatch that didn't cleanly report success,
   and they are no longer handled identically:
   - **Clean turn-exhaustion** (the notification is a non-error, non-JSON message — the payload contains neither an `API Error` / `Internal server error` marker nor a valid `status` JSON block — AND carries no non-clean-terminal `<status>` signal: the implementer voluntarily ran out of turn budget before emitting the required JSON report) — **unchanged**, routes straight to Clean mid-work stop below, never through the liveness probe in (c).
     The redundancy rationale still holds here: `--stage finalize`'s own completeness recount disambiguates partial-vs-dead by inspecting the actual commit count against the batch's card count, which is conclusive when the implementer had a full turn to make commits before stopping.
   - **Non-clean terminal notification** (the `<task-notification>`'s `<status>` tag is present and its value is not `completed` — observed values include `completed`, `failed`; a stall/watchdog kill surfaces as `<status>failed</status>` with the stall reason in `<summary>` — AND the message does not contain (a)'s literal API-error marker text) — **NEW liveness probe**, mirroring (c) exactly: before invoking `--stage finalize`, call `TaskOutput(task_id: <agentId>, block: false)` using the `agentId` retained per step 2.
     If it reports the agent is still running: take no action this turn — no finalize call, no escalation — and wait for the agent's own next `<task-notification>` for the same `agentId`, exactly as (c) already does for reviewer/fixer.
     If it reports the agent is no longer running,
     or the probe call itself errors: proceed to Clean mid-work stop below exactly as documented.
     This closes a gap the recount alone cannot: a stopped/interrupted notification that arrives with zero commits made gives finalize no commit evidence to recount against, so it cannot tell "genuinely dead" from "still working, will finish and report later" — the same staleness problem `#587`/`#595` already solved for reviewer/fixer, now closed for implementer too (#610).

   **Clean mid-work stop (implementer only):** Reached either directly (clean turn-exhaustion, per (b) above) or after (b)'s stopped/interrupted probe branch determines the agent is no longer running.
   Do NOT re-dispatch fresh immediately.
   Instead, write the notification to the `.out.md` file as normal and invoke the `--stage finalize` step (step 5).
   Finalize inspects the commit count against the batch's card count and returns one of:
   - **`status: success`** (all cards committed and the tree is clean) — when the finalize envelope's `inferred` field is `true`, call `_status.append_inferred_success_log(status_path, batch_name, round, timestamp)` (`signature: _status.append_inferred_success_log(status_path: Path, batch_name: str, round: int, timestamp: str) -> None`) and commit the resulting `status.md` change on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: log inferred-success for {batch_name}"`) before proceeding — when `inferred` is absent or `false` (the implementer reported the JSON line normally), this call is skipped entirely and the existing success path is otherwise unchanged — proceed normally to step 6.
   - **`stuck_type: incomplete`** (some-but-not-all cards committed — the partial clean stop) — route to the **`incomplete` recovery defined in step 5 below** (warm-`SendMessage` first, then the `--resume-incomplete` fallback).
     Do **NOT** route this to the Stuck escalation transient `commits_made > 0` skip-to-cleanliness path: that path accepts the partial batch as done and is exactly the #574 false-success bug.
     The whole point of the `incomplete` classification (see Shared Decision `stuck_type: incomplete is a new first-class classification`) is that the remaining cards must be finished, never accepted as complete.
   - **`stuck_type: transient`** (genuine raw-API-error or interruption surfaced through finalize, e.g. a brief-write failure) — handle exactly as today via the one-retry transient path;
     this branch is **unchanged**.
   - **`stuck_type: logic`, reason "no structured report"** (no commits were made and no JSON was found) — reached only via the clean-turn-exhaustion sub-case of (b) above, since the stopped/interrupted sub-case already confirmed via the probe that the agent is no longer running before ever reaching this point — route to *Stuck escalation*, which self-resolves once before escalating, exactly as any other `stuck_type: logic` result.

   A clean turn-exhaustion stop after Batch 1 lands on the `incomplete` branch, not the transient branch — finalize now reclassifies a partial-batch verify failure or no-JSON inference as `incomplete` rather than `transient`.

   **(c) Non-clean terminal notification for a reviewer or fixer dispatch — NEW liveness probe.**
   The widened trigger: the `<task-notification>`'s `<status>` tag is present and its value is not `completed` (observed values include `completed`, `failed`; a stall/watchdog kill surfaces as `<status>failed</status>` with the stall reason in `<summary>`), AND the message does not contain (a)'s literal API-error marker text.
   Before classifying as `stuck_type: transient`, call `TaskOutput(task_id: <agentId>, block: false)` using the `agentId` retained per step 2 ("Record the `agentId` the Agent tool returns in that launch message and retain it for the duration of this batch").
   For the **reviewer sub-case only** (not fixer): before calling `TaskOutput`, first check whether `output_path` (the absolute path read verbatim from step 1's prepare envelope, per step 5's existing convention "For the three review CLIs, `<path>` is the `output_path` field read verbatim from step 1's prepare envelope") already exists on disk via a `test -f <output_path>` shell check.
   If the file exists: treat the reviewer as no-longer-running and proceed straight to the existing "no longer running" branch below (skip the `TaskOutput` call entirely for this occurrence).
   If the file does not exist: the result is ambiguous (still-running or dead-before-writing) — fall back to `TaskOutput` exactly as today, unchanged.
   This `test -f` pre-check applies to the reviewer sub-case of (c) only;
   the fixer sub-case of (c), and the implementer's mirrored probe in (b) above, continue using `TaskOutput` unchanged — fixer and implementer have no autonomously-written deliverable file available before their terminal notification arrives (per the `cheap-liveness-check-reviewer-only (#784)` Decision), so no equivalent check exists for them.
   Branch on the result:
   - **If it reports the agent is still running:** take no dispatch action this turn.
     Do not re-dispatch, do not classify as `stuck_type: transient`.
     The harness will deliver the agent's own next `<task-notification>` for the same `agentId` when it actually finishes (matches the observed `#595` behavior — the "killed" agent later delivered a real `completed` notification unprompted).
     This wait is unbounded by design, matching every other Agent-mode dispatch's existing "no log-polling or liveness check required" contract (see "Agent-mode properties" below) — no bounded re-check loop is added for this probe.
     For a **reviewer** dispatch: this is one continuous `Agent()` call and one continuous measurement — do NOT restart or reset `review_start_epoch`;
     there is nothing to sum yet.
   - **If it reports the agent is no longer running,
     or the probe call itself errors** (the task_id is already gone): proceed to the existing one-retry transient classification from (a) and re-dispatch exactly as today, including the same second-consecutive-failure escalation rule.
     For a **reviewer** dispatch, this includes the reviewer-only `test -f <output_path>` shortcut's file-exists outcome above — that outcome, too, routes into (a)'s re-dispatch and therefore sums `review_elapsed_s` across attempts exactly like (a), never resets it.

   This probe exists because both `#587` and `#595` were live incidents where a "killed"/"stopped by user" notification was stale for an agent that was, in fact, still running to completion — see `_mill/discussion.md`'s `stopped/interrupted-notification liveness probe (#587, #595)` Decision for the full incident writeups and rationale.

4. **Capture output — reviewer-skipped.**
   For an **implementer, fixer, or merge-in** dispatch, write **the message captured from the `<task-notification>`** to `<brief_path>.out.md` (utf-8), unchanged.
   The response file extends the brief path by replacing the trailing `.md` with `.out.md` — for a brief `foo-r1.md` the response is `foo-r1.out.md`.
   For a **reviewer** dispatch, skip this step entirely — the reviewer holds its own `Write` grant and already wrote `.out.md` itself;
   the orchestrator does not write it a second time.
   The old behaviour made the orchestrator read the reviewer's entire final message and write that whole thing back out to disk, so a full findings dump landed in the Builder's context twice — once in the notification payload it had to read to classify the round, and again in the file it wrote — even though "Builder reads only the JSON envelope verdict, never the findings" (see step 3 of "Code Review loop") and "Implementer owns receive-review" (see Principles) already forbid the Builder from acting on those findings.

5. **Run finalize stage:** Invoke the CLI with `--stage finalize`, the same standard arguments, and `--agent-output <path>`.
   For the three **review** CLIs, `<path>` is the `output_path` field read verbatim from step 1's prepare envelope — do not re-derive it by string-replacing the brief path's trailing `.md` with `.out.md`;
   the envelope already names the exact file the reviewer wrote.
   For **implementer, fixer, and merge-in** CLIs, whose prepare envelopes carry no `output_path` field, keep deriving `<path>` as `<brief_path>.out.md` (the trailing `.md` replaced by `.out.md`), as before.
   Parse the returned JSON envelope.

   Additionally thread any applicable prepare-envelope fields into the finalize call: for fix and implementer CLIs, pass `--session-id <session_id>` and `--start-sha <start_sha>` (when `start_sha` is not null in the envelope);
   for `millpy-fix.py` finalize calls specifically, additionally pass `--nits-only` when the prepare envelope's `nits_only` field is `true` (the field is present only when the prepare-stage call itself included `--nits-only`;
   a finalize call must NOT pass `--nits-only` when the envelope omits the field or has it `false`, since only a genuine NIT-only fix pass should skip the no-content-commit gate and receive the `nits-fixed-<scope>` marker);
   for review CLIs, pass `--round <round>`.

   For the three **review** CLIs specifically, additionally pass `--actual-model <value>` using the model value the `effort-tier-review-cli` batch's step-3 `mill-go-base/SKILL.md` edit recorded as actually passed to this round's Agent tool call — this keeps the finalized review file's `reviewer_model` field accurate even when the Builder dispatched a different tier than the prepare envelope's `model` field named (a manual override) or the prepare-stage's own large-prompt auto-switch already changed it before the envelope was read.
   Implement/fix/merge-in CLIs' finalize calls do not take this flag (no `reviewer_model`-equivalent field exists on their side, per this task's earlier confirmed-absent decision).

   **Agent-mode duration forwarding — review CLIs only.**
   Under agent-mode dispatch (`dispatch == agent`), for the three **review** CLIs only, additionally
   pass `--duration-s <review_elapsed_s>` on this `--stage finalize` invocation, alongside the
   existing `--agent-output`, using the value recorded/summed per step 3 and step 4 above.
   Never pass `--tool-calls` or `--cost-usd` under agent-mode — the Agent tool notification contract
   carries no such signal, so those cells are legitimately `n/a` in the finalized review file and the
   JSON envelope.
   Implementer, fixer, and merge-in finalize invocations are unchanged — they take no
   `--duration-s`/`--tool-calls`/`--cost-usd` flags at all.

   For `millpy-fix.py` specifically, "the same standard arguments" means re-passing `--scope`, `--batch-name` (batch scope only), and `--review-file <path>` exactly as given to the prepare-stage call — `millpy-fix.py` requires `--review-file` unconditionally at every `--stage`, not just `prepare` (its argparse validates `args.review_file is None` before branching on `--stage`), so a `--stage finalize` call that omits it fails argument parsing before finalize logic ever runs.
   Give any `--stage finalize` call an extended Bash-tool timeout — recommend 600000ms (10 minutes) — whenever that CLI's finalize stage replays a batch's `verify:` command as a regression guard: this currently applies to both `millpy-fix.py --stage finalize` and `millpy-implement.py --stage finalize`, each of which replays every batch's `verify:` command sequentially, which can exceed the default 2-minute Bash tool timeout on plans with several slow verify suites.
   This timeout note is scoped to finalize calls for CLIs whose finalize stage replays verify — fix-CLI (both `--nits-only` and full fix, both batch and holistic scope) and implementer-CLI;
   review-CLI finalize calls don't run verify commands and aren't affected.

5.5. **`incomplete` recovery (implementer only — agent mode):** When the finalize envelope from step 5 has `stuck_type: incomplete`, the batch is provably partial: some cards were committed but not all.
Recover the existing session rather than retrying from scratch (Shared Decision `resume must preserve the original start_sha`;
discussion `warm-resume-mechanism`, `start-sha-preserving-resume`):

   1. **Warm `SendMessage` resume (preferred).**
      If the `agentId` recorded in step 2 is still retained, the original subagent session is still addressable.
      Send it back to work in the same warm session:
      ```
      SendMessage(to: <agentId>, "Finish any remaining cards in this batch, run verify, then emit the required JSON report as your final line.")
      ```
      Wait for the resulting `<task-notification>`, write its message to `<brief_path>.out.md` (overwriting the prior capture, per step 4's naming rule), and re-run `--stage finalize` (step 5) with the same standard arguments.
      The warm-`SendMessage` path **bypasses prepare entirely**, so status.md's original `start_sha` and `implementer_session` are untouched — finalize's completeness recount runs from the original baseline and counts every content commit (the partial ones plus any new ones).
      Re-capturing `start_sha` here would under-count a now-finished batch and loop `incomplete` forever.
   2. **`--resume-incomplete` fallback (cold re-dispatch).**
      Fall back to this path when **any** of the following holds: no `agentId` was retained;
      the `SendMessage` call errors because the agent already terminated (the stop arrived as `status: completed`, so the harness worker is gone);
      or the warm-resumed agent again stops without emitting JSON.
      Re-dispatch the implementer once via the `--resume-incomplete` path — run the prepare stage as `--stage prepare <batch_name> --resume-incomplete`, then the Agent tool, then `--stage finalize` as usual. `--resume-incomplete` reads the original `start_sha` and `implementer_session` from status.md instead of re-capturing HEAD, skips the cleanliness snapshot and the `mill-go: start batch` housekeeping commit, and so **preserves the original `start_sha`** — never a fresh one.
      Record the new `agentId` this re-dispatch returns, in case a further resume is needed.
   3. **After recovery.**
      Re-parse the finalize envelope and branch in step 6.
      A `status: success` (or inferred success) means the batch finished — when the re-parsed envelope's `inferred` field is `true`, call `_status.append_inferred_success_log(status_path, batch_name, round, timestamp)` and commit the resulting `status.md` change on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: log inferred-success for {batch_name} (post-recovery)"`), before proceeding normally.
      This is a structurally separate check from the step 3(b) Clean mid-work stop call site — finalize's envelope after an `incomplete` recovery is examined here independently, so an implementer that goes `incomplete` on its first turn and then completes cleanly without emitting JSON on the resumed turn is caught only by this call site, not the other one.
      When `inferred` is absent or `false`, skip this call entirely.
      If the envelope is **still** `stuck_type: incomplete` after one warm resume and one `--resume-incomplete` fallback, hand it to the `### Stuck escalation` `incomplete` branch (it does not silently loop).

6. **Branch on verdict:** The envelope's `status`, `verdict`, and `stuck_type` fields are what the caller branches on.
   The agent-mode `incomplete` recovery (step 5.5) is the one addition: an `incomplete` envelope routes through the warm-`SendMessage` / `--resume-incomplete` recovery before any escalation.

**Agent-mode properties:**
- No log-polling or liveness check required: the orchestrator waits for the `<task-notification>` from the background agent instead of polling a log file.
- A background agent IS a detached worker and CAN be stopped or interrupted.
  ('Stopped/interrupted' here is one example of the broader non-clean-terminal `<status>` trigger step 3(b)/(c) now test for — see step 3 above.)
  A stopped/interrupted agent produces a notification indicating it did not complete normally — handle that per step 3's recovery paths below (implementer: liveness-probe-then-clean-mid-work-stop/`incomplete` routing per step 3(b);
  reviewer/fixer: liveness-probe-then-one-retry-transient path per step 3(c)).
- `transient` stuck errors can still be emitted by `finalize` as synthetic JSON (e.g., if the brief write fails).
- The one-retry transient policy applies immediately to raw API errors, and to stopped/interrupted reviewer/fixer agents once step 3's liveness probe confirms the agent is no longer running (see step 3).
  Stopped/interrupted implementer agents are first checked by the same liveness probe (step 3(b));
  once it confirms the agent is no longer running, they are routed to the existing clean-mid-work-stop / `incomplete` recovery (see step 3).
- `incomplete` stuck errors emitted by `finalize` are recovered in-session via the step 5.5 warm-`SendMessage` / `--resume-incomplete` path, NOT the transient retry-fresh path — they preserve the original `start_sha` so a finished batch is never re-counted as partial.
- Waiting on a dispatch — either branch — is never a decision point: state in one sentence what you're waiting for, then wait. `AskUserQuestion` (or any equivalent free-text operator prompt) is banned here unconditionally — every stuck/escalation path in this file now resolves by self-resolving once then halting via `_status.set_blocked`, never by prompting.

**Tree-guard checkpoint block.** Referenced by name from every dispatch call site in this file and from the skill's companion files, which name it as `**Tree-guard checkpoint block**` in `plugins/mill/skills/mill-go-base/SKILL.md`. Exactly two forms, both sharing the same body:
- **Pre-dispatch form** — invoked immediately before a dispatch.
- **Post-dispatch form** — invoked once per dispatch, immediately after that dispatch's prepare-through-finalize sequence returns. The ERROR-only-aggregate retries at `### 3. Code Review loop` sub-step 4.5 and `plugins/mill/skills/mill-go-base/holistic-review.md` sub-step 3.5 are separate dispatch points, each with its own pre/post pair — not sub-cycles of the dispatch that preceded them.

Body (both forms): `result = _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)`; `if result["triggered"]: _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])`.
`signature: _treeguard.check_and_restore(worktree: Path, tracked_root: str = "_mill", *, git_root: Path | None = None) -> dict` returning `{"triggered": bool, "restored_paths": list[str], "timestamp": str | None}`.
`signature: _status.append_recovery_log(status_path: Path, timestamp: str, restored_paths: list[str]) -> None`.

The post-dispatch form brackets the out-of-process execution window that `worktree_snapshot_guard` cannot see, and the block must not be invoked from inside the Agent-mode dispatch pattern's own numbered steps — it belongs at each call site, since that pattern also serves non-review dispatch.

**Why not fork?**
Every dispatch above uses a fresh `Agent(subagent_type: ...)` call, never `Agent(subagent_type: "fork")`.
A fork inherits the parent's context,
but that inheritance costs three things every role above depends on: (1) a fork always runs on the **parent's model** and ignores a `model` override, breaking mill's per-role model assignment — implementer-class roles carry a literal `model:` key (`roles.implementer.model: sonnethigh`, `roles.fixer.model: haiku`, and merge-in's `model: haiku`, all in `plugins/mill/templates/mill-config.yaml`), while reviewer roles instead name a *reviewer* from `agents.yaml` (e.g. `roles.discussion-review.holistic.reviewer: sonnetmax` in the shipped template) whose model is resolved from that registry and mapped to an Agent tier by `_agent_dispatch.model_to_tier` — fork breaks both mechanisms, since it ignores the `model` argument either way;
(2) a fork inherits the **parent's tools**, so a reviewer forked from mill-go would hold `Edit`, `Write`, and `Bash` beyond its briefs-scoped grant and lose its read-only guarantee;
(3) a fork's **crash-resume path is unverified** — `millpy-implement.py --stage prepare` writes the brief to disk via `_agent_dispatch.write_brief` regardless of dispatch shape, and `--resume-incomplete` re-runs prepare, so the brief is present either way, but nothing has confirmed that a fork returns the `agentId` and completion-notification shapes step 3's liveness probe and step 5.5's warm resume depend on.
mill-go2 accepts these trade-offs for the implementer role only, as an experiment — see its `## Dispatch overrides`;
every other role, and every mill-go dispatch, keeps the fresh-`Agent` default.
Fork is otherwise used only at three sites: mill-start's Explore phase (see `mill-start/SKILL.md`), mill-plan's Phase: Plan research dispatch (see `mill-plan/SKILL.md`'s "Fork scope guardrail"), and, experimentally, mill-go2's implementer override.
Fork's advertised "the child's tool output stays out of the parent" is **not** a differentiator here either — an ordinary fresh Agent call already keeps a subagent's tool output out of the parent's context.

## Review cost line

This section is the single source of truth for the post-round cost print in every orchestrator.
mill-start and mill-plan reference this section rather than restating it.

**When to print.**
Once, immediately after each review round's JSON envelope is in hand, under agent-mode dispatch,
before branching on the verdict.
Print it for `ERROR` rounds too — an expensive failed round is exactly what the operator most needs
to see.

**Format.**

```
[review] <type> r<N> (<scope>): <verdict>, <model>, <duration>, <tool_calls> tool-calls
```

with `, $<cost_usd>` appended only when `cost_usd` is non-null.
Render a null `duration_s`, `tool_calls`, or `model` as the literal `n/a`.
Render duration as `<n>s` when under a minute, and `<m>m<ss>s` otherwise.
ASCII only.

**Where each field comes from.**
`type`, `round`, and `verdict` come from the round's JSON envelope directly.
`duration_s`, `tool_calls`, and `cost_usd` come from that envelope's `reviews[...]` entry matching
this scope.
`model` comes from the prepare envelope's `model` field under agent-mode (or the recorded
actually-dispatched tier when the operator overrode it — see "## Agent-mode dispatch" step 3's
"record the `model` value actually passed" instruction).

**Not persisted.**
This line is orchestrator chat output only — it is never written to a file.
The persisted copy of the same numbers lives in the review file's yaml header, readable later via
`/mill-review-summary`.

### 0. Wiki health-check

Before launching the implementer / reviewer for this batch, verify a config source is reachable.
If the check fails, release the builder lock and halt — a config source became unavailable mid-run and the implementer's downstream error would mask the root cause.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
import _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
if not _client.health_check(wiki_path):
    print('[<VARIANT_LABEL>] wiki daemon health check failed', file=sys.stderr)
    raise SystemExit(1)
" || {
    PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
    echo "[<VARIANT_LABEL>] HALT: wiki daemon unreachable or unhealthy -- see the reason printed above; re-run mill-setup only if mill-config.yaml is confirmed missing" >&2
    exit 1
}
```

### 0.55. Done-gate baseline pre-flight (first batch of the task only)

Immediately after "0.
Wiki health-check" and before "0.5.
Baseline pre-flight," for the task's **FIRST batch only** (not on every batch — only once per task run, same guard shape as "0.5.
Baseline pre-flight" below), read `(cfg.get("pipeline") or {}).get("done_gate_baseline_preflight", False)` and `(cfg.get("pipeline") or {}).get("done_gate")`.
If the preflight flag is falsy OR `done_gate` is `None`/absent, skip this step entirely — log nothing, proceed straight to "0.5.
Baseline pre-flight."
Otherwise, invoke `_done_gate.run_preflight` from `git_root` (not hub dir — identical cwd to the "0.
Pre-done gate" block in `plugins/mill/skills/mill-go-base/handoff.md`):

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json
import _paths, _config, _done_gate
git_root = _paths.resolve_git_root()
hub_root = _paths.resolve_hub_path()
cfg = _config.load_config(hub_root, git_root)
pipeline_cfg = cfg.get('pipeline') or {}
if not pipeline_cfg.get('done_gate_baseline_preflight', False):
    raise SystemExit(0)
gate_cmd = pipeline_cfg.get('done_gate')
if not gate_cmd:
    raise SystemExit(0)
result = _done_gate.run_preflight(gate_cmd, git_root)
print(json.dumps(result))
"
```

Give this Bash-tool call the same extended 600000ms (10-minute) timeout recommended for finalize-stage verify replays above: `run_preflight` invokes the configured `done_gate` command, which is an arbitrary, potentially slow project command (e.g. a full regression suite) with no bound on runtime, sharing the identical default-2-minute-Bash-timeout risk that motivated the original finalize-stage-CLI fix.

Parse stdout for a JSON line (absent when the flag/`done_gate` check above short-circuited via `SystemExit(0)` -- that is the normal skip path, not an error).
If the JSON line's `result` is `blocked`, log the reason (ASCII-only) but do **NOT** halt — proceed to batch 1 regardless.
This differs deliberately from the "0.
Pre-done gate" gate in `plugins/mill/skills/mill-go-base/handoff.md`, which DOES halt on a `blocked` result: at this point in the flow a failing `done_gate` reflects the *parent* branch's own pre-implementation state, which is diagnostic information this task's batches cannot fix, and blocking Prepare on it would make an otherwise-startable task undispatchable.
This pre-flight's only job is to get a self-capturing regression/snapshot suite's baseline captured from the right (pre-implementation) commit before any batch touches the tree — it fulfills that job even when `run_preflight` itself reports `blocked` (a captured "blocked" baseline is still a validly-timed baseline for the comparison made at Handoff time).
The "0.
Pre-done gate" block in `plugins/mill/skills/mill-go-base/handoff.md` is unchanged and still halts on `blocked` there.
Skip this step entirely for every batch after the first.

### 0.5. Baseline pre-flight (first batch of the task only)

Immediately before "### 1.
Implement" fires for the task's **FIRST batch only** (not on every batch — only once per task run), invoke the task-scoped module-wide verify baseline computation:

> **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
    --slug baseline-preflight -- \
    "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" --stage baseline
```

This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until the line `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
```

Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed; `"dead"` -> log the reason (ASCII-only) and continue to batch 1 anyway — do NOT halt here, matching this section's own "never blocks the task" principle stated below (a failed/skipped computation just means the per-batch module-wide gate falls back to strict behavior, which is safe). Once `[mill-bg] EXIT` appears, run `grep '^{' <log-path>` to extract the two JSON summary lines.

(no `batch_name` positional argument — `--stage baseline` is task-scoped, not batch-scoped.) Parse the two JSON lines extracted above — one per substage. The first line covers the `module_wide` substage and is identical in shape to today's single-line contract, just tagged with `"substage": "module_wide"` (parse and log exactly as today: `{"stage": "baseline", "substage": "module_wide", "result": "computed"|"cached"|"error"|"skipped", "value": ...}`). This call is **idempotent and safe to invoke unconditionally even on a resumed/restarted mill-go run**: the `--stage baseline` handler itself checks whether `module_verify_baseline` is already cached in status.md and no-ops (`{"stage": "baseline", "substage": "module_wide", "result": "cached", "value": ...}`) if so. On `{"result": "error", ...}` or `{"result": "skipped", ...}` (no module-wide verify configured for this task), log the reason and continue to batch 1 anyway — this pre-flight step never blocks the task; its only job is to populate the cache before batch 1's implementer can touch dependency manifests. A failed/skipped computation just means the per-batch module-wide gate falls back to strict behavior, which is safe.

The second line covers the `per_batch` substage: `{"stage": "baseline", "substage": "per_batch", "computed": [<batch names computed this call>], "cached": [<batch names already had a baseline>], "errored": {<batch name>: <reason>, ...}}`.
Log a one-line summary of the `computed`/`cached`/`errored` counts and continue to batch 1 regardless of any `errored` entries — this substage never blocks the task either, matching the `module_wide` substage's own never-block behavior.
An errored batch just means that batch's own per-batch verify gate falls back to strict (any-failure-blocks) behavior at its own finalize time, which is safe.

Why this must run before batch 1 specifically, eagerly and once: per `_mill/discussion.md`'s `baseline-aware module-wide verify gate (#590)` Decision ("Compute it **eagerly, once, before the task's first batch implementer is ever dispatched**"), this ordering guarantees no implementer session has touched dependency manifests yet, so the transient worktree's reused dependency state is still guaranteed to match the parent branch tip.
Skip this step entirely for every batch after the first.

This background-dispatch-and-poll pattern removes the Bash-tool timeout ceiling entirely, instead of relying on a capped foreground call: `--stage baseline`'s `per_batch` substage replays every batch's `verify:` command to seed `verify_baseline_failures`, an arbitrary, potentially slow project command with no bound on runtime, and a capped foreground Bash-tool call -- even at the 600000ms (10-minute) ceiling previously recommended here -- has twice been observed to time out on tasks with several slow batch verify commands (#897, #875).

### 0.6. Per-batch baseline recapture (self-hosting only)

This is a shared check-and-invoke block, referenced (not duplicated) from the single insertion point in "### 1.
Implement" below — immediately before step 5 (`--stage finalize`) of the Agent-mode dispatch pattern.
It exists only to backfill a still-missing per-batch `verify_baseline_failures` baseline for a self-hosting task's own plan, using the task worktree's own copy of `millpy-implement.py` rather than the frozen `${CLAUDE_PLUGIN_ROOT}` cache — the cache is provably a no-op for this purpose since it never reflects this task's own in-progress commits.

**Session-scoped cadence flag.**
Before "## Execute — sequential loop" begins, initialize a local Builder variable `baseline_recapture_attempted = False`.
This variable is never persisted to status.md or any file — it resets to `False` whenever a mill-go session (re)starts, matching the existing in-memory-only precedent of the Agent-mode `agent_id` handle (see "## Agent-mode dispatch" step 2).

**Trigger check.**
At the hook point, run all of:
1. `baseline_recapture_attempted is False`.
2. `_paths.is_self_hosting_task(git_root)` is `True`.
3. This batch's entry in `_status.read_batches(status_path)` (matched by `name == <batch_name>`) has `verify_baseline_failures` still `None`.
4. This batch's own resolved `verify:` command is non-`None` — resolved the same way `_enumerate_batch_verify_triples` resolves it: read `overview_text = overview_path.read_text(encoding="utf-8")` (mirroring `millpy-implement.py:670-671`), look up this batch's `file` in `_plan_dag.extract_batch_index(overview_text)`, read that file's frontmatter via `_plan_dag._read_batch_frontmatter`, and pass it through `_plan_dag.parse_verify_field(frontmatter, worktree_root, git_root)` — a non-`None` first element of the returned tuple satisfies this condition.

If all four hold, proceed to Invoke below.
If any one is false, skip this step entirely — no logging needed for the skip itself (the once-per-run budget and non-self-hosting no-op are both expected, high-frequency states, not anomalies).

**Invoke.**
Set `baseline_recapture_attempted = True` immediately (before running the command below), so the attempt is consumed even if the invocation itself fails or hangs.
Then run, from the task worktree (same cwd convention as "0.5.
Baseline pre-flight" above):

> **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
    --slug baseline-recapture -- \
    env PYTHONPATH="<git_root>/plugins/mill/scripts" "$MILL_PYTHON" "<git_root>/plugins/mill/scripts/millpy-implement.py" --stage baseline
```

The `env PYTHONPATH="<git_root>/plugins/mill/scripts"` prefix on the inner command is required, not cosmetic: everything after `millpy-bg.py`'s `--` separator is executed as a literal argv list (`_worker_main` in `millpy-bg.py` calls `subprocess.run(cmd, ...)` with no shell and no `env=` override), so the pre-edit block's `PYTHONPATH="<git_root>/..." "$MILL_PYTHON" ...` shell-level env-var-prefix idiom cannot be reused verbatim inside that payload — without an explicit `env VAR=value` wrapper, the inner command would silently inherit the OUTER `millpy-bg.py` call's own `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` (cache-form) instead, defeating this section's entire purpose (importing the worktree's own in-progress sibling modules instead of the frozen cache). `env` is a plain executable that sets environment variables for a single child process without requiring a shell, so it composes correctly with `subprocess.run`'s no-shell argv-list execution.

Poll the same way "0.5. Baseline pre-flight" does above (`cat <log-path>` for `[mill-bg] EXIT`, with the same `_bg.check_bg_status` liveness-check branch, parsed as `(status, pid_or_code)`: `"running"` -> keep polling, `"exit"` -> proceed, `"dead"` -> log the reason (ASCII-only) and treat as a no-op, matching this card's own "0.6" Failure handling paragraph below), then run `grep '^{' <log-path>` to extract the two JSON summary lines.

Substitute the literal `git_root` path resolved at Path Setup for BOTH the inner `env PYTHONPATH=` value and the `millpy-implement.py` script path argument — do NOT use `${CLAUDE_PLUGIN_ROOT}` for either; this is the one deliberate, narrow exception to the cache-form convention (see the plan overview's "cache-vs-worktree execution path for the retry" Shared Decision and root `CLAUDE.md`'s "Hard constraints" / "Path invariants"). The OUTER `millpy-bg.py` wrapper call — both its own script path and its own `PYTHONPATH` — stays cache-form (`${CLAUDE_PLUGIN_ROOT}`), matching every other `millpy-bg` call site in this file family (e.g. "0.5. Baseline pre-flight" above); only the inner command that `millpy-bg.py` backgrounds gets the worktree-form exception.
Parse the two JSON lines extracted above, in the identical shape "0.5.
Baseline pre-flight" already documents (first line: `{"stage": "baseline", "substage": "module_wide", "result":
"computed"|"cached"|"error"|"skipped", "value": ...}`; second line:
`{"stage": "baseline", "substage": "per_batch", "computed": [...], "cached": [...], "errored": {...}}`), and log a one-line ASCII-only summary of the `per_batch` line's counts.

**Failure handling.**
Any failure of this invocation — non-zero exit, a `dead` liveness-check result (the worker died mid-run), malformed or missing JSON output on either line, or `--stage baseline` not yet existing in the worktree's mid-development code — is logged (ASCII-only) and treated as a no-op: proceed to this batch's normal strict-mode finalize exactly as if no recapture had been attempted.
Never escalate to `stuck`/blocked over a recapture failure.

### 1. Implement

Venv-check before per-batch invocation:

```bash
if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" ] && [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
    echo "[<VARIANT_LABEL>] venv missing -- attempting uv sync"
    uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
    if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" ] && [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
        echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
        exit 1
    fi
fi
```

Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-implement.py` and `<args> = <batch_name>`.

For this dispatch instance only, immediately before step 5 of the pattern above (`--stage finalize`) runs, execute the "### 0.6.
Per-batch baseline recapture (self-hosting only)" check.

The CLI atomically: resolves paths and config, renders the implementer brief, generates a `session_id`, sets batch state → `running`, records `start_sha` and `implementer_session` in status.md, commits and pushes on the task branch, and spawns the implementer.
The Builder reads the JSON summary from the finalize envelope.
Note: the CLI exits 0 when the implementer produced JSON (success or stuck).
On exit code 1 the JSON line in the finalize envelope still carries a `{"status":"stuck","stuck_type":"transient",...}` line if an LLM-layer failure (timeout, dead session, etc.) occurred — parse it the same way and route through Stuck escalation.
Only treat exit 1 as an unrecoverable pre-launch error when the JSON line in the finalize envelope is absent.

### 2. Parse implementer report

The implementer's last output line must be JSON:

```json
{"status":"success|stuck","commit_sha":"...","session_id":"...", ...}
```

- `status: success` → continue to Code Review.
- `status: stuck, stuck_type: transient` → auto-retry ONCE: re-invoke `millpy-implement.py <batch_name>` (no `--resume` flag — a fresh batch start).
  Record `review_round: 0`, do not change batch state.
  If the second invocation also reports `stuck_type: transient` → escalate per *Stuck escalation* below.
- `status: stuck, stuck_type: verify | logic` → route to *Stuck escalation*, which self-resolves once before escalating.
- Malformed / missing JSON line → treat as `stuck_type: logic` reason "no structured report".

### 2b. Cleanliness gate

After a `success` report: Before the dirt computation, resolve the parent branch and revert out-of-scope drift.

Inline Python (in step 2b, before compute_new_dirt):
```python
import _parent_branch, _cleanliness
parent_branch = _parent_branch.resolve(status_path, interactive=False)
reverted_paths, remaining_in_scope_lines = _cleanliness.revert_out_of_scope_drift(
    worktree_root, task_dir, parent_branch, git_root
)
in_scope_dirt = remaining_in_scope_lines
```

`signature: _parent_branch.resolve(status_path: Path, *, interactive: bool = True) -> str`
`signature: _cleanliness.revert_out_of_scope_drift(worktree: Path, task_dir: Path, parent_branch: str, git_root: Path | None = None) -> tuple[list[str], list[str] | None]`

If `in_scope_dirt is None` (the parent diff is unresolvable -- e.g. the parent branch ref no longer exists -- so `reverted_paths` is `[]` and nothing was safely revertable):
- `_status.set_batch_field(status_path, batch_name, "state", "blocked")`
- `_status.set_batch_field(status_path, batch_name, "blocked_reason", "parent diff unresolvable -- cannot determine in-scope drift")`
- `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`
- Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on <batch_name> — parent diff unresolvable"`
- Go to *Blocked*.

If `in_scope_dirt` is non-empty (and not `None`; genuine implementer-introduced dirt within task scope that did not pre-date the batch):
- `_status.set_batch_field(status_path, batch_name, "state", "blocked")`
- `_status.set_batch_field(status_path, batch_name, "blocked_reason", "uncommitted working tree after implementer report")`
- `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`
- Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on <batch_name> — dirty tree"`
- Go to *Blocked*.

If `in_scope_dirt` is empty (and not `None`), record `commit_sha` via `_status.set_batch_field(status_path, batch_name, "commit_sha", <sha from JSON report>)`.
Then continue to "3.
Code Review loop" as normal.

### 3. Code Review loop

If `roles.code-review.batch.reviewer` is null (or rounds: 0): set batch state → `approved`, `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> _mill/briefs/ && git -C <worktree> commit -m "<VARIANT_LABEL>: approve batch {batch_name} (per-batch review disabled)"`, and continue to the next batch.
Skip the rest of this section.

- Set batch state → `reviewing`, `review_round: 1`.
- `extra_files = []`.
- `min_batch_rounds = cfg.get("roles", {}).get("code-review", {}).get("batch", {}).get("min_rounds", 1)`.

**Convergence gate (min_rounds + demoted predicate).** On any round whose envelope's top-level `verdict` is `APPROVE` (step 4's `APPROVE` branch below), compute:

```
converged = (N >= min_batch_rounds) and not any(f.get("demoted") for f in envelope["findings"])
```

`envelope["findings"]` is the top-level field the JSON envelope already carries (`ReviewResult.findings`) — no backend change needed to read it. This site has no approved-batch carryforward concept, so `envelope["findings"]` is read directly, unfiltered.

- `converged is True`: proceed exactly as step 4's `APPROVE` branch describes (no behavior change).
- `converged is False` AND `N < roles.code-review.batch.rounds`: the NIT-fix dispatch (when `nit_count > 0`) still runs — real, safe work — but do NOT execute the branch's terminal actions (`_status.append_phase(status_path, f"approved-{batch_name}", ...)`, the approve-commit, the loop break). Instead continue the loop to round N+1 (re-dispatch code review for this batch).
- `converged is False` AND `N >= roles.code-review.batch.rounds` (last allowed round): treat as an implicit approval — run the branch's existing terminal actions exactly as if `converged` were `True`, but append `" (min_rounds/demoted-predicate not satisfied by round cap)"` to the approve-commit message (`"<VARIANT_LABEL>: approve batch {batch_name}"`) so the shortfall is auditable.
- Step 5 (Max-rounds exhaustion) is untouched — it only fires when verdict never reached `APPROVE` (BLOCKINGs remained the whole time), orthogonal to this gate's implicit-approve-at-cap fallback, which lives inside the `APPROVE` branch itself.

For each round `N` from 1 to `roles.code-review.batch.rounds`:

- Tree-guard checkpoint block, pre-dispatch form (see "## Agent-mode dispatch" above) — before the append_phase/commit below.
- `_status.append_phase(status_path, f"reviewing-{batch_name}-r{N}", _timestamp.now_utc_iso())`.
  Commit immediately: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: reviewing batch {batch_name} round {N}"` — mirrors the Holistic Review loop's own existing pattern at the same file (`_status.append_phase(status_path, "holistic-reviewing", ...)` immediately followed by an equivalent commit).
  This closes the window where an uncommitted phase-append could itself be the file a tree-guard restore later discards — see `_mill/discussion.md`'s "Closing the same-file modify-then-delete window in mill-go's per-batch loop" Decision.

1. **Crash-recovery check.**
   Before firing the CLI, scan `reviews_dir` for a file matching `*-code-review-{batch_name}-r{N}.md`.
   If found, validate its freshness: fetch `ref_ts = _status.phase_entry_timestamp(status_path, f"reviewing-{batch_name}-r{N}", occurrence=1)`;
   treat the file as this round's review ONLY if `ref_ts` is not None AND the file's mtime (UTC) is at or after `ref_ts`.
   If freshness validation passes, parse its verdict from the fenced yaml block via `_review_common.parse_verdict(file_content)` and skip to step 4 below.
   This covers the case where mill-go crashed after writing the review but before committing state.
   If the file is stale (mtime before `ref_ts`) or `ref_ts` is None, ignore the file and fall through to firing the CLI.

   Freshness validation in inline Python:
   ```python
   from datetime import datetime, timezone
   from pathlib import Path
   ref_ts_str = "<iso-timestamp-string>"  # result from phase_entry_timestamp
   file_path = Path("<review-file-path>")
   ref_ts = datetime.fromisoformat(ref_ts_str.strip('"')).replace(tzinfo=timezone.utc) if ref_ts_str else None
   file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
   is_fresh = ref_ts is not None and file_mtime >= ref_ts
   ```

   State explicitly: ERROR-only retries still do NOT consume the round counter;
   freshness — not counter consumption — is what rejects stale pre-retry files. `signature: _review_common.parse_verdict(text: str) -> str`
   `signature: _status.phase_entry_timestamp(status_path: Path, phase: str, *, occurrence: int = 1) -> str | None`

1.5.
**Prior-notes digest (round N > 1 only).**
If `N > 1`: scan the prior round's review file (from round `N-1`) for every line matching `### [NIT] <title>` (case-insensitive NIT marker); the heading may carry a class suffix, so `### [NIT:consistency] <title>` matches as well as `### [NIT] <title>`, and the title is the heading text after the closing bracket in either form.
A heading carrying a `**Demoted-from:** BLOCKING` line on the line below it was demoted by the stage ceiling and is a genuine NIT for the purposes of this prior-non-blocking-items list, not a suppressed BLOCKING.
Extract the title text and the next non-empty line (which should contain Location and Issue fields).
Build a digest: one line per NIT finding, in format "- Title: issue context" (ASCII-only, all non-ASCII replaced with closest ASCII), write to `<briefs_dir>/prior-nonblocking-<batch_name>-r<N>.txt`, and pass `--prior-notes <digest-path>` to the `millpy-review-code.py` invocation below.
The `reviews/` read-ban is unchanged — only the curated digest reaches the reviewer.
Round 1 passes no `--prior-notes` (digest defaults to `(none)` in the template).

2. Tree-guard checkpoint block, pre-dispatch form (see "## Agent-mode dispatch" above) — immediately before the Agent-mode dispatch below.

   Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = --batch <batch_name> [--extra-file <p> ...] [--prior-notes <digest-path>]`.
   The CLI prints one JSON line `{"type":"code","round":N,"verdict":"...","reviews":[...]}`.

Tree-guard checkpoint block, post-dispatch form (see "## Agent-mode dispatch" above) — immediately after the Agent-mode dispatch pattern above returns (prepare through finalize).

3. **Builder reads only the JSON envelope verdict, never the findings.**
   Loading `mill-receiving-review` is the dispatched implementer's job (see Principles below).
   Builder does not load the skill.
   Before branching on the verdict, print the cost line for this round per "## Review cost line"
   above, with `<type> = code` and `<scope> = <batch_name>`.
   Printing the cost line does not relax the read-ban above: the Builder still never reads the
   findings, only the envelope fields the cost line names.

4. Branch on verdict:
   - `APPROVE` — If `nit_count > 0` in the envelope, dispatch one cold-start NIT-only fix pass:
   
     `nit_count` is derived from the envelope's post-ceiling `findings` list; the per-finding `title`, `severity`, and `class` are available there too, if the fixer brief needs them.

     **Dispatch the NIT-fix pass whenever `nit_count > 0` — there is no exception to this for the Builder, even under time or performance pressure.
     'Non-blocking' does NOT mean optional: deferred nits re-surface as BLOCKING in later rounds and cost more total rounds.**
     The fixer, not the Builder, decides what to leave: within the pass, the fixer may leave a nit unfixed only when the reviewer explicitly marked it 'no action required' — that latitude governs the fixer's in-pass judgment, not the Builder's dispatch decision, and never excuses skipping the dispatch itself.

     **Prior-blocking digest.**
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     import _prior_blocking, pathlib
     digest = _prior_blocking.build_digest(pathlib.Path('<reviews_dir-abs-path>'), scope='batch', batch_name='<batch_name>')
     pathlib.Path('<briefs_dir>/prior-blocking-<batch_name>-r<N>.txt').write_text(digest, encoding='utf-8')
     "
     ```
     Unlike the existing prior-notes digest above, this is called at every round with no `N > 1` guard — `build_digest` returns `""` when there is no prior BLOCKING history yet, and `millpy-fix.py` renders an empty digest file as `"(none)"`, so the round-1 case needs no special-casing here.

     Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N> --nits-only --prior-blocking <briefs_dir>/prior-blocking-<batch_name>-r<N>.txt`.
     The fixer loads `mill-receiving-review` and applies the NITs from the APPROVE'd review file. Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior. Do NOT re-review — the NIT fix is trusted. The NIT-fix session commits its own source-file changes atomically; on stuck → escalate via the existing Stuck escalation path.
     After the NIT-fix completes successfully (or is skipped because `nit_count = 0`): compute `converged` per the Convergence gate above.
     If `converged`, or `N >= roles.code-review.batch.rounds` (implicit-approve-at-cap): set batch state → `approved`, `review_file: <path>`. `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`. Use the `file` field from `reviews[0]` in the JSON summary (or the crash-recovery scan path) as `<review_file_path>`. Commit on the task branch: `git -C <worktree> add <status_path> <review_file_path> _mill/briefs/ && git -C <worktree> commit -m "<VARIANT_LABEL>: approve batch {batch_name}"` — when not `converged` (implicit-approve-at-cap fired), append `" (min_rounds/demoted-predicate not satisfied by round cap)"` to the commit message. Break out of the loop → next batch.
     If not `converged` and `N < roles.code-review.batch.rounds`: skip the terminal actions above and continue to round N+1 (re-dispatch code review for this batch).
   - `NEED_CONTEXT` — read the `## Missing context` bullets from the review file.
     For each listed path, if it exists under the worktree, append to `extra_files` for the NEXT round. `_notify.notify("<VARIANT_LABEL>.review-need-context", f"batch {batch_name} round {N}", slug=slug, files=len(missing))`.
     Record this gap for mill-self-report (see `plugins/mill/skills/mill-go-base/handoff.md`).
     Increment round and continue the loop.
     If ALL the missing files are paths already in `extra_files` from a prior round (no new info), treat as a stuck-logic failure and break.
     Reading the structured `## Missing context` bullet list does not require `mill-receiving-review` -- only finding-handling does. `signature: _notify.notify(event: str, detail: str, **context) -> None`
   - `REQUEST_CHANGES` — Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N>`.

     The CLI atomically: resolves the batch plan, sets batch state → `fixing`, calls `_status.append_phase` for `fixing-{batch_name}-r{N}`, commits and pushes (status.md plus the review file), and dispatches a cold-start fixer session with the fix prompt (which instructs the fixer to load `mill-receiving-review` and apply findings).
     Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior described under "1.
     Implement".
     On stuck → escalate.

4.5.
**Step 4.5: ERROR-only-aggregate retry (no round consumed)**

   **Usage-error immediate halt (checked first, every round).** Before evaluating the trigger condition below, inspect the JSON envelope's `reviews[]` array (when present) for any entry with `error_kind: "usage"`. If found, halt immediately on this occurrence — no retry, no round consumed — regardless of what any other entry in the same `reviews[]` list contains. Reuse this same step's existing second-pass halt mechanics below (including whatever batch-state/commit mechanics that halt already implies via the shared *Blocked* section this SKILL.md defines), but halt with `BLOCKED: code review usage error: <message>` (where `<message>` is the offending entry's `error` field) and surface it to the user — distinct wording from the existing `ERROR-only round {N}` phrasing.

   When no entry in `reviews[]` is `error_kind: "usage"` (per the immediate halt above), and the JSON envelope from sub-step 2 has top-level `verdict: "ERROR"` (or, equivalently, every remaining entry in `reviews[]` has `verdict: "ERROR"`), skip sub-step 4 entirely and immediately re-run:

   Tree-guard checkpoint block, pre-dispatch form (see "## Agent-mode dispatch" above) — immediately before this retry's Agent-mode dispatch.

   Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = --batch <batch_name> [--extra-file <p> ...]`.

   Tree-guard checkpoint block, post-dispatch form (see "## Agent-mode dispatch" above) — immediately after it returns.

   The round counter `N` is **not** consumed — the round produced no reviewable output.
   On the **second** consecutive run that still has top-level `verdict: "ERROR"`, halt with `BLOCKED: code review ERROR-only round {N}` and surface each entry's `error` string from `reviews[]` to the user.
   Do NOT auto-retry beyond the second pass.
   The two-pass cap mirrors mill-plan's existing step 3.5. *(Closes #228 — rate-limit errors no longer mis-dispatch the implementer with a null review file.)*

5. **Max-rounds exhaustion.**
   After `roles.code-review.batch.rounds` rounds without APPROVE: `_notify.notify("<VARIANT_LABEL>.review-exhausted", f"batch {batch_name}", slug=slug, rounds=N)`, set batch state → `blocked`, `blocked_reason: "review rounds exhausted"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on {batch_name} after {N} rounds"`.
   Go to *Blocked* below.

### Stuck escalation

For any `stuck_type` (`transient` already-retried, `verify`, `logic`, `infrastructure`, `incomplete`): auto-handle according to the stuck_type rules below — mill-go never surfaces a numbered prompt and waits for an operator reply here.
Each stuck_type gets its own one-shot self-resolve or auto-retry step per the rules below;
on a repeat of the same failure after that one-shot attempt, the bullet's own escalation path sets batch state → `blocked`, appends the phase, commits, and goes to *Blocked*.

- **`infrastructure`** (the worker died, likely logout) — auto-retry ONCE: re-dispatch once with a fresh session (no `--resume` flag — the dead session cannot be reattached).
  If the re-fire also reports `infrastructure`: set batch state → `blocked`, `blocked_reason: "infrastructure: worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on {batch_name}"`, and go to *Blocked*.
  The re-fire matches the existing `running`-state handling in `plugins/mill/skills/mill-go-base/resume.md` (fresh start;
  killed session cannot be reattached).
- **CLI emits `stuck_type: transient`** (LLM-layer failure surfaced as the synthetic stuck JSON described in Implement step 2;
  the CLI exits 1 in that case but stdout carries the JSON) → apply the one-retry policy: re-invoke `millpy-implement.py <batch_name>` once with no `--resume` flag (a fresh session).
  If the second invocation also reports `stuck_type: transient`, escalate per the routing below.
- `transient` (already retried once):
  - **If `commits_made > 0` in the stuck JSON** (the implementer timed out after committing some work): skip re-invocation of the implementer;
    proceed directly to the per-batch cleanliness gate (scope violations check) then code review as if the implementer had reported success — commits were made before the timeout, so there is nothing left to retry.
  - **Otherwise** (no commits made, the field is absent,
    or the timeout happened before any commit) → self-resolve once: re-fire the implementer fresh (no `--resume`) — a first-occurrence timeout with no commits is most often a transient LLM/network hiccup, so no plan edit is needed for this attempt.
    If the retry ALSO reports `transient` with no commits made: set batch state → `blocked`, `blocked_reason: "transient: no commits after retry"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on {batch_name}"`, and go to *Blocked*.
- **`incomplete`** (batch provably partial — some cards committed, not all;
  reached here only when the in-line recovery already ran once and the batch is still partial) — resume preserving the original `start_sha`, never retry-fresh (Shared Decisions `stuck_type: incomplete is a new first-class classification` and `resume must preserve the original start_sha`;
  discussion `warm-resume-mechanism`, `start-sha-preserving-resume`): auto-resume **once** via the same `start_sha`-preserving path (warm-`SendMessage` first, `millpy-implement.py <batch_name> --resume-incomplete` as the fallback — see step 5.5's `incomplete` recovery).
  If the auto-resume yields `success`, continue normally.
  If it is **still** `incomplete`, set batch state → `blocked`, `blocked_reason: "incomplete after resume"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on {batch_name} (incomplete after resume)"` and push, and go to *Blocked*.
  Never re-fire with a fresh `start_sha`.
- `verify` / `logic` (first occurrence) → self-resolve once: investigate the failure using the same judgment an implementer/fixer already applies when picking "edit plan and retry" — read the verify/review output that produced this stuck signal, edit the plan file(s) if the failure traces to an ambiguous or incorrect card.
  **Regardless of whether a plan edit was made**, append a `## Prior failure` section to the affected batch file (`<plan_dir>/NN-<batch_name>.md`, placed immediately after its frontmatter, before `## Rename mechanic`/`## Batch Scope` — create the section if it is not already present) with one new bullet stating the round and the verbatim stuck-JSON `reason` text.
  Before re-firing, record the self-resolve: `_status.append_phase(status_path, "self-resolved-verify-logic", _timestamp.now_utc_iso())`, `git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: self-resolved verify/logic stuck ({batch_name})"`.
  Then re-fire the implementer fresh for this batch.
  If the retry produces the *same* `verify`/`logic` failure on this batch: set batch state → `blocked`, `blocked_reason: "verify/logic: unresolved after retry"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on {batch_name}"`, and go to *Blocked*.

### Blocked

- `_notify.notify("<VARIANT_LABEL>.blocked", f"batch {batch_name}: {blocked_reason}", slug=slug, batch=batch_name)`.
- Release the builder lock:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
  ```
- Tell the user: "Batch X blocked with reason Y. Inspect reviews/ and status.md.
  Re-run `/mill-go` after resolving, or `/mill-abandon` to wind down."
  Do not proceed to Handoff (`plugins/mill/skills/mill-go-base/handoff.md`).

## Resume

**Read `plugins/mill/skills/mill-go-base/resume.md` now, before any other action in this phase.** All of this phase's behaviour lives in that file. Do not proceed from this heading without reading it.

## Holistic code review

**Read `plugins/mill/skills/mill-go-base/holistic-review.md` now, before any other action in this phase.** All of this phase's behaviour lives in that file. Do not proceed from this heading without reading it.

## Handoff

**Read `plugins/mill/skills/mill-go-base/handoff.md` now, before any other action in this phase.** All of this phase's behaviour lives in that file. Do not proceed from this heading without reading it.

## Principles

- **Lean Builder.**
  You never read card bodies, diffs, or source files unless responding to a stuck-logic event on a specific batch.
  Your context stays small by design — this is what lets Opus be a legitimate Builder choice.
- **Implementer owns receive-review.**
  On `REQUEST_CHANGES` the implementer (not Builder) loads `mill-receiving-review` and applies findings.
  Builder passes a pointer to the review file;
  the implementer's warm session already knows the code.
- **Commits go through `git-commit`.** `implementer-brief.md` already instructs this, but enforce it if the implementer asks for confirmation: every per-card commit invokes the `git-commit` skill so lint + `codeguide-update` run per-commit.
  Batch N+1's implementer then reads a codeguide that already reflects batch N's additions.
- **One task per worktree.**
  The builder lock enforces this at runtime.
  Do not attempt to relax it.
- **Never guess when stuck.**
  Self-resolve once per the documented `stuck_type` rules, then halt cleanly (`_status.set_blocked`) if the same failure recurs — never invent a recovery beyond that one documented attempt, and never surface a numbered-options prompt to the operator.
- **Review files are the ground truth.**
  Verdict parsing reads only the fenced yaml block;
  the `## Findings` body is the implementer's job to read, not yours.
- **Helper signatures are documented inline.**
  Every helper this skill names has an explicit one-line signature in the section that calls it.
  Never Read or Grep the helper source — the signature is here,
  and any failure surfaces as an exception. (See `mill:workflow` for the project-wide rule.)
- **TodoWrite items name batches by number.**
  Emit todo items as `Implement batch N (<batch-slug>)` — e.g. `Implement batch 1 (foundations)` — so progress in the todo list correlates 1:1 with plan files (`NN-<batch-slug>.md`).
  Bare names without a number force the operator to cross-reference the Batch Index every time.

## Board discipline

- `status_path`, `reviews_dir/<file>`, and `plan_dir/<file>` writes are committed on the **task branch** via `git -C <worktree> add ... && git -C <worktree> commit`. `millpy-implement.py` and `millpy-fix.py` push their own task-branch state commits (batch-start, batch-fix, holistic-fix) to `origin/<task-branch>` immediately after each `git commit`.
  The Builder's own state commits (Prepare, Approve, blocked, done) and per-card implementer commits do not push — mill-merge pushes the full task branch at task end.
  Adding push to the Builder's own commits is a follow-up task;
  this PR scopes the push policy to CLI commits only.
- Wiki phase mutations (the Handoff `[ready-to-merge]` flip) go through `_client.set_phase(wiki_path, slug, "ready-to-merge")`.
  The daemon serializes all writes and pushes automatically.
- Phase transitions via `_status.append_phase`;
  batch-state mutations via `_status.set_batch_field`.
  Hand-editing either yaml block is banned.
- The path-invariant rule from CLAUDE.md is load-bearing: working state never goes to the wiki — only Home.md / _Sidebar.md do.

## History

Pre-strip version (1483 lines, with the legacy non-agent dispatch branches and the Resume /
Holistic / Handoff sections inline) is at commit `356da5e5`. Restore with:
`git show 356da5e5:plugins/mill/skills/mill-go-base/SKILL.md`.
