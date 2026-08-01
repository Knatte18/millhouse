# Discussion: Non-interactive pipeline — mill-plan and mill-go always run autonomously

```yaml
task: Non-interactive pipeline: only mill-start's interview may prompt the operator
slug: pipeline-walkaway-mode
status: discussing
parent: main
```

## Problem

Today, `mill-plan` and `mill-go` stop and wait for an operator reply at many
points that don't need a human — a numbered-options prompt is still a stop,
even though `mill:conversation`'s "numbered options, no `AskUserQuestion`"
rule only changed the *shape* of the prompt, not whether it blocks. The only
place operator presence should be required is mill-start's initial interview
(Phase: Discuss). Everything after that — mill-plan's plan-review loop,
mill-go's batch and holistic review loops — should resolve routine decisions
itself and keep going, so an operator can kick off the pipeline and walk
away.

This is not about auto-picking a "Recommended" option from a menu. It is
about **not building the menu at all** for anything with an obvious
resolution: mill-plan and mill-go must always be autonomous, unconditionally
— there is no interactive/autonomous mode distinction for these two skills
after this task. Only conditions that are genuinely serious (a BLOCKED
verdict after exhausting retries, a failed done-gate, external state the
agent cannot safely touch) still halt and wait for the operator.

## Scope

**In:**
- `mill-plan/SKILL.md` — collapse the interactive/`autonomous_mode` branches
  in the Non-progress check and Max-rounds escape into always taking the
  "halt cleanly via `_status.set_blocked`" path (both are exhausted-retries
  signals — see Decisions).
- `mill-go/SKILL.md` — for every `stuck_type` / holistic-REQUEST_CHANGES /
  rate-limit / rounds-exhausted site, either (a) collapse to the halt path
  unconditionally (Stuck-escalation `verify`/`logic`, rate-limit-exhausted,
  holistic-rounds-exhausted), or (b) give the site new one-shot
  self-resolve logic where none exists today (`transient` no-commits,
  `verify`/`logic` on first occurrence, holistic `transient`/`verify`/
  `logic` — the gap found during discussion — and the three Handoff
  cleanup gates: nits, dirty tree, scope violations). The pre-done-gate
  check (actual `done_gate` command failure) stays a hard halt unchanged.
- `mill-merge/SKILL.md` / `scripts/_inplace.py` — the stale-worktree
  ambiguity (`prompt_stale_worktree`, a raw `input()` call) gets replaced
  with the agent investigating git state itself before falling back to
  abort-and-halt.
- Delete `pipeline.autonomous_mode` (config key, all read sites in
  mill-plan/mill-go, the write site in mill-autofix, its Phase 2
  pre-flight and Phase 4 cleanup-restore block) and delete
  `scripts/_autonomous.py` + `unit_tests/test-autonomous.py` (dead code,
  zero callers — confirmed by grep).
- Update `unit_tests/_test_cfg.py:62` and `unit_tests/test-config.py:599`,
  which reference the `autonomous_mode` fixture key, to match its removal.
- Every self-resolve action logs a `_status.append_phase`-style timeline
  row in `status.md` so the operator can review what was auto-decided
  after the fact.

**Out:**
- mill-start's own interview (Phase: Discuss) — stays interactive, always.
  This is the one place operator presence is required.
- mill-start's own `--auto` mode for its Discussion Review round — this is
  a separate, already-implemented, already-correct mechanism
  (`mill-start/SKILL.md` lines 13-41) and is not touched by this task.
- `pipeline.auto_merge` / `git.require_pr_to_base` — mill-go's Handoff
  step 5 (`mill-go/SKILL.md:966`) and mill-finalize's PR-vs-direct dispatch
  already implement exactly the desired behavior (`auto_merge: false` →
  mill-go stops and tells the operator to run `/mill-finalize` manually;
  `require_pr_to_base: true` → mill-finalize creates the PR and halts at
  its Step 7 waiting for review). No change.
- mill-merge's other halts: PR-still-open (`M3`, external GitHub state),
  dirty-parent-worktree (`M4`, agent isn't allowed to touch the parent
  worktree per the worktree-isolation rule), merge-lock timeout (`M6`,
  external process contention), missing `parent:` row in status.md (`M2`,
  a genuine mill-spawn setup bug, not a judgment call). All four stay
  exactly as they are.
- Any new opt-in flag or trigger mechanism. This is unconditional default
  behavior for mill-plan/mill-go, not something an operator switches on.

## Decisions

### unconditional-default-not-a-flag

