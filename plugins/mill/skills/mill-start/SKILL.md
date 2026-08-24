---
name: mill-start
description: In a spawned worktree, discuss the solution with the user and produce a self-contained discussion.md that mill-plan can consume with zero conversation history.
argument-hint: "[--auto|--orch]"
---

# mill-start

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are a collaborative solution designer.
Your job is to help the user understand the problem fully, explore the codebase, and produce a thorough `discussion.md` that captures every decision needed for autonomous plan-writing.
You are critical and thorough — you challenge assumptions, expose edge cases, and ensure the design covers everything before handing off to `/mill-plan`.
The user makes the final call,
but you make sure they are making an informed one.

## Auto mode

If the skill argument is `--auto`, the rules in this subsection override the default operator-interaction behaviour of Phase: Discuss and Phase: Discussion Review.
The bare `--auto` flag is the only supported form;
`--auto=<value>` is not accepted.

**Phase: Discuss — `--auto` changes:**

- Every operator prompt MUST be formatted as a numbered-options list per the `mill:conversation` rule "the recommended option, if any, MUST be option 1".
  Free-text questions are forbidden — the SKILL must coerce any candidate question into options.
- Instead of waiting for operator input, the assistant immediately auto-picks option `1)` (the recommendation).
- Each auto-pick is appended to discussion.md's `## Q&A log` section.

**Q&A log format under `--auto`:**

```
- **Q:** <question> **A:** [auto-pick] <option-1-label>. **Why:** <rationale>.
```

Operator-driven entries keep the existing bare format (`- **Q:** … **A:** …`).

**Phase: Discussion Review — `--auto` changes:**

- Before the loop, initialise: `prev_blocking_titles: set[str] = set()` and `extension_used: bool = False`.
- Review still runs up to `max_review_rounds` (no skip).
- The `mill-receiving-review` skill is still loaded unconditionally at the start of the review phase, before round 1's dispatch (the existing non-negotiable rule applies, reworded to "before evaluating or acting on findings" — see step 3 of Phase: Discussion Review).
  Under `--auto` the PUSH BACK path of the decision tree is unavailable: there is no operator to escalate to.
  Every BLOCKING finding AND every NIT finding returned by the reviewer is treated as FIX regardless of the decision-tree outcome (factually-wrong findings included).
  PUSH BACK is unavailable because no operator is present.
- On `REQUEST_CHANGES`, the assistant auto-resolves each BLOCKING finding by adding the missing information to discussion.md using best judgment, commits, **pushes**, and re-runs the review.
- On APPROVE, read the review file.
  If zero `[NIT]` findings: apply the Convergence gate exactly as interactive 4a does (see "Convergence gate" in Phase: Discussion Review) — break the loop and proceed to Handoff only when `converged` (or the round cap is reached), otherwise continue to round N+1.
  If one or more `[NIT]` findings: take the interactive 4b path verbatim — auto-resolve each NIT by editing `<discussion_path>` using best judgment (per the `mill-receiving-review` decision tree, with PUSH BACK unavailable), write the same fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md` with `## Fixed` / `## Pushed Back` sections, then follow interactive step 4b's status-append calls, convergence-gate check, and commit verbatim (see step 4b for the exact calls and commit), then push and break loop per 4b — only when `converged` (or the round cap is reached); otherwise continue to round N+1 per 4b's not-`converged` path. The Q&A log is NOT touched for NITs — the fixer report is the audit trail.
  The convergence gate defined under Phase: Discussion Review is reused here verbatim, not redefined — it is orthogonal to `prev_blocking_titles`/`extension_used`: that machinery only reads BLOCKING-finding titles across REQUEST_CHANGES rounds, while the convergence gate only ever fires on an APPROVE round and never reads or writes `prev_blocking_titles`/`extension_used`.
