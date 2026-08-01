# Discussion: Add mill-quick: skip-review pipeline for simple tasks

```yaml
task: Add mill-quick: skip-review pipeline for simple tasks
slug: mill-quick
status: discussing
parent: main
```

## Problem

The full mill pipeline (mill-start discussion + review rounds, mill-plan +
plan-review rounds, mill-go implement + code-review + fixer loops) pays a
fixed review-and-orchestration cost regardless of task size. For genuinely
simple or mechanical tasks — small doc fixes, one-line config changes,
renames — that cost is pure overhead: the "review" step ends up re-reading
the same few lines back with no real risk being caught.

There is currently no shortcut. Every spawned task pays the full
discuss/plan/review/implement/review cost. `mill-quick` is a new skill,
invoked immediately after `mill-spawn` (in place of `mill-start`), that
collapses the entire pipeline into a single pass: one session reads the
task, makes the fix, commits, runs the repo's test suite, and marks the
task done — with no discussion round, no plan, no reviewer of any kind.

## Scope

**In:**
- New skill `mill-quick`, entry-gated to run only when `_mill/status.md`
  `phase: discussing` (i.e. immediately post-`mill-spawn`, before
  `mill-start` has ever run).
- Reads the task directly from the wiki (`_client.get_task(wiki_path,
  slug)`), the same call `mill-start` Phase: Explore Step 1 uses — there is
  no `discussion.md`/`plan.md` to read from, since this bypasses both.
- The invoking session itself performs the entire fix: exploration,
  editing, committing. No subagent is dispatched — no `Agent`/`Task` tool
  call, no `mill-implementer-*` spawn, no Agent-mode dispatch pattern.
  Whatever model the operator started this session with is the model that
  does the work; `mill-quick` has no tier/model-selection parameter.
- Runs `pipeline.done_gate` (the existing repo-wide test-suite command,
  `mill-config.yaml` `pipeline.done_gate`) as the verify step before
  marking the task done. This is a **hard precondition**: if
  `pipeline.done_gate` is unset/`null`, `mill-quick` halts immediately,
  before touching any file, with an error telling the operator to
  configure it first. `mill-quick` never proceeds with unverified work.
- On verify success: `_status.append_phase(status_path, "done", ts)`
  directly (mirrors mill-go's Handoff Step 1 exactly — no `set_done`
  helper exists in this codebase).
- On verify failure: `_status.set_blocked(status_path, reason, timestamp)`,
  then halt back to the operator. No retry loop, no self-fix rounds — a
  single attempt only.
- Writes an intermediate `phase: implementing` (existing enum value,
  already rendered correctly by `mill-status`) before starting work, so a
  concurrently-running `mill-status`/`mill-inspect` doesn't see a
  task frozen at `discussing` while `mill-quick` is actually working.
- Precondition checks before any edit: wiki `task['status'] == 'active'`
  (same gate as `mill-start` Phase: Select) and `status.md` `plan: null`
  (belt-and-suspenders confirmation of the `discussing`-only entry gate).
- Eligibility for using `mill-quick` at all is pure operator trust — no
  automatic size/complexity heuristic inside the skill. Invoking it is the
  decision, matching `mill-start`'s existing precedent of not
  second-guessing why the operator started a task a particular way.

**Out:**
- No `discussion.md`, no `plan/`, no `reviews/` — zero new files under
  `_mill/` beyond `status.md`'s own phase-timeline rows. The task's audit
  trail is the timeline plus the git commit(s), nothing else. (Any
  `_mill/plan/` content is deleted before merge regardless of pipeline
  used, so parity with the full-pipeline artifact set is not a goal.)
- No reviewer dispatch of any kind — no discussion-review, no plan-review,
  no code-review, no fixer round.
- No entry from any phase other than `discussing`. A task that has already
  gone through `mill-start` (`discussed` or later) cannot be fast-forwarded
  through `mill-quick` — the operator must choose the fast path at spawn
  time, not switch mid-pipeline.
- No retry/self-correction loop on verify failure — this is explicitly a
  single-shot skill; a failed attempt halts and hands back to the operator
  rather than looping.
- No changes to `mill-go`, `mill-plan`, or `mill-start` themselves —
  `mill-quick` is a new, independent entry point that happens to reuse
  `_status.py` helpers and the existing `pipeline.done_gate` config key.

## Decisions

### verify-mechanism

- Decision: Reuse the existing repo-wide `pipeline.done_gate` config key
  (`mill-config.yaml`) as `mill-quick`'s verify step — the same command
  mill-go's Handoff pre-done gate runs (`mill-go/SKILL.md` "0. Pre-done
  gate."). If `done_gate` is `null`/unset, `mill-quick` halts immediately
  with an error instructing the operator to configure it, before making
  any edit.
- Rationale: There is no per-task `verify:` command outside a plan.md
  batch structure, and `mill-quick` deliberately has no plan.md. Reusing
  `done_gate` needs zero new plumbing and zero new config schema. Making
  it a hard precondition (halt if null) preserves the brief's core safety
  claim — "a failing verify never gets marked done" — which would
  otherwise be silently unenforceable in a hub where `done_gate` isn't
  configured (confirmed: this hub's `mill-config.yaml` currently has
  `done_gate: null`).