- Decision: Self-resolving behavior is the *only* behavior for mill-plan
  and mill-go — there is no flag, no config key, and no distinction
  between "interactive" and "autonomous" sessions for these two skills
  after this task. `pipeline.autonomous_mode` and `_autonomous.py` are
  deleted, not repurposed.
- Rationale: `_autonomous.py`'s flag-file API (`is_autonomous`/
  `set_autonomous`/`clear_autonomous`, `<hub>/.millhouse/autonomous.flag`)
  has zero callers anywhere in `scripts/` or `skills/` (confirmed via
  grep, independently verified twice). Its docstring claims it "replaces
  the removed `pipeline.autonomous_mode` config key" — that claim is
  false; the config key is very much alive and is what mill-plan/mill-go
  actually read today. Extending either mechanism with a new opt-in
  would just add a second flag on top of dead scaffolding. The task's
  own premise — "operator starts the pipeline and walks away" — means
  this must be the default, not something requiring an extra step to
  enable.
- Rejected: Resurrecting `_autonomous.py`'s flag file. Adding a new
  `pipeline.walkaway_mode` key. Both add indirection for no behavioral
  benefit once the target behavior is unconditional.

### still-halts-collapses-to-todays-autonomous-branch

- Decision: For every site that stays a genuine halt (see the "Stays a
  genuine halt" list below), the fix is almost always just deletion —
  keep today's `pipeline.autonomous_mode: true` branch's behavior
  (`_status.set_blocked`, commit, push, clear halt message) as the *only*
  branch, and delete the "interactive, wait for a numbered reply" branch
  next to it. mill-plan/mill-go never wait live for a reply again; they
  either resolve something themselves or set `blocked` and stop.
- Rationale: Nearly every genuine-halt site already has a fully-specified
  autonomous-mode branch written today (it just isn't the default path).
  Reusing it verbatim is both correct and far less work than inventing new
  halt behavior.
- Rejected: Writing new halt logic from scratch — unnecessary, the
  existing autonomous-mode branches at each of these sites are already
  correct.

### self-resolve-then-escalate-on-repeat

- Decision: Sites with no existing autonomous-mode branch (mill-go's
  `stuck_type: verify`/`logic` on first occurrence, `transient` with no
  commits, holistic `transient`/`verify`/`logic`, and the three Handoff
  cleanup gates) get new one-shot self-resolve logic: the agent
  investigates/fixes/retries once using its own judgment (same tools an
  implementer or fixer already has — Read/Edit/Bash/plan-editing), logs
  what it did as a status.md timeline row, and continues. If the *same*
  failure recurs after that one self-resolve attempt, it escalates to
  the genuine-halt path (`_status.set_blocked`) — this mirrors the
  existing one-retry shape already used for `transient`/`infrastructure`
  (re-invoke once, block on repeat), just applied to sites that didn't
  have it. The pre-done-gate check itself (an actual failing `done_gate`
  command) is the one Handoff-adjacent case that stays a hard, immediate
  halt — no self-resolve attempt, because the plan-writer must decide
  which handoff gates get a self-resolve pass in the plan (e.g. nits: run
  the NIT-fix pass; dirty tree: commit or clean; scope violations: decide
  in/out of scope) and which fixed one-shot action applies to each.
- Rationale: This is what "de skal fikse selv" means concretely — not
  auto-picking a menu option, but actually doing the fix (editing the
  plan, re-running a batch, cleaning the tree) the way a present operator
  would have told it to, then proceeding. A second consecutive failure on
  the same thing is a real stuck signal (matches the task proposal's
  named "stuck-escalation that has already exhausted its retries"
  exception) and should still surface to the operator.
- Rejected: Retrying indefinitely without ever halting (risks infinite
  loops / silent divergence — explicitly rejected by the existing
  rate-limit-fallback halt's own rationale, "silent infinite fallback is
  wrong", which this task keeps). Halting immediately on first occurrence
  without attempting self-resolve (defeats the point of this task).

### stays-a-genuine-halt-list

- Decision: The following sites keep halting and waiting for the
  operator, unconditionally, mapped against the task proposal's own three
  named exceptions (BLOCKED verdict / failed done-gate / exhausted
  stuck-escalation):
  - mill-plan Non-progress check (`SKILL.md:332`) — two consecutive
    rounds with an identical non-empty `## Pushed Back` set; a stable
    reviewer/fixer disagreement, not resolvable by retrying.
  - mill-plan Max-rounds escape (`SKILL.md:334-341`) — round cap
    exhausted with BLOCKING findings remaining.
  - mill-go Stuck escalation `verify`/`logic`, second occurrence
    (`SKILL.md:604`, reached via the new self-resolve-then-escalate path
    above) and `incomplete` after the resume already attempted
    (`SKILL.md:603`, already correctly auto-resumes once today, keep
    as-is).
  - mill-go rate-limit-exhausted-with-no-fallback-configured
    (`SKILL.md:831`) — no reviewer available to fall back to; nothing to
    self-resolve.
  - mill-go holistic-rounds-exhausted (`SKILL.md:869-874`) — exhausted
    retries at the holistic level, same shape as mill-plan's max-rounds.
  - mill-go Handoff pre-done-gate failure specifically
    (`SKILL.md:921-948`) — this is the literal "failed done-gate" named
    exception.
  - mill-merge: PR-still-open (`SKILL.md:97-99`), dirty-parent-worktree
    (`SKILL.md:169-173`), merge-lock timeout (`SKILL.md:120-122`),
    missing `parent:` row (`_parent_branch.resolve`, already supports
    `interactive=False` → raises a clean error instead of blocking
    stdin — mill-merge should call it that way and turn the exception
    into a `_status.set_blocked` halt, matching the pattern used
    elsewhere).
- Rationale: each represents either external state the agent cannot
  safely resolve (GitHub PR state, another process's lock, the parent
  worktree it isn't allowed to touch) or a stable failure signal where
  another automatic attempt has already been shown not to help.
- Rejected: Self-resolving any of these — would risk silently shipping
  broken state (done-gate), corrupting shared/external state (PR,
  parent worktree, lock), or looping forever on a disagreement that
  isn't going to resolve itself.

### stale-worktree-self-investigates

- Decision: `_inplace.prompt_stale_worktree` (raw `input()` call, fires
  when the current branch matches the recorded task branch AND a
  worktree dir already exists at the target path) is replaced with the
  agent checking `git worktree list` / the worktree's git state itself to
  determine which case it actually is, and proceeding accordingly. Only
  fall back to the existing abort-and-halt if the ambiguity remains after
  checking.
- Rationale: This is a genuinely investigable local-git-state question,
  not an external system and not a stable disagreement — well within an
  agent's own tools. Today's "Abort (Recommended)" default is a safe
  fallback for a *human* who doesn't want to inspect git state manually;
  an agent can just inspect it.
- Rejected: Leaving this as a blocking `input()` call — this is exactly
  the "stop and ask about something with an obvious answer" pattern the
  operator explicitly called out, just implemented as a raw stdin prompt
  instead of a conversational one. Same failure mode, needs the same fix.

### no-new-permission-prompting-tool-calls

- Decision: Any new or rewritten self-resolve logic in mill-plan/mill-go
  must stick to non-interactive, non-permission-prompting tool calls
  (Read/Edit/Write/Grep/Bash with non-interactive commands) — never
  `sed` or any other command that triggers a Claude Code permission
  prompt for something with an obvious resolution.
- Rationale: A tool-permission prompt is the same "pipeline stops and
  waits" failure this task exists to eliminate, just triggered by the
  harness instead of by an explicit question. This repo already bans
  `sed` project-wide, explicitly including "any script/prompt it
  generates for a dispatched sub-agent (implementer/reviewer/fixer)"
  (`CLAUDE.md`, commit `64adbbf6`) — this decision just makes explicit
  that the ban applies to whatever this task writes too.
- Rejected: N/A — this is a restatement of an existing binding project
  rule, not a new option to weigh.

### audit-trail-via-status-timeline

- Decision: Every self-resolve action appends a
  `_status.append_phase(status_path, "<short-reason>", timestamp)`-style
  row to status.md's existing timeline — no new dedicated field or
  section.
- Rationale: This is the mechanism every other phase transition in
  mill-plan/mill-go already uses; reusing it means the operator reviews
  auto-decisions the same way they review everything else that happened
  while they were away, with no new place to look.
- Rejected: A separate "Auto-decisions" section in status.md — pure
  duplication of a mechanism that already exists and is already the
  audit trail for everything else.

## Technical context

**Dead code to delete:**
- `plugins/mill/scripts/_autonomous.py` (whole file — `is_autonomous`,
  `set_autonomous`, `clear_autonomous`, backed by
  `<hub>/.millhouse/autonomous.flag`; zero callers anywhere in `scripts/`
  or `skills/`, confirmed by grep excluding the definition file itself).
- `plugins/mill/unit_tests/test-autonomous.py` (82 lines, tests only the
  dead module above).

**`pipeline.autonomous_mode` config key — every site to remove:**
- `plugins/mill/templates/mill-config.yaml:122` — the key itself
  (`autonomous_mode: false  # Set true by mill-autofix; read by mill-go
  and mill-plan for autonomous stuck-handling`).
- `plugins/mill/skills/mill-plan/SKILL.md:332` (Non-progress check) and
  `:334` (Max-rounds escape) — both read the key to choose between the
  interactive-wait branch and the halt branch; collapse to always the
  halt branch (see Decision `still-halts-collapses-to-todays-autonomous-branch`).
- `plugins/mill/skills/mill-go/SKILL.md` — reads at lines `588`, `590`,
  `598`, `603`, `831`, `833`, `862`, `869`. Each site's existing
  `autonomous_mode: true` branch becomes the unconditional behavior;
  the sibling interactive branch is deleted. Lines `591`/`600` (`transient`
  no-commits) and `862`-`864` (holistic `transient`/`verify`/`logic` — the
  gap found during discussion: these three currently have **no**
  `autonomous_mode` branch at all, unlike the sibling `infrastructure`
  branch one line above at `862`) need new self-resolve logic written
  (Decision `self-resolve-then-escalate-on-repeat`), not just a
  collapse.
- `plugins/mill/skills/mill-autofix/SKILL.md` — Phase 2 pre-flight
  (lines `85-120`, "enable autonomous mode": reads/writes
  `.millhouse/config.local.yaml` to set `autonomous_mode: true`) and the
  matching cleanup/restore block around lines `400-419` (`original_cfg_text`
  save/restore) both become dead once mill-plan/mill-go no longer read
  the key — remove Phase 2 entirely and simplify the cleanup phase
  accordingly. Also remove the reference at line `10`
  ("`pipeline.autonomous_mode: true` is a temporary mutation... must be
  restored on every exit path").
- `plugins/mill/unit_tests/_test_cfg.py:62` and
  `plugins/mill/unit_tests/test-config.py:599` — fixture/test references
  to the `autonomous_mode` key; update to match its removal from the
  schema.
- `plugins/mill/skills/mill-start/SKILL.md:41` — documentation-only
  touch. The line currently reads "`--auto` is independent from
  `pipeline.autonomous_mode`: ... `pipeline.autonomous_mode` is a config
  key controlling mill-go's stuck-handling... Operators opt into each
  separately." This becomes factually wrong once the key is deleted and
  mill-go has no opt-in left at all. Reword to state that mill-start's
  `--auto` remains its own separate mechanism, without describing the
  now-deleted key's semantics. This is the only edit inside mill-start's
  Auto mode section (lines 13-41) — the rest of that section (the actual
  `--auto` behavior) stays untouched, per Scope's "Out" list.

**mill-plan/SKILL.md exact sites:**
- Line `332`, Non-progress check: today branches on
  `pipeline.autonomous_mode: true` to skip a (nonexistent — there is no
  numbered prompt here today, just two different halt-message shapes)
  prompt and go straight to `_status.set_blocked(status_path, f"non-progress
  round {N}", ...)`. Make this the only path, always.
- Lines `334-341`, Max-rounds escape: today branches on
  `pipeline.autonomous_mode: true` to skip the 3-option numbered prompt
  (`Deep problems` / `Shallow — one more round` / `Override`, computed
  Recommended) and go straight to `_status.set_blocked(status_path,
  f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain", ...)`.
  Make this the only path, always; delete the numbered-prompt branch and
  its "wait for the user's choice" text entirely.

**mill-go/SKILL.md exact sites (`### Stuck escalation`, lines
`586-605`; `## Holistic code review` sub-steps `3.6`/`4`/`5`/`7`, lines
`819-874`; `## Handoff`, lines `876-948`):**
- `588`: the top-level `autonomous_mode: true` branch gate — becomes
  unconditional (delete the `if`, keep the body).
- `590` (`infrastructure`): already-correct auto-retry-once-then-block
  shape; make unconditional, delete the "interactive" sibling branch.
- `592-599` (`transient`, `commits_made > 0`): already-correct
  auto-pick-skip-to-cleanliness shape; make unconditional.
- `600` (`transient`, no commits / timeout before first commit): **no
  existing autonomous branch** — new self-resolve logic needed (e.g.
  retry fresh once using the agent's own judgment about what likely
  caused the timeout; escalate to halt if it recurs).
- `601-603` (`incomplete`): the interactive branch already resumes once
  before escalating; the `autonomous_mode: true` branch does the same
  thing with a `_status.set_blocked` on second failure. These converge
  in behavior already — just delete the interactive branch's
  three-option prompt on the escalated case and keep the
  `autonomous_mode` branch's, unconditionally.
- `604` (`verify`/`logic`, first occurrence): **no existing autonomous
  branch** — new self-resolve logic needed (edit the plan / investigate
  and retry once, using the same judgment a human would have applied
  picking "edit plan and retry"; escalate to halt if it recurs on the
  same batch).
- `819-833` (Rate-limit fallback): `831`'s `autonomous_mode: true` +
  no-fallback-configured branch already halts correctly — keep, make
  unconditional (it already reads as "halt" either way here, so this is
  a light touch: just drop the flag check, the behavior doesn't change).
  `833`'s "operator interactive path" note becomes obsolete — delete.
- `862` (holistic `infrastructure`): already-correct auto-retry-once
  shape; make unconditional.
- `863` (holistic `transient`): **no existing autonomous branch** — new
  self-resolve logic needed, same one-shot-retry-then-escalate shape as
  `600`.
- `864` (holistic `verify`/`logic`): **no existing autonomous branch** —
  new self-resolve logic needed, same shape as `604`.
- `869-874` (holistic rounds exhausted): `869`'s `autonomous_mode: true`
  branch already halts correctly via `_status.set_blocked` +
  `blocked_reason`; make unconditional, delete the 3-option interactive
  prompt (`870-874`) entirely.
- `886-888` (Nit-enforcement gate): **no existing autonomous branch** —
  today just halts with `BLOCKED: unfixed nits...`. New self-resolve
  logic: dispatch the NIT-fix pass itself (the same pass already
  documented and invoked elsewhere in this file, e.g. around lines
  `528-533` and `840-851`) before reaching this gate, rather than halting
  when it finds unfixed nits.
- `894-903` (Terminal cleanliness gate): **no existing autonomous
  branch** — today halts with `BLOCKED: dirty working tree...`. New
  self-resolve logic: commit the in-scope dirt itself (it's the agent's
  own uncommitted work on the task branch) before reaching this gate.
- `907-915` (Scope violations cleanup gate): note `_cleanliness
  .clean_ephemeral_scope_violations` already auto-removes ephemeral
  build artifacts and only halts on `blocking_paths` (genuinely
  ambiguous untracked files) — **no existing autonomous branch** for the
  `blocking_paths` case. New self-resolve logic: agent decides per-file
  whether it's in-scope work (commit it) or leftover cruft (remove it),
  using the plan/discussion to judge scope, and logs the call.
- `921-948` (Pre-done gate: actual `done_gate` command failure) — stays
  exactly as-is, hard halt, no self-resolve attempt (Decision
  `stays-a-genuine-halt-list`).

**mill-merge / `_inplace.py` / `_parent_branch.py`:**
- `plugins/mill/scripts/_inplace.py:62-102`,
  `prompt_stale_worktree(slug, worktree_path) -> str` — raw `input()`
  call, defaults to `"abort"` on invalid/EOF input. Replace the call
  site in `mill-merge/SKILL.md:21-23` with agent-driven investigation
  (`git worktree list`, check the worktree's actual state) before
  falling back to the existing abort-and-halt.
- `plugins/mill/scripts/_parent_branch.py:87-129`, `resolve(status_path,
  *, interactive=True, expected_slug=None) -> str` — already supports
  `interactive=False`, which raises `ParentBranchError` instead of
  blocking on stdin (used already by mill-finalize at
  `mill-finalize/SKILL.md:34`). mill-merge's own call site
  (`SKILL.md:45`) should use `interactive=False` too and turn a caught
  `ParentBranchError` into a `_status.set_blocked` halt with the
  exception's message, rather than ever calling with `interactive=True`.

**Already correct, no change needed:**
- `mill-go/SKILL.md:966` (Handoff step 5) — `pipeline.auto_merge`
  gating whether `/mill-finalize` is invoked at all.
- `mill-finalize/SKILL.md:32-39` (Dispatch) — `git.require_pr_to_base`
  choosing PR-mode vs direct-mode.
- `mill-finalize/SKILL.md:131-139` (PR Steps, Step 7) — halts after PR
  creation, exactly matching "if require_pr_to_base is true, mill-go
  should halt when the PR is ready."

## Constraints

- `sed` is banned project-wide for anything this task writes or any
  script/prompt it generates for a dispatched sub-agent — see Decision
  `no-new-permission-prompting-tool-calls`.
- Worktree isolation: self-resolve logic must never edit files in or
  `cd` into the parent worktree (this is why `M4`, dirty-parent-worktree,
  stays a genuine halt rather than something the agent cleans up itself).
- `print()`/`_log()` output stays ASCII-only per project convention
  (`—` → ` -- `, `->` stays `->`) — applies to any new status/log
  messages this task's self-resolve paths emit.
- No new config key or flag — see Decision
  `unconditional-default-not-a-flag`.

## Testing

- `plugins/mill/unit_tests/test-autonomous.py` — delete (tests the
  deleted `_autonomous.py`).
- `plugins/mill/unit_tests/_test_cfg.py:62`,
  `plugins/mill/unit_tests/test-config.py:599` — update fixtures that
  reference the removed `autonomous_mode` config key; re-run
  `run-all.py` after to confirm nothing else depended on it.
- No new unit-testable logic is introduced by the SKILL.md prose changes
  themselves (these are Claude-Code-interpreted instructions, not
  Python), but any new helper functions the plan chooses to extract for
  self-resolve decisions (e.g. a git-state check for the stale-worktree
  case, a scope-violation classifier) are TDD candidates in the existing
  `unit_tests/` style (in-memory/tempfile fixtures, no real git/LLM).
- No integration-test changes anticipated — `integration_tests/` invokes
  real git and optionally real claude; verify none of the mill-plan/
  mill-go/mill-merge integration tests currently assert on the
  interactive-prompt branches being taken (they would need updating to
  assert the new unconditional self-resolve behavior instead, if so).

## Q&A log

- **Q:** Is `_autonomous.py`'s flag file the mechanism to build on, per
  the task proposal? **A:** No — confirmed by grep that it has zero
  callers anywhere in `scripts/` or `skills/`. The live mechanism is
  `pipeline.autonomous_mode`, already wired through mill-plan and
  mill-go's stuck-escalation paths. `_autonomous.py` is dead code with a
  misleading docstring; delete it.
- **Q:** Should the config-key comment flagged as "stale" in the
  original proposal (`autonomous_mode: false  # Set true by
  mill-autofix; read by mill-go and mill-plan`) be cleaned up as a
  side-note? **A:** That comment is accurate, not stale — it's
  `_autonomous.py`'s own docstring (claiming the key was "removed") that
  is wrong. Moot either way since this task deletes the key entirely.
- **Q:** Should mill-plan/mill-go self-resolve via an "auto-pick the
  Recommended numbered option" mechanism? **A:** No — that framing was
  rejected explicitly. There is no menu to auto-pick from; mill-plan and
  mill-go must be instructed that asking about routine, obviously-
  resolvable situations is not allowed at all — they resolve it
  themselves (edit the plan, retry, fix nits, clean the tree) using
  their own judgment, the same way an implementer/fixer sub-agent
  already operates.
- **Q:** Is mill-merge in scope? **A:** Only for the stale-worktree
  ambiguity (`M1`, a raw `input()` call, not an LLM prompt) and the
  parent-branch-resolution call shape (`M2`, switch to
  `interactive=False` + halt-on-exception like mill-finalize already
  does). The four other mill-merge halts (PR-still-open, dirty-parent-
  worktree, merge-lock timeout, missing `parent:` row) and the
  `auto_merge`/`require_pr_to_base`-driven merge decision itself are
  untouched — confirmed already correct: `auto_merge: false` → mill-go
  halts before invoking mill-finalize; `require_pr_to_base: true` →
  mill-finalize halts after creating the PR, waiting for the operator.
- **Q:** What about tool-permission prompts (e.g. `sed`) as a separate
  "stop and ask" mechanism? **A:** Already covered by the existing
  project-wide `sed` ban (`CLAUDE.md`, commit `64adbbf6`), which
  explicitly includes scripts/prompts generated for dispatched
  sub-agents. This task's own new code must not introduce any new
  permission-prompting tool calls — restated as a binding constraint,
  not a new decision to make.
- **Q:** Does "always autonomous" apply even to a manually-started,
  operator-watching `/mill-plan` or `/mill-go` session? **A:** Yes — per
  the task's own premise, mill-plan and mill-go are always autonomous
  regardless of who started the session or whether anyone is watching.
  There is no interactive mode left for these two skills.