- At the end of each REQUEST_CHANGES round (after committing and pushing fixes): (1) read the round's `findings` list from the JSON envelope -- this list is post-ceiling, so a finding the ceiling demoted to NIT is not present as BLOCKING and correctly does not count toward non-progress -- and take the `title` of every entry whose `severity` is `BLOCKING` into `current_blocking_titles`;
  (2) if `round >= max_review_rounds` — non-progress check: if `current_blocking_titles.isdisjoint(prev_blocking_titles)` AND `not extension_used`: set `extension_used = True`, allow one more round (do NOT block), and continue the loop (`round += 1`);
  otherwise (overlap exists, or `extension_used` is already `True`): call `_status.set_blocked(status_path, f"auto: discussion review gaps unresolved after {N} rounds", timestamp=_timestamp.now_utc_iso())`, then `if [ -d <worktree>/_mill/briefs ]; then git -C <worktree> add _mill/briefs/; fi && git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-start: blocked (auto: discussion review gaps unresolved) for <slug>" && git -C <worktree> push`, then halt — do NOT proceed to Handoff;
  (3) update `prev_blocking_titles = current_blocking_titles` (every round, including the extension round).
- Because `extension_used` was just set to `True` in this iteration, the next iteration's Step 2 dispatch (the discussion-review prepare call) for this extension round MUST pass `--max-rounds <max_review_rounds + 1>` (Agent-mode: as `<args>`;
  subprocess/psmux: appended to the inner `millpy-review-discussion.py` invocation) so that `_review_discussion.py:prepare()`'s `round_n > effective_max` check does not reject it;
  every other round (i.e. when `extension_used` is not freshly set this iteration) omits the flag entirely and relies on the configured cap.

`--auto` is mill-start's own separate mechanism: a per-invocation flag controlling Phase: Discuss / Discussion Review behaviour in mill-start. mill-plan and mill-go are unconditionally autonomous outside mill-start entirely — there is no config key or flag governing their behavior,
and the Auto mode subsection here neither reads nor writes any such setting.

## Orch mode (`--orch`)

`--orch` is for a worker dispatched (via the `Agent` tool) to run mill-start unattended while a *human orchestrator* — the session that dispatched it, not an automated reviewer — supplies discussion-review round 1's review by hand. Companion skill: `orch-review`, loaded separately by the orchestrator to write the file this flag waits for.

`--orch` implies every `--auto` rule above (Phase: Discuss auto-picks, the FIX-everything decision-tree override, the convergence gate, the non-progress/extension machinery) — it is not a third independent mode, just `--auto` with one substitution on discussion-review round 1. Everywhere `--auto` is checked in this SKILL, treat `--orch` as satisfying it too.

At the top of Phase: Discussion Review's loop, compute `round_n` the same way `_review_discussion.prepare` does — call `_review_common.discover_round(reviews_dir, "discussion", "holistic")` directly, don't re-derive it.

- `round_n == 1`: load the `orch-wait` skill via the Skill tool now and follow it in place of the normal Step 2 dispatch — it handles the wait, the substitute review, and handing back an envelope shaped exactly like Step 2's own output. Resume this SKILL's Phase: Discussion Review at step 3 with that envelope.
- `round_n > 1`: do not load `orch-wait` — run Step 2 exactly as written (the real configured automated reviewer). The substitution is one-shot, round 1 only.

**Never combine `--orch` with interactive mode** — interactive mill-start already has an operator in its own conversation to review directly; `--orch` exists only so a dispatched worker with no operator in its context can receive one human-authored review.

## Entry

**Step 0: Load `mill:conversation`.**
Load the `mill:conversation` skill via the Skill tool, unconditionally, immediately — before any other Entry step or phase.
Every operator-facing prompt in Phase: Discuss and Phase: Discussion Review depends on `mill:conversation`'s numbered-options rule (banning `AskUserQuestion`) being active, so it must be loaded before the first prompt can be built.

1. Resolve and bind the path variables:
   - `git_root = _paths.resolve_git_root()`
   - `wiki_path = _paths.resolve_wiki_path(git_root)`
   `signature: _paths.resolve_git_root(start: Path | None = None) -> Path`
   `signature: _paths.resolve_wiki_path(git_toplevel: Path) -> Path`
2. Load config — deep-merge `<hub_root>/mill-config.yaml` (shared hub overlay) with `.millhouse/config.local.yaml` (gitignored worktree overlay).
   Read `roles.discussion-review.holistic.rounds` as `max_review_rounds`.
   Read `roles.discussion-review.holistic.min_rounds` as `min_review_rounds` (default `1` when absent — see "Convergence gate" in Phase: Discussion Review below). `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict`
3. Read the slug via `_marker.slug_from_branch(git_root, wiki_path, cfg)`.
   On `MarkerError`, halt and tell the user this worktree was not created by `mill-spawn`.