- Rejected: A new per-invocation `verify:` argument (more precisely
  scoped, but adds a parameter surface and burdens the operator with
  specifying it correctly every call); no automated verify at all
  (fastest, but defeats the purpose of the done-gate reuse entirely).

### entry-phase-gate

- Decision: `mill-quick` only runs when `status.md` `phase: discussing`
  (mill-spawn's initial phase) and `plan: null`. Any other phase halts
  with an explanation that `mill-quick` must be invoked immediately after
  `mill-spawn`, before `mill-start`.
- Rationale: `mill-quick` is a full pipeline replacement, not a mid-stream
  shortcut. Restricting entry to the earliest possible phase keeps the
  "which pipeline am I on" decision a single up-front choice per task
  rather than something that can be switched mid-flight, which would
  create ambiguity about what state (partial discussion? partial plan?)
  is being discarded.
- Rejected: Allowing entry from any non-terminal phase (more flexible, but
  lets an operator abandon partial `mill-start`/`mill-plan` work
  implicitly, which is a much bigger and unstated decision than "skip
  review for a simple task"); restricting entry to `discussed` or later
  (would require `mill-start` to always run first, defeating the point of
  a fully collapsed fast path).

### single-inline-agent

- Decision: The entire fix (explore, edit, commit) is performed inline by
  the session that invoked `/mill-quick` — no subagent is spawned. There
  is no `Agent`/`Task` tool call, no Agent-mode dispatch envelope
  (prepare/finalize), no `mill-implementer-*` agent definition involved.
- Rationale: A running session cannot change its own model type mid-session
  — "which model does the fix" is already decided by whichever model the
  operator started this session with when they typed `/mill-quick`.
  Modeling this as a dispatch call (as mill-go does for its
  `mill-implementer-*` agents) would need a tier-selection parameter that
  has no meaningful value to select, since the model is already fixed by
  session start. This also means `mill-quick` needs none of mill-go's
  Agent-mode dispatch machinery (prepare/finalize envelopes, background
  polling, `millpy-bg`) — it is a linear script the orchestrating session
  runs top to bottom.
- Rejected: Dispatching one `mill-implementer-<tier>` subagent (mirrors
  mill-go's existing dispatch pattern and was the initial framing here,
  but the operator corrected it — the whole point is that the *current*
  session is the one agent, with the model already fixed by how the
  operator launched it).

### zero-artifacts

- Decision: No `discussion.md`, `plan/`, or `reviews/` files are written.
  The audit trail is `status.md`'s phase timeline (`discussing` →
  `implementing` → `done`/`blocked`) plus the fix commit(s).
- Rationale: These files exist elsewhere to let a review round or a
  fresh session reconstruct context with zero conversation history.
  `mill-quick` has no review round and no handoff to another session, so
  there is nothing that needs reconstructing. `_mill/plan/` content is
  deleted before merge regardless of which pipeline produced it, so
  parity with the full pipeline's artifact set was explicitly called out
  as unimportant.
- Rejected: A minimal stub `discussion.md` ("skipped via mill-quick") for
  audit-trail consistency with full-pipeline tasks — adds a file with no
  reader.

### failure-handling

- Decision: On `done_gate` failure (non-zero exit), call
  `_status.set_blocked(status_path, reason, timestamp)` and halt back to
  the operator. Single attempt only — no retry, no self-fix round.
- Rationale: `set_blocked` (rather than leaving `phase: implementing`
  unchanged) makes the stuck task visible to `mill-status`/`mill-cleanup`
  the same way any other blocked task is. A retry loop would reintroduce
  exactly the "fixer round" machinery the operator explicitly ruled out —
  "ONE AGENT DOES ALL. No fixer."
- Rejected: Leaving phase unchanged at `implementing` on failure (cheaper,
  but makes the stuck task invisible to other tooling that scans for
  `blocked`); an in-skill retry/self-fix loop (directly contradicts the
  single-agent, no-fixer design).

## Technical context

- Path resolution mirrors `mill-start`'s Entry/Path Setup exactly:
  `git_root = _paths.resolve_git_root()`, `worktree_root =
  _paths.resolve_hub_path()`, `status_path =
  _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`.
  `mill-quick` needs no `discussion_path`/`reviews_dir` resolution since it
  writes neither.
- Task read: `_client.get_task(wiki_path, slug)` — same call and same
  `PYTHONIOENCODING=utf-8` wrapping `mill-start` Phase: Select/Explore use,
  for the same cp1252-on-Windows reason documented there.
- `_status.py` helpers to reuse directly (already present, no new helper
  needed): `read(status_path)` / `read_status(status_path)` for the
  current phase, `append_phase(status_path, phase, timestamp)` for
  `implementing` → `done`, `set_blocked(status_path, reason, timestamp)`
  for the failure path.
- `pipeline.done_gate` execution should mirror mill-go's Pre-done gate
  exactly (`mill-go/SKILL.md` "0. Pre-done gate."): `subprocess.run(
  gate_cmd, cwd=git_root, shell=True, capture_output=True, text=True)`,
  non-zero exit → failure path.
- No changes needed to `mill-config.yaml`'s schema — `roles:` is a
  reviewer-round registry, not a skill registry; no mill-* skill is
  declared anywhere in YAML, so `mill-quick` requires no new config key to
  exist as a skill. It only *reads* the existing `pipeline.done_gate` key.
- Commit discipline should mirror the existing per-phase-transition commit
  pattern used throughout `mill-start`/`mill-go`: one commit for the
  actual fix (`git add` the changed files, message referencing the slug),
  a separate small commit for each `status.md` phase-timeline write
  (`implementing`, then `done` or `blocked`), each pushed immediately —
  matching every other mill skill's push-per-phase-commit discipline.
- `mill-merge`/`mill-finalize` require nothing beyond `phase: done` in
  `status.md` (`mill-merge/SKILL.md`, `mill-finalize/SKILL.md`) — neither
  references `discussion.md` or `plan/` existence anywhere, so a
  `mill-quick`-completed task hands off to them unmodified.
- No existing precedent in this codebase for a single-agent
  implement+verify skill with no reviewer split — every current
  `mill-implementer-*` dispatch in `mill-go` is unconditionally followed
  by a code-review loop. `mill-quick` is the first skill of this shape;
  mill-plan should not assume any existing dispatch helper covers this
  case.

## Constraints

No `CONSTRAINTS.md` present at the hub root beyond the general path,
worktree-isolation, and wiki-access rules already enforced repo-wide (see
`CLAUDE.md`) — no task-specific constraints beyond what's captured under
Decisions above.

## Testing

- `_status.py` interactions (`append_phase`, `set_blocked` calls with the
  right phase strings and ordering) are unit-testable the same way
  existing `_status.py` behavior is tested — no real git/LLM needed.
- The `done_gate`-null precondition (halt before any edit, no file
  touched) is a TDD candidate: a fixture with `done_gate: null` must
  produce a halt with zero filesystem side effects.
- The entry-phase gate (`phase != discussing` or `plan != null` → halt) is
  a second TDD candidate, mirroring how `mill-plan`/`mill-go`'s own
  entry-gate checks are tested today.
- The done-gate subprocess invocation itself (success path → `phase:
  done`; failure path → `phase: blocked` with `set_blocked`'s reason
  populated) should be covered with a fake `done_gate` command (e.g.
  `exit 0` / `exit 1`) rather than a real test suite, consistent with
  `integration_tests/`'s existing use of `.scratch/` fixtures over real
  external processes for deterministic branches.
- End-to-end (real git, a trivial fixture task, a real `done_gate` command
  that both passes and fails) belongs in `integration_tests/`, matching
  the existing split between `unit_tests/` (fixtures only) and
  `integration_tests/` (real git, optionally real claude).

## Q&A log

- **Q:** Where does mill-quick source its verify command from, given
  there's no plan.md? **A:** Reuse the existing repo-wide
  `pipeline.done_gate` config key — the same command mill-go's Handoff
  pre-done gate already runs. Confirmed as a hard requirement: mill-quick
  must actually run the test suite, so a `null` done_gate halts the skill
  entirely rather than silently skipping verification.
- **Q:** Which status.md phases can mill-quick start from? **A:** Only
  `discussing` (mill-spawn's initial phase) — "only from the start."
  mill-quick replaces mill-start/mill-plan/mill-go entirely for eligible
  tasks; it is not a mid-pipeline shortcut.
- **Q:** Who performs the fix — a dispatched subagent or the invoking
  session itself? **A:** The invoking session itself, inline, with no
  subagent dispatch. A running session can't change its own model type,
  so "one agent does everything" means the session the operator already
  started (with whatever model they chose) does the whole job — there is
  no tier/model-selection parameter to design, and no
  "spawned implementer" concept at all.
- **Q:** Do the `_mill/` artifacts (discussion.md, plan/) matter for
  parity with the full pipeline? **A:** Not important — `_mill/plan/`
  content gets deleted before merge regardless of which pipeline produced
  it, so mill-quick writing zero artifacts is fine.
- **Q:** On done_gate failure, does status.md get `phase: blocked` or is
  the phase left unchanged? **A:** `phase: blocked` via `set_blocked`, so
  the stuck task is visible to `mill-status`/`mill-cleanup` like any other
  blocked task.
- **Q:** Is there an intermediate phase while the single session is
  working? **A:** Yes — `phase: implementing` (an existing, already-
  rendered enum value) is written before work starts, so a concurrent
  `mill-status` read doesn't show the task frozen at `discussing`.
- **Q:** Any automatic eligibility/size heuristic gating use of
  mill-quick? **A:** No — pure operator trust, matching mill-start's
  existing precedent of not second-guessing why the operator started a
  task a particular way.