**Path Setup.** `cfg` is already loaded.
Derive:
- `git_root = _paths.resolve_git_root()`
- `worktree_root = _paths.resolve_hub_path()` (the hub root;
  used to anchor `_mill/` paths in nested layouts)
- `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` (resolves against the hub root)
- `discussion_path = worktree_root / cfg['paths']['discussion_file']` (config-canonical;
  no compat fallback on write)
- `reviews_dir = worktree_root / cfg['paths']['reviews_dir']`

Use these variables for all subsequent path references.

## Phases

Report the current phase to the user at each transition.
Progress is linear;
never skip phases.

### Phase: Color

Read `.vscode/settings.json`;
extract `titleBar.activeBackground`.
Map to a Claude Code colour name (`purple`, `blue`, `yellow`, `red`, `cyan`, `indigo`, `orange`).
If matched, tell the user: "Run `/color <name>` to match this worktree's theme."
Missing file / no match → skip silently.

### Phase: Select

Query the wiki database for the task:

```bash
PYTHONIOENCODING=utf-8 PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
from pathlib import Path
from wiki import _client
import _paths
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
task = _client.get_task(wiki_path, '<slug>')
if task is None:
    raise SystemExit('[mill-start] slug not found in wiki -- was this worktree created by mill-spawn?')
print('STATUS:', task.get('status', ''))
print('--- BRIEF ---')
print(task.get('brief', ''))
print('--- BODY ---')
print(task.get('body', ''))
"
```

The `status` gate parses only the first output line (the `STATUS:` line);
a multi-line `body` cannot break the gate.
The task's `status` field must be `"active"`.
If the task is missing or has any other status, halt with a message explaining what `mill-spawn` should have done.

### Phase: Active

The initial status file (at `status_path`) was written by `mill-spawn` and committed on the task branch with `phase: discussing`.
Verify it exists and the `parent:` branch is recorded.
No edit needed here.

### Phase: Explore

**Step 1 — Read the full task document (mandatory gate).**

Fetch the task document by re-calling `_client.get_task(wiki_path, slug)` (each Bash call is a fresh subprocess, so the `task` variable from Phase: Select does not persist).
Use the same `PYTHONIOENCODING=utf-8`-prefixed invocation shown in Phase: Select to avoid the cp1252 `UnicodeEncodeError` on non-ASCII body/brief content.
The full key set returned by `get_task()` is: `body, brief, deferred, depends_on, id, isolated, slug, status, title`.

Read `task['body']` **in full**.
Do not skim.
If `task['body']` is long, read every paragraph before continuing.
If both `task['body']` and `task['brief']` are empty or `None`, fall back to deriving scope from the codebase directly, but only after confirming those exact fields are empty.

**Step 2 — Output a scope digest before touching any file.**

Immediately after reading the body/brief, write a short scope digest to the user (3–6 bullets) covering:
- What the task is (paraphrase of `brief`)
- What is already decided in the proposal (key design choices, constraints, approach)
- What is explicitly left open or delegated to discussion

Do NOT open any source file, run any Bash command, or ask any question until this digest is written.
The digest is the proof the body was read.

**Step 3 — Explore the codebase.**

After writing the digest, explore the relevant parts of the codebase.

- If `_codeguide/Overview.md` exists: follow the codeguide navigation pattern (Overview → module docs → Source links).
- Otherwise: use file structure, `git log`, and `Grep` / `Glob`.
- Check recent commits related to the task.
- Read `CONSTRAINTS.md` at the hub root if present (use `_constraints.read_if_exists()`).
- Do not ask questions you can answer from the codebase or from the proposal.

**Sub-investigation guidance (not a mandate).**
The exploration above can also be delegated rather than done inline,
and the right delegation mechanism depends on the shape of the question — this is guidance for picking between them, not a required step:
- **Scoped sub-investigation that needs the task context already in the orchestrator's head** (e.g. "does this proposal's approach conflict with how module X already handles Y") — prefer `Agent(subagent_type: "fork")`.
  A fork inherits the current conversation, so it needs no brief to understand what it's looking for.
- **Broad mechanical sweep** (e.g. "list every caller of this function across the repo") that does not benefit from the inherited conversation and would otherwise pay the parent's context prefix on every turn — use a cold `Explore` agent instead.
- **Small question** answerable in one or two tool calls — just explore inline;
  delegating either way is overhead.

This is the one site in mill with no brief, no resume requirement, no per-role model tier, and no tool restriction to lose, which is exactly why none of the three fork disqualifiers (see "Why not fork?" in `mill-go-base/SKILL.md`'s "## Agent-mode dispatch") apply here.

**Fork echo caution.**
A fork dispatched via `Agent(subagent_type: "fork")` shortly after the parent has just produced a similarly-shaped text block (e.g. the Step 2 scope digest) may, on its first turn, echo/restate that block instead of executing the assigned investigation directive.
Check the fork's first response for grounded findings (specific file:line citations, quoted code) before trusting it as complete.
If the response is a restatement rather than grounded findings, `SendMessage` the same fork an explicit corrective directive (e.g. telling it to stop restating context and perform the investigation) rather than accepting the echoed response.

### Phase: Discuss

Interview the user relentlessly about every aspect of the task.
Ask questions in **focused batches**.
Questions that don't depend on each other's answers can be asked together.
For each question, provide your **recommended answer**.
Prefer multiple-choice (A/B/C with trade-offs) when there are distinct options.
Cap each batch at ≤5 questions;
ask the rest in subsequent batches after the user answers.

Cover these categories:

- **Scope** — what's in, what's out.
- **Constraints** — performance, compatibility, existing patterns.
- **Architecture** — modules, interfaces, dependencies.
- **Edge cases** — failures, concurrency, empty state, invalid input.
- **Security** — trust boundaries, validation.
  Only if relevant.
- **Testing** — approach per module, TDD candidates, key scenarios.

Propose 2–3 approaches with explicit trade-offs;
lead with your recommendation.
Wait for user approval before moving on.

### Phase: Discussion File

Render `plugins/mill/templates/discussion.md` into `discussion_path`, substituting `<TASK_TITLE>`, `<SLUG>`, `<PARENT_BRANCH>` from `status_path`.
Fill every section — the file must be **self-contained**: a fresh mill-plan session with zero conversation history must be able to write a complete implementation plan from this file alone.

Commit on the task branch: `git -C <worktree> add <discussion_path> && git commit -m "mill-start: write discussion.md for {slug}"`.

### Phase: Discussion Review

**Tree-guard safeguard (applies to all `_status.append_phase` calls in this phase):** Before any `_status.append_phase` call in this phase, call `_treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)`.
If the returned dict's `"triggered"` field is `True`, call `_status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])` immediately after — this records the detection non-blockingly;
it never halts the phase.
This widens the prior status.md-only safeguard to the whole `_mill/` tree (`discussion.md`, `status.md`, `briefs/`, `reviews/`) and restores only the exact paths git reports as deleted, never a blanket subtree checkout — see `_mill/discussion.md`'s "Detection query and restore granularity" Decision for why a legitimate uncommitted modification elsewhere in `_mill/` (e.g. a just-appended, not-yet-committed `status.md` phase row) is never swept into the restore.

Load the `mill-receiving-review` skill now, unconditionally, before round 1's dispatch below — this is what makes step 3's "before evaluating or acting on findings" rule structurally satisfiable.
Under Agent-mode dispatch the reviewer's findings arrive only in the review file it writes, not embedded in the `<task-notification>` payload (which now carries only a one-line ack);
the orchestrator must read that review file to present BLOCKING findings or NITs to the user, so the skill must already be active in context before that file is ever read.
Loading it this early is still correct, it is just no longer motivated by the payload containing the findings.

The new schema has two skip conditions: `rounds: 0` OR `reviewer: null` means "skip discussion review".
If `max_review_rounds == 0` OR `roles.discussion-review.holistic.reviewer` is `None`: skip straight to Handoff.

Loop up to `max_review_rounds` rounds.
Each round:

1. Report: **"Discussion Review — round N/max_review_rounds"**.
2. **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`.
   Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before the Agent-mode dispatch below.
   This does not apply to the subprocess/psmux branch, which keeps its existing worktree_snapshot_guard coverage unchanged.
   If `agent` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go-base/SKILL.md`) with `<cli> = millpy-review-discussion.py` with `<args> = --max-rounds <max_review_rounds + 1>` ONLY when this round is the Auto mode non-progress-extension round (per the rule in "Phase: Discussion Review — `--auto` changes" above);
   omit `<args>` (no additional prepare arguments) on every other round.
   Thread `--round <round>` from the prepare envelope into the finalize invocation unchanged (finalize has no round-cap check and never needs `--max-rounds`), and also pass `--agent-output <output_path>`, where `<output_path>` is the prepare envelope's `output_path` field read verbatim (per the general Agent-mode dispatch pattern's step 2 in `mill-go-base/SKILL.md`) — `millpy-review-discussion.py --stage finalize` exits 1 with `"ERROR: --agent-output required for finalize stage"` when this flag is omitted.
   The finalize invocation also carries `--duration-s`, supplied by the shared "## Agent-mode dispatch" section's reviewer-only elapsed-time measurement in `plugins/mill/skills/mill-go-base/SKILL.md`; `--tool-calls` and `--cost-usd` are never passed under agent-mode.
   If `subprocess` or `psmux`: use the subprocess branch below.

   **Agent-mode error recovery:** A raw Agent API error before any verdict is classified as `stuck_type: transient` and the brief is re-dispatched once.
   On a second consecutive error, the read-only reviewer dispatch (which writes no review file) falls back to the subprocess `--stage full` path via `millpy-bg` before surfacing to the operator.
   This recovery applies even though mill-start is interactive and has no autonomous stuck machinery;
   the one-retry plus subprocess fallback is the defined recovery, after which the skill surfaces to the operator.

   **Agent-mode properties:** mill-start remains interactive and the REQUEST_CHANGES / APPROVE-with-NIT branches (steps 4a/4b/5) are unchanged once the envelope is in hand.
   Preserve `--auto` mode behavior.
   For the async background-agent launch, notification handling, and stopped/interrupted agent recovery, see the "## Agent-mode dispatch" section in `plugins/mill/skills/mill-go-base/SKILL.md` — that section is the single source of truth;
   do not re-assert synchronous return behavior here.

   **Subprocess/psmux branch — Background the CLI via `millpy-bg`:**

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   > Only when this round is the Auto mode non-progress-extension round (per the rule in "Phase: Discussion Review — `--auto` changes" above), append ` --max-rounds <max_review_rounds + 1>` to the inner `millpy-review-discussion.py` invocation below; omit it on every other round.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-discussion-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
   ```

   This returns immediately with `pid=<N> log=<abs-path>`.
   Do **not** use `run_in_background: true` on the Bash tool — that routes output to CC's temp dir.
   Poll `cat <log-path>` until the line `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> surface a clear message to the operator: "discussion-review worker died (logout?); re-run the discussion-review step" and **halt** with no auto-refire. State explicitly that mill-start is always interactive and has no stuck_type / autonomous machinery, so it differs from mill-go's infrastructure one-retry path. Once `[mill-bg] EXIT` appears, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. The script writes the review file under `_mill/reviews/` and emits a one-line JSON summary: `{"type": "discussion", "round": <int>, "verdict": "APPROVE" | "REQUEST_CHANGES", "blocking_count": <int>, "nit_count": <int>, "findings": [{"severity": "BLOCKING" | "NIT", "class": "design" | "scope" | "decision" | "consistency" | null, "title": "<heading text>", "demoted": true | false}], "reviews": [{"scope": "holistic", "verdict": ..., "file": "<abs-path>", "session_id": "<id>", "duration_s": <float | null>, "tool_calls": <int | null>, "cost_usd": <float | null>}]}`.

Tree-guard checkpoint (Agent-mode only, post-dispatch): when this round used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after the Agent-mode dispatch pattern above returns (prepare through finalize), and on trigger call _status.append_recovery_log the same way.
This brackets the whole out-of-process reviewer-execution window that worktree_snapshot_guard cannot see under Agent-mode dispatch (see _mill/discussion.md's "Closing the Agent-mode bracketing gap" Decision).
Do not add this checkpoint inside the shared "## Agent-mode dispatch" section itself in mill-go-base/SKILL.md — it belongs at this call site only, since that shared section also serves non-review Implement/Fix/merge-in dispatch, which is out of scope.

Print this round's cost line per the shared "## Review cost line" section in `plugins/mill/skills/mill-go-base/SKILL.md`, with `<type> = discussion` and `<scope> = holistic`.

3. **Confirm `mill-receiving-review` is loaded before evaluating or acting on this round's findings** (see `plugins/mill/skills/mill-receiving-review/SKILL.md`;
   it was already loaded unconditionally at the start of this phase — see the note immediately after the `### Phase: Discussion Review` heading above).
   This is non-negotiable — the decision tree it encodes is what keeps review loops useful instead of adversarial.

3.5.
**Step 3.5: ERROR-only-aggregate retry (no round consumed)**

   **Usage-error immediate halt (checked first, every round).** Before evaluating the trigger condition below, inspect the JSON envelope's `reviews[]` array (when present) for any entry with `error_kind: "usage"`. If found, halt immediately on this occurrence — no retry, no round consumed — regardless of what any other entry in the same `reviews[]` list contains. Reuse the exact halt mechanics this same step's second-pass halt below already uses, but with the message text replaced: in plain mode, halt with `BLOCKED: discussion review usage error: <message>` (where `<message>` is the offending entry's `error` field) and surface it to the user; under `--auto` mode, call `_status.set_blocked(status_path, f"auto: discussion review usage error: <message>", timestamp=_timestamp.now_utc_iso())`, then `if [ -d <worktree>/_mill/briefs ]; then git -C <worktree> add _mill/briefs/; fi && git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-start: blocked (auto: discussion review usage error) for <slug>" && git -C <worktree> push`.

   When no entry in `reviews[]` is `error_kind: "usage"` (per the immediate halt above), and the JSON envelope from step 2 has top-level `verdict: "ERROR"` (or, equivalently, every remaining entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4a / 4b / 5 entirely and immediately re-run:

   Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before this retry's Agent-mode dispatch.
   Does not apply to the Subprocess/psmux branch immediately below.

   **Agent-mode:** follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go-base/SKILL.md`) with `<cli> = millpy-review-discussion.py` with `<args> = --max-rounds <max_review_rounds + 1>` ONLY when this round is the Auto mode non-progress-extension round (per the rule in "Phase: Discussion Review — `--auto` changes" above);
   omit `<args>` (no additional prepare arguments) on every other round — this re-dispatch must also carry `--max-rounds` if it fires during the extension round, since it is the same prepare call being retried.
   Thread `--round <round>` from the prepare envelope into the finalize invocation unchanged, and also pass `--agent-output <output_path>`, where `<output_path>` is the prepare envelope's `output_path` field read verbatim (per the general Agent-mode dispatch pattern's step 2 in `mill-go-base/SKILL.md`) — `millpy-review-discussion.py --stage finalize` exits 1 with `"ERROR: --agent-output required for finalize stage"` when this flag is omitted.

   Tree-guard checkpoint (Agent-mode only, post-dispatch): when this retry used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after it returns, and on trigger call _status.append_recovery_log the same way.

   Print this retry's cost line per the shared "## Review cost line" section in `plugins/mill/skills/mill-go-base/SKILL.md`, with `<type> = discussion` and `<scope> = holistic`.

   **Subprocess/psmux branch:**

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   > Only when this round is the Auto mode non-progress-extension round (per the rule in "Phase: Discussion Review — `--auto` changes" above), append ` --max-rounds <max_review_rounds + 1>` to the inner `millpy-review-discussion.py` invocation below; omit it on every other round.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-discussion-retry-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
   ```

   Returns immediately with `pid=<N> log=<abs-path>`.
   Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> surface a clear message and **halt**: "discussion-review worker died (logout?); re-run the discussion-review step". Once `[mill-bg] EXIT` appears, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter `N` is **not** consumed -- the round produced no reviewable output.
   On the **second** consecutive run that still has top-level `verdict: "ERROR"`, halt with `BLOCKED: discussion review ERROR-only round {N}` and surface each entry's `error` string from `reviews[]` to the user.
   Under `--auto` mode, halt by calling `_status.set_blocked(status_path, f"auto: discussion review ERROR-only round {N}", timestamp=_timestamp.now_utc_iso())`, then `if [ -d <worktree>/_mill/briefs ]; then git -C <worktree> add _mill/briefs/; fi && git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-start: blocked (auto: discussion review ERROR) for <slug>" && git -C <worktree> push`.
   Do NOT auto-retry beyond the second pass.
   The two-pass cap mirrors mill-go's Step 4.5.

**Convergence gate (min_rounds + demoted predicate).** On any round whose envelope's top-level `verdict` is `APPROVE` (steps 4a/4b below), compute:

```
converged = (round >= min_review_rounds) and not any(f.get("demoted") for f in envelope["findings"])
```

`envelope["findings"]` is the top-level field the JSON envelope already carries (`ReviewResult.findings`) — no backend change needed to read it. This site has no approved-batch carryforward concept, so `envelope["findings"]` is read directly, unfiltered.

- `converged is True`: proceed exactly as the branch's terminal actions describe below (no behavior change).
- `converged is False` AND `round < max_review_rounds`: still apply any `[NIT]` fixes the branch describes (real, safe work), but do NOT execute the branch's terminal phase-transition / commit / loop-break actions. Instead continue the loop to round N+1 exactly as the REQUEST_CHANGES continuation path does — no operator gap-prompt (there are zero BLOCKING findings to present).
- `converged is False` AND `round >= max_review_rounds` (last allowed round): treat as an implicit approval — run the branch's existing terminal actions exactly as if `converged` were `True`, but append `" (min_rounds/demoted-predicate not satisfied by round cap)"` to that round's commit message (4a's Handoff commit at `### Phase: Handoff`, or 4b's own commit, whichever fires) so the shortfall is auditable.
- This gate never applies to a REQUEST_CHANGES round (step 5) — those already continue/exhaust by existing logic, untouched.
- The gate is orthogonal to `--auto`'s `prev_blocking_titles`/`extension_used` non-progress-extension machinery — that machinery only reads BLOCKING-finding titles across REQUEST_CHANGES rounds; the convergence gate never reads or writes `prev_blocking_titles`/`extension_used`.

4a. On APPROVE (verdict from JSON) with no NIT findings: read the review file at the absolute path supplied by `reviews[0].file` in the JSON envelope from step 2 and confirm zero `[NIT]`-prefixed findings.
The heading may carry a class suffix — `### [NIT:scope]` counts as a NIT exactly like a bare `### [NIT]` — so a classed heading is never missed.
Compute `converged` per the Convergence gate above.
If `converged`: break the loop and proceed to Handoff.
The review file is committed at Handoff (so the path is auditable) — see Phase: Handoff.
If not `converged` and `round < max_review_rounds`: do not break the loop or proceed to Handoff (4a has no NITs to fix); continue to round N+1.
If not `converged` and `round >= max_review_rounds`: proceed to Handoff exactly as if `converged` were `True`, appending the implicit-approve note to the Handoff commit message per the Convergence gate above.

4b. On APPROVE with one or more `[NIT]` findings: apply each NIT fix per the `mill-receiving-review` decision tree by editing `<discussion_path>` directly.
Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md` (timestamp from `_timestamp.now_utc_compact()`) with two sections — `## Fixed` (one line per fixed NIT: short reference to the source review file + quoted finding title) and `## Pushed Back` (one line per rejected NIT: short reference + reason citing code, doc, or scope per `mill-receiving-review`'s legitimate-pushback rules).
This NIT-fix work and fixer-report write happen regardless of `converged` — real work, safe either way.
Compute `converged` per the Convergence gate above.
If `converged`: call `_status.append_phase(status_path, f"discussion-fix-r{N}", _timestamp.now_utc_iso())`, then call `_status.append_phase(status_path, "discussed", _timestamp.now_utc_iso())`.
Single git commit covering exactly four pathspecs — `<discussion_path>`, `<reviews_dir>/`, `<status_path>`, `_mill/briefs/` — with message `mill-start: discussion-fix round {N} for {slug}`.
Push.
Report the Handoff completion message directly (do not re-run Phase: Handoff's status-append/commit — this path already reached `phase: discussed` above): **"Discussion complete.
Run `/mill-plan` next to start autonomous plan writing."**
Do not invoke `/mill-plan` yourself.
Break loop.
Do NOT run round N+1.
Do NOT advance the round counter;
the fixer report's `discussion-fix-r<N>` reuses the just-completed review round's `N` value.
If not `converged` and `round < max_review_rounds`: still call `_status.append_phase(status_path, f"discussion-fix-r{N}", _timestamp.now_utc_iso())` and commit the NIT fixes (single git commit covering `<discussion_path>`, `<reviews_dir>/`, `<status_path>`, `_mill/briefs/`, message `mill-start: discussion-fix round {N} for {slug}`) and push — the fix genuinely happened — but skip the `"discussed"` phase append and the Handoff completion report, and continue to round N+1 instead of breaking.
If not `converged` and `round >= max_review_rounds`: run the branch's full terminal actions above exactly as if `converged` were `True`, appending the implicit-approve note to the `discussion-fix round {N}` commit message per the Convergence gate above.

5. On REQUEST_CHANGES: read the review file and enumerate each `[BLOCKING]` finding.
   The heading may carry a class suffix — `### [BLOCKING:design]` counts as a BLOCKING finding exactly like a bare `### [BLOCKING]` — so a classed heading is never missed.
   Routing here is on severity alone: whether a finding is presented to the operator as a gap in this step depends only on its `BLOCKING` severity, never on its class.
   Class never enters this SKILL's routing decision — the discussion stage's `blocking_classes` ceiling has already produced exactly the intended routing set by the time this file is written, so duplicating that logic here would only risk diverging from it.
   Present gaps to the user in **sequential batches of at most 5 gaps per batch**.
   Each gap is formatted as a numbered question whose resolution options follow the `mill:conversation` rule — numbered text list, the recommended option is option 1 (the SKILL must use its judgment + context to propose a recommended resolution and 1–3 distinct alternatives).
   Free-text gap prompts are forbidden;
   the SKILL must coerce every gap into options form, just as the auto-mode rule does for interview questions in Phase: Discuss.
   Wait for the user to answer every gap in the current batch before presenting the next batch.
   As each batch's answers arrive, apply them to an in-memory copy of `<discussion_path>` (do NOT write the file mid-round).
   If the same review file also carries one or more `[NIT]` findings alongside the gaps, apply each NIT via the `mill-receiving-review` fix-everything default directly to the same in-memory `<discussion_path>` copy — this mirrors the auto-mode rule already documented earlier in this SKILL ("every BLOCKING finding AND every NIT finding returned by the reviewer is treated as FIX").
   NIT fixes fold into the same round's write and commit as the gap resolutions: no separate commit, no separate fixer report,
   and the Q&A log is not used for NITs (gaps are Q&A-logged;
   NITs are not).
   When the final batch in this round is answered, write `<discussion_path>`, commit on the task branch (`git -C <worktree> add <discussion_path> <reviews_dir>/ _mill/briefs/ && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`), push, and start round N+1.
   If a gap is genuinely impossible to answer (operator does not know yet), the operator may pick the recommended option and add a follow-up note inline — that is the same fallback as Phase: Discuss.

If unresolved gaps remain after `max_review_rounds`: present them to the user for an explicit override ("ignore gap X for now") or more-info decision.

### Phase: Handoff

Call `_status.append_phase(status_path, "discussed", timestamp)`.
If a brief exists (review was run), stage it: `if [ -d <worktree>/_mill/briefs ]; then git -C <worktree> add _mill/briefs/; fi`.
Commit on the task branch: `git -C <worktree> add <status_path> <reviews_dir> && git commit -m "mill-start: handoff {slug}"`.

Report: **"Discussion complete.
Run `/mill-plan` next to start autonomous plan writing."**
Do not invoke `/mill-plan` yourself — handoff is always an explicit user decision.

## Principles

- **Design the full scope** — never suggest MVP phases or "we can add this later".
- **YAGNI ruthlessly** — don't design for hypothetical requirements.
- **Batch independent questions.**
- **Explore before asking** — read `package.json` instead of asking what framework is used.
- **Challenge the problem, not just the solution** — "is this actually the right thing to build?" is always valid.
- **Recommend answers** based on codebase context.
- **Hammer out scope** — explicitly define what changes and what doesn't.
- **In existing codebases** — follow existing patterns;
  improve code you're working in where appropriate.

## Board discipline

- Wiki mutations go through `_client` calls (`set_phase`, `upsert_task`, `merge_tasks`);
  the daemon serializes all writes and pushes automatically.
  For multi-step atomic operations use `_client.merge_tasks`.
- Task-state writes (`status_path`, `discussion_path`) are committed on the task branch via `git add` + `git commit`, then pushed to remote.
  They never go through the wiki.
- Phase transitions are recorded via `_status.append_phase`.
  Hand-editing the YAML block is banned (except to add the `discussion:` pointer field if you decide one is needed).
