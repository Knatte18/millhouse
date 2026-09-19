# Turn-reduction audit: mill-start / mill-plan / mill-go-base

```yaml
source: turn-reduction-audit task, _mill/discussion.md
```

Classifies every step of `mill-start/SKILL.md`, `mill-plan/SKILL.md`, and `mill-go-base/SKILL.md`
as **Mechanical/collapsible**, **Borderline**, or **Excluded**, so a follow-up task can mechanize
the deterministic shapes into single script calls without touching anything that still needs to
stay a visible, interruptible turn.

## Scope

**In:** every numbered step and every `### Phase:`/`###`-level heading in
`plugins/mill/skills/mill-start/SKILL.md`, `plugins/mill/skills/mill-plan/SKILL.md`, and
`plugins/mill/skills/mill-go-base/SKILL.md`. Also: confirming whether
`plugins/mill/skills/mill-go/SKILL.md` and `plugins/mill/skills/mill-go2/SKILL.md` add any step
sequences of their own beyond loading `mill-go-base`.

**Out (explicitly, not silently):** `plugins/mill/skills/mill-merge/SKILL.md`,
`plugins/mill/skills/mill-finalize/SKILL.md`, and every other skill. The task's background section
cites `mill-merge`'s 8-9-step shape only as a *motivating example* for why this problem matters
elsewhere in the repo — the task's own "What needs to happen" section names only
`mill-start`/`mill-plan`/`mill-go-base` (+ `mill-go`/`mill-go2`) as audit targets. Auditing
`mill-merge` or any other skill is a separate future task. Implementing any candidate below is also
out of scope for this task — see `## Cross-cutting recommendations` and `## Follow-up backlog
candidates`.

## Methodology

Three buckets, taken verbatim from the task body and `_mill/discussion.md`'s "Classification
scheme" Decision:

- **Mechanical/collapsible** — deterministic, no judgment call, no Agent dispatch, no
  operator-facing halt/prompt in between. A candidate for a single script call.
- **Borderline** — mechanical on paper but entangled with a halt message, an operator-visible
  phase name, or brackets an Agent dispatch. Needs explicit design treatment, never a blind
  collapse.
- **Excluded** — genuine LLM reasoning, judgment, Agent dispatch, or a round-by-round loop per
  `plugins/mill/skills/workflow/SKILL.md`'s anti-pattern #2 ("Don't write wrapper scripts for
  orchestration loops the SKILL.md describes inline").

**Mechanical/collapsible entries** record four fields: step range, current per-step behavior,
whether the mechanical work is already scripted per-step (so the only win is collapsing N
script-invoking turns into 1) or involves un-scripted logic, and a rough per-run turn-count saving.

**Borderline entries** record two alternatives — full exclusion (leave the step sequence entirely
as orchestrator-driven text) and a scoped partial collapse (a script call does only the
deterministic read+classify work and returns a JSON blob; the SKILL.md keeps ownership of the
actual halt-message text, the operator-facing phase name, and the decision of which named branch to
take) — plus an explicit recommendation between them. Never a single forced verdict, per
`_mill/discussion.md`'s "Borderline treatment" Decision.

## mill-start

`plugins/mill/skills/mill-go/SKILL.md` (29 lines) and `plugins/mill/skills/mill-go2/SKILL.md` (105
lines) add no mechanical step sequences of their own: `mill-go` is a bare load-`mill-go-base`-and-
follow wrapper (its own "## Driver preamble" and "## Dispatch overrides" sections are both `(none)`).
`mill-go2` only overrides the implementer/fixer dispatch calls with fork/cold-fallback branching
logic — judgment about when to fork vs. fall back cold, not a mechanical read/write/branch shape —
and preloads a fixed skill set once per session in its "## Driver preamble" (a single Skill-tool
batch, not a repeated shape). Both files were re-read for this audit (not copied from
`_mill/discussion.md`'s prior confirmation on faith) and confirm the same conclusion.

- **Entry Step 0** (lines 81-83) — load `mill:prose`/`mill:conversation` via the Skill tool —
  **Excluded**. A Skill-tool load is not a scriptable Python call; the tool call itself is the
  mechanism.
- **Entry step 1** (lines 85-89) — resolve `git_root`/`wiki_path` via `_paths` calls — **Mechanical/
  collapsible**. Current behavior: two sequential `_paths` calls with no branching. Already scripted
  per-step (each is one function call); the only win is collapsing 2 script-invoking reads into 1.
  Rough saving: ~1 turn.
- **Entry step 2** (lines 90-92) — deep-merge config, read two `rounds`/`min_rounds` keys —
  **Mechanical/collapsible**. Deterministic config read, no judgment. Already scripted
  (`_config.load_config`); saving ~1 turn when combined with steps 1 and 3.
- **Entry step 3** (lines 93-95) — resolve slug via `_marker.slug_from_branch`, halt on
  `MarkerError`, report the slug string to the user — **Mechanical/collapsible**. The halt is a
  fixed, non-branching error path (no operator-facing choice), so it stays Mechanical rather than
  Borderline. Already scripted; saving ~1 turn.
- **Path Setup** (lines 97-107) — derive `worktree_root`/`status_path`/`discussion_path`/
  `reviews_dir` from already-bound `cfg` — **Mechanical/collapsible**. Pure deterministic path
  arithmetic, already expressed as scripted `_paths` calls.
  - **Combined candidate:** Entry steps 1-3 + Path Setup (lines 85-107) are one natural collapse
    unit — a single script call resolving every path/config value mill-start needs before Phase:
    Color ever runs, mirroring the identical shape already flagged for `mill-plan`'s and
    `mill-go-base`'s own Entry sequences (see `## mill-plan` and `## mill-go-base` below). Current
    per-step behavior: 4 separate reads across 3 numbered steps plus an unlabeled Path Setup block,
    each currently issued as its own tool call. Already-scripted-per-step: yes, every sub-call is an
    existing helper function; nothing here is un-scripted logic. Rough turn-count saving: ~4 turns
    collapsed to 1.
- **Auto mode** (lines 17-60) — per-invocation flag governing Discuss/Discussion-Review behavior
  under `--auto` — **Excluded**. Every rule here is either a judgment override (FIX-everything
  decision-tree substitution) or governs a round-by-round loop (non-progress/extension machinery),
  squarely the anti-pattern #2 shape.
- **Orch mode** (lines 62-77) — `--orch` flag layering a human-substitute round-1 review plus a
  two-consecutive-APPROVEs convergence gate — **Excluded**. Judgment/branching logic (which skill to
  load for round 1, when convergence is satisfied), not a deterministic read/write/branch.
- **Phase: Color** (lines 115-121) — read `.vscode/settings.json`, map a color, tell the user a
  `/color` hint or skip silently — **Mechanical/collapsible**. Current behavior: one file read, one
  fixed-table lookup, one conditional print. Un-scripted today (no helper module backs this phase);
  a new small script call would collapse it. Rough saving: ~1 turn.
- **Phase: Select** (lines 123-147) — query the wiki via a `PYTHONIOENCODING=utf-8`-prefixed Python
  one-liner, parse the `STATUS:` line, halt if not `"active"` — **Mechanical/collapsible**. Current
  behavior: this phase is *already* a single Bash-tool invocation (one inline script) — no further
  turn-count collapse is possible; the status gate itself is deterministic. Already scripted
  per-step; rough saving: ~0 turns (already at the 1-turn floor).
- **Phase: Active** (lines 149-153) — verify `status_path` exists and `parent:` is recorded, "no
  edit needed here" — **Mechanical/collapsible**. Trivial existence/field check with no judgment;
  un-scripted today (no dedicated helper), but the win is marginal since it is a single read.
  Rough saving: ~0-1 turns.
- **Phase: Explore, Step 1** (lines 157-166) — fetch the task document via `_client.get_task`,
  read `task['body']` in full — **mixed**. The fetch itself (one `PYTHONIOENCODING=utf-8`-prefixed
  Bash call) is **Mechanical/collapsible** (already a single scripted call, ~0 further saving); "read
  in full, do not skim" is **Excluded** — it is a comprehension requirement on the LLM, not a
  deterministic branch.
- **Phase: Explore, Step 2** (lines 168-176) — write a 3-6 bullet scope digest before touching any
  file — **Excluded**. Genuine synthesis/writing task.
- **Phase: Explore, Step 3** (lines 178-186) — explore the codebase via codeguide/`git log`/
  `Grep`/`Glob`, judgment on what to read — **Excluded**. Open-ended judgment call, no fixed shape.
- **Sub-investigation guidance** (lines 188-197) — guidance for choosing fork vs. cold `Explore`
  vs. inline, plus the #919 incident note — **Excluded**. Pure judgment guidance, not an executable
  step.
- **Fork scope guardrail** (line 199) — pre/post `git status --porcelain` snapshot-and-diff around
  a research fork, revert-on-violation — **Borderline**. It brackets an Agent dispatch (the research
  fork), the exact Borderline trigger in the classification scheme.
  - *Full exclusion:* leave the whole guardrail as orchestrator-driven text exactly as today — the
    snapshot/diff/revert decision stays visible in the transcript alongside the fork dispatch it
    protects.
  - *Scoped partial collapse:* a script call takes the pre-dispatch baseline and the post-dispatch
    snapshot as two arguments and returns the diff (new-vs-baseline entries) as a JSON list; the
    SKILL.md keeps the actual fork dispatch, the violation-detected halt/revert decision, and the
    baseline-vs-post-return capture calls themselves (each is a single, cheap `git status`
    invocation that does not itself need scripting).
  - **Recommendation:** scoped partial collapse for the diff-computation step only — the two
    `git status --porcelain` captures and the fork dispatch itself must stay inline (they bracket the
    actual Agent call and the operator-visible revert decision), but comparing two porcelain listings
    for "new-since-baseline" entries is pure string-set arithmetic with no judgment in it.
- **Fork echo caution** (lines 201-204) — check whether a fork's first response is a grounded
  finding or an echo, and if so send a corrective directive — **Excluded**. Judgment call on
  response quality, not a deterministic branch.
- **Phase: Discuss** (lines 206-228) — interview the user in batches, propose approaches, wait for
  approval — **Excluded**. The canonical round-by-round operator-loop shape anti-pattern #2 names.
- **Phase: Discussion File** (lines 230-235) — render the discussion template, fill every section,
  commit — **mixed**. Rendering the template skeleton and the final `git add && git commit` are
  **Mechanical/collapsible** (deterministic, already a single Bash call for the commit — ~0 further
  saving); "Fill every section" so the file is self-contained is **Excluded** — it is the write-up of
  everything the interview just produced, genuine authorship.
- **Phase: Discussion Review** (lines 237-409) — the review loop. Broken down at its own numbered-
  step/subsection granularity:
  - **Tree-guard safeguard** (lines 239-242) — `_treeguard.check_and_restore` +
    `_status.append_recovery_log` on trigger, before every `_status.append_phase` call in this phase
    — **Mechanical/collapsible**. Deterministic helper pair, already scripted, called at multiple
    sites in this phase; collapsing the check-and-append pair into one call site removes a
    conditional-append turn each time it fires. Rough saving: ~1 turn per fire.
  - **Load `mill-receiving-review`** (lines 244-247) — **Excluded**. Skill-tool load, same reasoning
    as Entry Step 0.
  - **Skip conditions** (lines 249-250) — `rounds: 0` OR `reviewer: None` means skip to Handoff —
    **Mechanical/collapsible**. Two-key deterministic check; un-scripted today but trivial. Rough
    saving: ~0-1 turns.
  - **Step 1: report round number** (line 255) — **Mechanical/collapsible**. A print statement;
    negligible saving on its own, folds naturally into whichever call precedes it.
  - **Step 2: dispatch mode + Agent-mode/subprocess dispatch** (lines 256-299) — **Borderline**. It
    brackets the reviewer's own Agent dispatch (the genuine LLM review) and the tree-guard
    checkpoints around it.
    - *Full exclusion:* leave the whole three-step Agent-mode pattern (prepare → Agent call →
      finalize) and the subprocess/`millpy-bg` polling loop exactly as documented — every mechanical
      sub-piece (poll `cat`/`grep`, parse JSON) stays inline next to the dispatch it serves.
    - *Scoped partial collapse:* a script call performs the deterministic prepare-envelope parsing
      (extract `subagent_type`/`model`/`session_id`/`round`/`output_path`) and the subprocess-branch
      polling-until-`[mill-bg] EXIT` loop, returning the parsed JSON summary; the SKILL.md keeps the
      actual `Agent()` tool call, the tree-guard checkpoint calls (already their own Mechanical
      entry above), and the branch decision on the resulting verdict.
    - **Recommendation:** scoped partial collapse for the subprocess-branch polling loop only (the
      repeated `cat <log-path>` / liveness-check / `grep '^{'` cycle is pure mechanical polling with
      no judgment); the Agent-mode branch's Agent-tool call itself must stay inline since it *is*
      the dispatch this Borderline classification protects.
  - **Step 3: confirm `mill-receiving-review` loaded** (lines 301-303) — **Mechanical/collapsible**.
    A one-line confirmation restating an already-loaded state; trivial, ~0 saving on its own.
  - **Step 3.5: ERROR-only-aggregate retry** (lines 305-346) — **Borderline**. Same shape as step
    2 above — it re-runs the identical Agent-mode/subprocess dispatch pattern, so it brackets the
    same Agent dispatch.
    - *Full exclusion:* keep the whole retry cycle (usage-error immediate halt, ERROR-verdict
      detection, re-dispatch, two-pass cap) as orchestrator-driven text.
    - *Scoped partial collapse:* a script call classifies the envelope (usage-error vs.
      ERROR-verdict-retry vs. reviewable) and, for the subprocess branch, runs the identical
      poll-until-exit mechanics step 2's collapse candidate already covers; the SKILL.md keeps the
      halt-message text, the two-pass-cap halt decision, and the Agent-mode call itself.
    - **Recommendation:** scoped partial collapse, reusing the same script call step 2's
      recommendation introduces — this step is structurally the same dispatch-and-classify shape,
      just gated by a different trigger condition, so a shared helper serves both.
  - **Convergence gate** (lines 348-363) — compute `converged` from `round`/`min_review_rounds`/
    `demoted` predicate (and, under `--orch`, `prev_verdict_was_approve`) — **Mechanical/
    collapsible**. Pure boolean arithmetic over already-available values, no judgment. Un-scripted
    today (computed inline); a shared helper would remove one inline-computation turn per round.
    Rough saving: ~1 turn per round.
  - **Step 4a: APPROVE, no NITs** (lines 365-371) — **Mechanical/collapsible**. Deterministic
    branch on `converged`/round-cap, fixed commit message, fixed report text. Un-scripted; rough
    saving: ~1 turn (folds the read-review-file + branch + commit into one call).
  - **Step 4b: APPROVE with NITs** (lines 373-388) — **Excluded** overall — applying each NIT fix
    "using best judgment" is genuine editing work — but its terminal bookkeeping (the
    `_status.append_phase` + single commit + Handoff-completion report, once NIT fixes are already
    applied) is the same append_phase+commit shape flagged as Mechanical/collapsible for
    `mill-go-base`'s `## Prepare` section below; recorded here as a **Borderline** note rather than a
    separate top-level bucket entry, since it is entangled with the judgment-driven NIT-fix work that
    precedes it in the same numbered step.
    - *Full exclusion:* leave the append_phase/commit/report sequence inline, immediately after the
      NIT-fix judgment work, exactly as today.
    - *Scoped partial collapse:* once NIT fixes are already applied (an LLM-judgment precondition
      that cannot itself be scripted), a script call performs the `_status.append_phase` + git
      commit + push in one call, returning the commit sha; the SKILL.md keeps the Handoff-completion
      report text and the loop-break decision.
    - **Recommendation:** scoped partial collapse for the bookkeeping tail only, once the NIT-fix
      editing itself is done — this mirrors the "Helper-function home for the `append_phase` +
      git-commit pattern" Decision this audit records as a cross-cutting recommendation (see below).
  - **Step 5: `--auto`/`--orch` guard / interactive gap-prompt** (lines 390-407) — **Excluded**. The
    guard branch defers to the Auto-mode machinery (already Excluded above); the interactive path is
    the canonical batched-question-and-wait loop, the anti-pattern #2 shape.
  - **Unresolved-gaps-after-max-rounds fallback** (line 409) — **Excluded**. Operator-facing
    override decision, judgment.
- **Phase: Handoff** (lines 411-419) — `_status.append_phase(status_path, "discussed", ...)`, stage
  briefs if present, one commit, report a fixed completion string — **Mechanical/collapsible**.
  Current behavior: one phase append, a conditional `git add`, one commit, one fixed print. Already
  expressible as a single script call (`_status.append_phase` + `_subprocess_util.git_commit`, see
  the cross-cutting recommendation below); un-scripted today as a combined unit. Rough saving: ~2
  turns collapsed to 1.

## mill-plan

- **Entry Step 0** (lines 16-18) — load `mill:prose`/`mill:conversation` — **Excluded**. Skill-tool
  load, same reasoning as `mill-start`'s Entry Step 0.
- **Entry Step 0.5: parse arguments** (lines 20-31) — token-walk `$ARGUMENTS` for `--revise`/
  `--approve`, halt on both or on an unknown token — **Mechanical/collapsible**. Pure deterministic
  string parsing with fixed halt messages, no judgment. Un-scripted today (inline token-walk); rough
  saving: ~1 turn.
- **Entry step 1** (lines 33-38) — resolve `git_root`/`wiki_path`/`worktree_root` — **Mechanical/
  collapsible**. Same shape as `mill-start`'s steps 1-3 + Path Setup; already-scripted per-call.
- **Entry step 2** (lines 39-43) — load config, read `max_review_rounds`/`min_review_rounds`/
  `pipeline.entry_wait*` — **Mechanical/collapsible**. Deterministic config read.
- **Entry step 3** (lines 44-45) — resolve slug, halt on `MarkerError` — **Mechanical/collapsible**.
  Fixed halt text, no operator choice.
- **Path Setup** (lines 47-52) — derive `status_path`; note `plan_dir`/`reviews_dir` are deferred to
  later phases — **Mechanical/collapsible**.
  - **Combined candidate:** Entry steps 1-3 + Path Setup (lines 33-52) are one collapse unit, same
    shape and same recommendation as `mill-start`'s equivalent sequence above. Rough saving: ~3
    turns collapsed to 1.
- **Entry step 4: phase-table branch** (lines 54-138) — re-derived line range for this audit (the
  task body's own first-pass citation of "~60 lines" is stale; `_mill/discussion.md`'s own
  re-derivation of 54-138 checked out against the current worktree source and is used here
  unchanged). This is the task body's own cited Borderline worked example and now spans three
  distinct sub-parts, each classified separately below rather than as one monolithic entry, since
  they no longer share one shape:
  - **`--revise` pre-check** (lines 57-62) — read `phase`/`approved`, branch on
    `planned+approved: true` vs. `blocked` vs. neither, flip `approved: false`, append_phase, commit
    — **Borderline**. It brackets a phase-name-visible transition (`planning`) and a fixed halt
    message for the "neither" branch.
    - *Full exclusion:* keep the whole three-way branch and its commit/push inline, exactly as
      today.
    - *Scoped partial collapse:* a script call reads `phase`/`approved` and returns which of the
      three branches applies (as a JSON tag), plus performs the deterministic `approved: false` edit
      and the `_status.append_phase`+commit for the two proceed-branches; the SKILL.md keeps the
      "unsupported" halt message text and the decision of which branch's report to show the
      operator.
    - **Recommendation:** scoped partial collapse — the branch-selection read is pure
      deterministic YAML inspection, and the two proceed-branches' bookkeeping (edit + append_phase +
      commit) is the same append_phase+commit shape flagged cross-cuttingly below; only the halt
      wording for the "neither" branch needs to stay SKILL-owned.
  - **`--approve` pre-check** (lines 64-70) — read `phase`/`blocked_reason`, branch on
    `blocked` + `max-rounds exhausted` prefix vs. not, flip `approved: true`, commit, fall through to
    Handoff — **Borderline**. Same shape as `--revise` above: brackets a fixed halt/defensive-guard
    message and an operator-visible `approved:` flip.
    - *Full exclusion:* keep inline exactly as today.
    - *Scoped partial collapse:* a script call performs the `blocked_reason.startswith(...)` check
      and the `approved:` frontmatter flip + commit in one call, returning whether the pre-check
      applied; the SKILL.md keeps the "already true" defensive halt and the "--approve only applies
      to..." halt text.
    - **Recommendation:** scoped partial collapse, mirroring the `--revise` pre-check's
      recommendation — same mechanical shape, same reasoning.
  - **Phase table itself** (lines 72-79) — six-row `phase:` → action lookup — **Mechanical/
    collapsible**. A fixed dict lookup with no judgment (each row's *action* may itself be Excluded
    or Borderline, as classified separately, but the lookup that selects a row is pure mechanical
    dispatch). Un-scripted; rough saving: ~1 turn.
  - **Entry-gate wait for upstream mill-start** (lines 81-116) — compute the wait-trigger match,
    build the `Monitor` wait command, wait for the `<task-notification>`, branch on `READY`/
    `TIMEOUT`/harness-stop — **Borderline**. It brackets the `Monitor` tool's long-running wait (a
    dispatch-shaped operation, not an Agent call, but the same "don't collapse the thing being
    waited on" concern applies) and ends in three distinct operator-facing halt/re-entry messages.
    - *Full exclusion:* keep the whole wait-and-branch sequence inline, exactly as today — the
      `Monitor` call, the event-branching, and every halt message stay orchestrator-owned.
    - *Scoped partial collapse:* a script call computes `matched`/`entry_wait`/`giveup_s` and builds
      the wait command string (`_phase_wait.build_wait_command`) in one call; the SKILL.md keeps the
      actual `Monitor` tool invocation, the event-branch decisions, and every halt/re-entry message.
    - **Recommendation:** scoped partial collapse for the command-construction step only (three
      deterministic reads + one helper call, currently three separate inline reads) — the `Monitor`
      call itself and the branch on its result must stay inline, since collapsing those would hide
      the operator-visible wait/timeout decision the Borderline bucket exists to protect.
  - **Entry: resuming after a max-rounds block** (lines 117-138) — read `blocked_reason`, branch on
    the `"max-rounds exhausted"` prefix, detect mid-`--revise` blocks, derive `N`/
    `local_max_review_rounds`, append_phase, commit, fall through to Phase: Plan Review —
    **Borderline**. Entangled with two distinct operator-facing halt messages (non-max-rounds block,
    mid-`--revise` block) and a phase-name-visible `"planning"` transition.
    - *Full exclusion:* keep the whole resume procedure inline exactly as today.
    - *Scoped partial collapse:* a script call performs the deterministic sub-pieces — the
      `blocked_reason` prefix check, the mid-`--revise` freshness comparison across
      `revise-*` subdirectories, and the `N`/`local_max_review_rounds` arithmetic — returning a JSON
      verdict (`resume` | `hard-stop` | `mid-revise-unsupported`) plus the computed values; the
      SKILL.md keeps the two halt messages and the `_status.append_phase`+commit+fallthrough
      decision.
    - **Recommendation:** scoped partial collapse — every sub-piece here is deterministic file
      inspection and arithmetic; only the two halt-message texts and the final fallthrough decision
      need to stay SKILL-owned.
- **Phase: Plan** (lines 144-304) — broken down at numbered-step granularity:
  - **Read discussion.md, capture `discussion_sha`** (lines 146-149) — **Mechanical/collapsible**.
    One read, one `git rev-parse` capture, no judgment.
  - **"think the plan through end-to-end"** (line 149) — **Excluded**. The entire reason Opus runs
    this phase; pure reasoning, no fixed shape.
  - **Fork scope guardrail** (lines 151-160) — pre/post `git status --porcelain` diffing around a
    research fork — **Borderline**, identical reasoning and recommendation to `mill-start`'s
    equivalent guardrail above (brackets an Agent dispatch): scoped partial collapse for the
    baseline-vs-post-return diff computation only, fork dispatch and violation-revert decision stay
    inline.
  - **Batch sizing** (lines 162-168) — judgment on how to split batches by module/subsystem boundary
    — **Excluded**. Genuine design judgment, not mechanizable.
  - **Write the files, steps 1-3** (lines 170-208) — render `plan-overview.md`/`plan-batch.md`
    templates, fill Batch Index/Cards/Batch Tests — **mixed**. Template rendering (step 1, the
    `_render.render` call) is **Mechanical/collapsible** (deterministic substitution, already
    scripted); filling the Batch Index/Cards/Batch Tests content is **Excluded** (the plan's actual
    design content, written by the planning LLM).
  - **Self-validate the DAG** (lines 246-248) — call `_plan_dag.extract_batch_index` +
    `_plan_dag.validate`, fix-then-retry on `PlanDAGError` — **Mechanical/collapsible**. Deterministic
    validation gate with a fixed retry shape; already scripted per-call (each is one function call
    issued as its own turn today). Rough saving: ~1 turn.
  - **Self-run the validator gate** (lines 250-269, including the `wiki-config-mutation`/
    `verify-full-suite`/`out-of-worktree-target` skip-check overrides) — **mixed**. The
    `_plan_validate.run` call itself is **Mechanical/collapsible** (deterministic, already scripted);
    each skip-check override's two-condition test is a judgment call on the planner's own design
    intent (e.g. "is this key addition's consuming code provably unused" cannot be answered
    mechanically) — **Excluded**.
  - **Fix findings via Step 1.5's table, re-run** (lines 286) — **Mechanical/collapsible** for the
    mechanical rows of the fix table (most rows are literal find-and-replace edits per the table);
    the rows the table itself marks "Halt — not mechanically fixable" are **Excluded** by the table's
    own design (a structural planning bug, not a fixable shape).
  - **Persist `skip_checks`/`discussion_sha` into frontmatter** (lines 288-290) — **Mechanical/
    collapsible**. Deterministic frontmatter edits with no judgment (the *values* being persisted
    were already computed above; this is just the write).
  - **Update `_mill/status.md`** (lines 294-299) — `_status.update_field` + `_status.append_phase` —
    **Mechanical/collapsible**. Same append_phase shape flagged cross-cuttingly; un-scripted as a
    combined unit today.
  - **Pre-commit drift check** (line 301) — re-run `git rev-parse`, compare against captured
    `discussion_sha`, halt+`set_blocked`+commit on mismatch, or fall through — **Borderline**. The
    "proceed" path is pure Mechanical (a sha comparison), but the mismatch path is a fixed,
    operator-facing halt message entangled with the same comparison.
    - *Full exclusion:* keep the whole check-and-branch inline, exactly as today.
    - *Scoped partial collapse:* a script call re-runs the `git rev-parse`, compares it, and on
      mismatch performs the `git clean -fd` + `_status.set_blocked` + commit + push in one call,
      returning a boolean; the SKILL.md keeps only the halt message text and the decision to stop
      short of committing the plan.
    - **Recommendation:** scoped partial collapse — the mismatch branch's actions are themselves
      fully mechanical (clean, set_blocked, commit, push); only the halt wording needs to stay
      SKILL-owned.
  - **Commit on the task branch** (lines 303-304) — **Mechanical/collapsible**. One `git add` +
    commit + push, fixed message.
- **Phase: Plan Review** (lines 306-618) — the review loop, mirroring `mill-start`'s Discussion
  Review shape closely enough that most sub-mechanics classify the same way:
  - **Path Setup / read persisted `skip_checks`/`discussion_sha`** (lines 308-337) — **Mechanical/
    collapsible**. Deterministic frontmatter reads.
  - **`--revise` namespacing override, `--max-rounds` threading for blocked-resume, live
    operator round-cap override, live operator waiver of step 6** (lines 316-329) — **Excluded**
    for the live-operator overrides (they exist specifically to accept a natural-language operator
    instruction — irreducibly interactive by design); **Mechanical/collapsible** for the `--revise`
    namespacing arithmetic and the blocked-resume `--max-rounds` threading (deterministic
    string/integer computation with no judgment, once the triggering condition is already known).
  - **Tree-guard safeguard** (lines 330-332) — **Mechanical/collapsible**, identical shape and
    recommendation to `mill-start`'s Tree-guard safeguard entry above.
  - **Load `mill-receiving-review`, skip conditions** (lines 334-342) — **Excluded** (skill load) /
    **Mechanical/collapsible** (the two-key skip check), same split as `mill-start`'s equivalent.
  - **Step 1: report round** (line 350) — **Mechanical/collapsible**, trivial.
  - **Step 1.5: pre-review validator gate, auto-run + fix table + two-pass cap** (lines 352-406) —
    **mixed**, same split as Phase: Plan's own validator-gate entry above: the CLI auto-run and the
    fix table's mechanical rows are **Mechanical/collapsible**; the fix table's "Halt" rows and the
    two-pass-cap halt message are **Excluded**/fixed text respectively (the halt itself is a simple
    fixed message, folded into the mechanical bookkeeping rather than broken out separately, since it
    has no judgment branch of its own beyond "second failure").
  - **Convergence gate (min_rounds)** (lines 411-421) — **Mechanical/collapsible**, identical
    reasoning to `mill-start`'s Convergence gate entry — pure boolean arithmetic over already-known
    values.
  - **Step 2: dispatch mode + Agent-mode/subprocess dispatch** (lines 423-497) — **Borderline**,
    identical reasoning and recommendation to `mill-start`'s Discussion-Review step 2 — brackets the
    plan reviewer's Agent dispatch; scoped partial collapse for the subprocess polling-until-exit
    loop only.
  - **Step 3: confirm review skill loaded** (lines 499-502) — **Mechanical/collapsible**, trivial.
  - **Step 3.5: ERROR-only-aggregate retry** (lines 504-549) — **Borderline**, identical reasoning
    and recommendation to `mill-start`'s equivalent step 3.5 — same dispatch-and-classify shape,
    different trigger condition.
  - **Unconditional round-recorded append** (line 551) — **Mechanical/collapsible**. Same
    append_phase+commit shape flagged cross-cuttingly.
  - **Guardrail (NIT/BLOCKING fixes scoped to `plan_dir` only)** (line 553) — **Excluded**. A
    standing constraint on the judgment-driven fix steps below it, not itself an executable step.
  - **Step 4a: APPROVE, zero NITs** (lines 555-560) — **Mechanical/collapsible**, same shape as
    `mill-start`'s 4a.
  - **Step 4b: APPROVE with NITs** (lines 562-577) — **Excluded** for the NIT-fix judgment work and
    the DAG/validator re-run's *judgment* content (deciding whether a given finding is a legitimate
    fix); **Borderline** for the terminal bookkeeping tail (append_phase + single commit +
    Handoff-transition), same reasoning and recommendation as `mill-start`'s 4b entry.
  - **Step 4c: REQUEST_CHANGES with `blocking_count == 0`** (lines 579-588) — same split as 4b:
    **Excluded** for the NIT-fix/validator-gate judgment; **Borderline** (scoped partial collapse
    recommended) for the terminal append_phase+commit tail.
  - **Step 4d: REQUEST_CHANGES with `blocking_count > 0`** (lines 590-601) — **Excluded**. Applying
    the `mill-receiving-review` decision tree to genuine BLOCKING findings is exactly the judgment
    work this bucket protects; even its terminal `_status.append_phase`+commit is entangled with the
    fixer-report content it accompanies in the same step, so it is not broken out as a separate
    Mechanical line the way 4a/4b/4c's cleaner terminal actions are.
  - **Step 5: Non-progress check** (lines 603-611) — **Borderline**. The `Pushed Back`-title-set
    comparison is a mechanical read, but the halt itself is the entire point of the check (a
    stable-disagreement circuit-breaker) and is explicitly never auto-escaped.
    - *Full exclusion:* keep inline exactly as today.
    - *Scoped partial collapse:* a script call reads both rounds' fixer reports and returns whether
      the title sets are identical and non-empty; the SKILL.md keeps the `_status.set_blocked`+
      commit+halt text.
    - **Recommendation:** scoped partial collapse for the title-set comparison only — the read-and-
      compare is pure mechanical text parsing; the halt decision and its operator-facing message must
      stay SKILL-owned, since this check exists specifically to force a human look.
  - **Step 6: Max-rounds escape** (lines 613-618) — **Borderline**, same reasoning as step 5 —
    mechanical `blocking_count`-read, but a deliberate halt whose whole purpose is stopping automatic
    progress.
    - *Full exclusion:* keep inline exactly as today.
    - *Scoped partial collapse:* a script call reads `result["blocking_count"]` and the live-waiver
      flag and returns which of "waive" / "halt" applies; the SKILL.md keeps the halt message and the
      waiver's implicit-approve commit text.
    - **Recommendation:** scoped partial collapse for the read-and-branch only, same reasoning as
      step 5.
- **Phase: Handoff** (lines 620-636) — guard-read `approved:`, halt on `false`, append_phase
  `"planned"`, commit+push, conditionally invoke `/mill-self-report --auto`, report a fixed
  completion string — **Mechanical/collapsible** for the guard-read/halt/append_phase/commit
  (deterministic, fixed halt text, no operator choice); the conditional `/mill-self-report --auto`
  invocation is an Agent-adjacent skill invocation, not itself a read/write/branch, so it is left
  attached to this same Mechanical entry rather than broken out (it is a single conditional
  skill-load, already effectively one turn). Rough saving for the guard+append_phase+commit portion:
  ~2 turns collapsed to 1.

## mill-go-base

Re-derived counts against the current worktree source (the task body's first-pass numbers are a
starting point, not ground truth — `_mill/discussion.md`'s own spot-check already found a one-off
drift): `_status.append_phase` call sites — `mill-start/SKILL.md` 6, `mill-plan/SKILL.md` 14,
`mill-go-base/SKILL.md` 21. `commit -m` occurrences — `mill-start/SKILL.md` 6,
`mill-go-base/SKILL.md` 17, `mill-plan/SKILL.md` 21. Both counts match `_mill/discussion.md`'s own
cited numbers exactly, so no drift beyond what that document already flagged. The two counts are
not 1:1 paired site-for-site: `mill-go-base/SKILL.md` has 21 `append_phase` calls against 17
`commit -m` occurrences because several call sites share one commit across two bookkeeping
operations (e.g. Prepare's `init_batches` + `append_phase` land in a single commit; the Cleanliness
gate's several `set_batch_field`+`append_phase` blocked-branches each pair 1:1 with their own
commit; the Stuck-escalation self-resolve path's `append_phase("self-resolved-verify-logic", ...)`
shares a commit with a `plan_dir` edit). This paired-vs-unpaired shape is exactly the kind of detail
a follow-up `append_phase_and_commit`-style helper (see `## Cross-cutting recommendations` below)
would need to preserve per call site, not collapse into one generic wrapper.

- **Entry Step 0 (variant binding + driver preamble)** (lines 19-33) — bind `VARIANT_LABEL`, halt if
  not invoked via a variant, splice in the variant's `## Driver preamble` — **Mechanical/
  collapsible** for the binding/halt check itself (deterministic, fixed halt text); the *content* of
  a variant's driver preamble (e.g. `mill-go2`'s fork-dispatch overrides) is Excluded elsewhere by
  each variant's own classification, already covered above (`mill-go`/`mill-go2` add no mechanical
  sequences beyond dispatch-override judgment).
- **Step 0: verify `CLAUDE_PLUGIN_ROOT`** (lines 35-46) — a one-line env-var guard —
  **Mechanical/collapsible**. Trivial, already effectively zero-turn (a guard clause inside a Bash
  block that runs anyway).
- **Step 0b: load `mill:prose`/`mill:conversation`** (lines 48-50) — **Excluded**. Skill-tool load,
  same reasoning as `mill-start`'s Entry Step 0.
- **Entry steps 1-4.5 (resolve paths, load config, read slug, acquire builder lock, Path Setup)**
  (lines 52-88) — **Mechanical/collapsible**. Current behavior: 5 sequential deterministic
  operations (`_paths` resolution, `_review_common.load_config`, `_marker.slug_from_branch`, the
  `millpy-builder-lock.py acquire` subprocess, and the multi-variable Path Setup block), each issued
  as its own step today. Already scripted per-step (every sub-call is an existing helper/CLI); this
  is the largest of the three files' Entry-sequence collapse candidates by step count. Rough saving:
  ~5 turns collapsed to 1.
- **Entry step 5: Entry phase gate** (lines 89-122) — guard against the merge-interrupted
  missing-`status.md` state, read `phase`/`blocked_reason`, six-row phase-table dispatch —
  **mixed**. The missing-`status.md` guard and the phase-table lookup itself are **Mechanical/
  collapsible** (deterministic dict dispatch, fixed messages on the terminal rows); the widened
  `implementing`/`reviewing`/`fixing`/`discussed`-family rows route into the two subsections below,
  classified separately since they are not simple terminal actions.
- **Mid-execution phase-gate widening** (lines 124-158) — compute `matched`, route across seven
  named branches (bare states, `approved-{batch}`, `holistic-reviewing`, `self-resolved-verify-logic`
  disambiguation, `holistic-approved`) — **Mechanical/collapsible**. Every branch here is a fixed
  string/regex match against `phase`/`_status.read_batches` state, with a fixed routing target (no
  branch asks an LLM anything or halts on an operator-facing message) — the most complex single
  dispatch table in the three files, but still purely deterministic. Un-scripted today as a combined
  routing table; rough saving: ~2-3 turns (collapsing the "read phase, read batches, compute match,
  pick a route" sequence into one call that returns the target section name).
- **Entry-gate wait for upstream mill-plan** (lines 160-201) — **Borderline**, identical reasoning
  and recommendation to `mill-plan`'s "Entry-gate wait for upstream mill-start" entry above (brackets
  a `Monitor` wait; scoped partial collapse for the wait-command construction only).
- **Entry step 6: read/validate/topo-sort the Batch Index** (lines 203-207) —
  **Mechanical/collapsible**. `_plan_dag.extract_batch_index` + `.validate` + `.topo_order`, three
  deterministic calls with no judgment. Rough saving: ~1 turn.
- **## Prepare** (lines 209-216) — `_status.init_batches` → `_status.append_phase("implementing",
  ...)` → one git commit, fresh-run only — **Mechanical/collapsible**. Current behavior: two
  status-file mutations followed by one commit, issued as three sequential tool calls today.
  Already-scripted-per-step: yes, both `_status` calls and the git commit are existing operations;
  the win is purely collapsing 3 script-invoking turns into 1 combined helper call (the
  `append_phase`+git-commit pattern the "Helper-function home" cross-cutting recommendation below
  names by candidate number). Rough saving: ~2 turns collapsed to 1.
- **## Agent-mode dispatch** (lines 221-450) — the shared three-step prepare/Agent-call/finalize
  pattern plus its error-recovery/liveness-probe/tree-guard machinery, referenced from every dispatch
  site in the file (Implement, Code Review, NIT-fix, fix/REQUEST_CHANGES) — **Borderline** as a
  whole, since every invocation of this pattern brackets a genuine Agent dispatch (implementer,
  reviewer, or fixer). Broken down by its own numbered steps:
  - **Step 1: run prepare stage, parse envelope** (lines 227-235) — **Mechanical/collapsible** on
    its own (a CLI invocation + JSON parse, already scripted), but it exists only to feed step 2's
    dispatch, so its collapse value is folded into the Borderline recommendation below rather than
    listed as an independent saving.
  - **Step 2: call Agent tool, record `agentId`/timestamps** (lines 236-271) — **Excluded**. This
    step *is* the Agent dispatch the Borderline classification protects; the `agentId`/timestamp
    bookkeeping around it is trivial and inseparable from the call itself.
  - **Step 3: recover from raw API errors and interruptions** (lines 277-342) — **Borderline**. The
    classification logic (raw-API-error marker match, implementer clean-turn-exhaustion vs.
    non-clean-terminal split, reviewer/fixer liveness probe) is deterministic pattern-matching over
    already-available notification text and `TaskOutput` results, but it exists entirely to decide
    how to react around the just-completed Agent dispatch.
    - *Full exclusion:* keep the whole three-way classification (a/b/c) inline exactly as today —
      every branch's re-dispatch or probe call stays orchestrator-visible.
    - *Scoped partial collapse:* a script call takes the notification text (and, where applicable,
      a `TaskOutput` probe result already fetched) and returns which of (a)/(b)/(c)'s sub-branches
      applies, as a classification tag; the SKILL.md keeps every re-dispatch decision, every
      `TaskOutput` call itself, and the transient-vs-incomplete-vs-logic routing that follows.
    - **Recommendation:** scoped partial collapse for the text-classification step only — matching
      an "API Error" marker, a `<status>` tag value, and a JSON-status-block presence is pure string
      inspection; the probe calls and every re-dispatch decision must stay inline since they are the
      dispatch-adjacent actions this Borderline bucket exists to protect.
  - **Step 4: capture output — reviewer-skipped** (lines 344-349) — **Mechanical/collapsible**. A
    conditional file write with no judgment (implementer/fixer/merge-in write; reviewer skips).
  - **Step 5: run finalize stage** (lines 351-380) — **Mechanical/collapsible** for the CLI
    invocation and flag-threading itself (deterministic, already scripted); the accompanying prose
    about Bash-tool timeout tuning and PATH inheritance is operational guidance, not itself a step.
  - **Step 5.5: `incomplete` recovery** (lines 382-412) — **Borderline**. The warm-`SendMessage`-
    then-`--resume-incomplete`-fallback shape re-dispatches into the same Agent session that step 2
    already dispatched, so it brackets the identical Agent dispatch this whole section protects.
    - *Full exclusion:* keep the whole warm-resume/cold-fallback sequence inline, exactly as today.
    - *Scoped partial collapse:* a script call determines which of "warm resume viable" / "cold
      `--resume-incomplete` required" applies (based on whether `agentId` is retained and the prior
      `SendMessage` outcome) and performs the deterministic envelope re-parse afterward; the
      SKILL.md keeps the actual `SendMessage`/`Agent` re-dispatch calls themselves.
    - **Recommendation:** scoped partial collapse for the branch-selection logic only — the two
      dispatch calls this recovery can issue must stay inline.
  - **Step 6: branch on verdict** (line 414-415) — **Mechanical/collapsible**. A pointer to the
    caller's own branching (Implement step 2, Code Review step 4, etc.), not additional logic of its
    own.
  - **Agent-mode properties / Tree-guard checkpoint block / "Why not fork?"** (lines 417-450) — not
    executable steps; reference documentation and a standing design rationale — **Excluded** from
    per-run classification (nothing here executes at runtime beyond the Tree-guard checkpoint calls,
    which are the same **Mechanical/collapsible** shape already flagged for `mill-start`'s Tree-guard
    safeguard entry above).
- **## Review cost line** (lines 452-486) — a print-format specification, invoked by name from
  every review dispatch site — **Mechanical/collapsible**. Deterministic field lookup + string
  formatting, already effectively a single print call per invocation; not itself a multi-step
  sequence to collapse further.
- **### 0. Wiki health-check** (lines 487-506) — one Python one-liner health-check, release lock +
  halt on failure — **Mechanical/collapsible**. Already a single Bash-tool invocation with a fixed
  halt message; rough saving: ~0 turns (already at the 1-turn floor), same shape as `mill-start`'s
  Phase: Select.
- **### 0.55. Done-gate baseline pre-flight** (lines 508-546) — first-batch-only conditional
  `_done_gate.run_preflight` invocation, log-and-continue on `blocked` — **Mechanical/collapsible**.
  Deterministic config-gated call with a fixed non-halting log path; already scripted.
- **### 0.5. Baseline pre-flight** (lines 548-578) — first-batch-only `millpy-bg`-backed
  `--stage baseline` invocation, poll-until-exit, parse two JSON lines, never halts —
  **Mechanical/collapsible**. Same "already-scripted subprocess + polling loop" shape as the
  various review-dispatch polling loops classified Borderline elsewhere — but this one brackets no
  Agent/LLM dispatch (it is a plain background CLI run), so it stays Mechanical rather than
  Borderline. Rough saving: ~1-2 turns (the poll-until-exit cycle collapses to one wait call).
- **### 0.6. Per-batch baseline recapture** (lines 580-625) — self-hosting-only conditional
  `millpy-bg`-backed recapture, four-condition trigger check, never escalates on failure —
  **Mechanical/collapsible**, same reasoning as 0.5 above (background CLI + polling loop, no Agent
  dispatch bracketed).
- **### 1. Implement** (lines 627-651) — venv-check, then the Agent-mode dispatch pattern with
  `millpy-implement.py` — **mixed**. The venv-check (lines 629-640) is **Mechanical/collapsible**
  (a fixed guard-and-`uv sync`-once shape); the dispatch itself is the same **Borderline** "##
  Agent-mode dispatch" entry already classified above, not re-classified per call site.
- **### 2. Parse implementer report** (lines 653-666) — branch on `status`/`stuck_type` from the
  implementer's JSON line, one-retry-then-escalate for `transient` — **Mechanical/collapsible**.
  Deterministic JSON-field dispatch with a fixed retry count; already effectively a single parse+
  branch operation. Rough saving: ~1 turn when the retry fires (folds the re-invocation decision into
  the same call as the parse).
- **### 2b. Cleanliness gate** (lines 668-743) — scope-violations check, parent-branch liveness
  resolution (including dead-parent auto-rebind/fallback/cycle), out-of-scope drift revert, dirt
  classification, each ending in either a `blocked`+commit or a fall-through — **Mechanical/
  collapsible**. Every branch here is a deterministic helper-call sequence (`_cleanliness`,
  `_parent_branch`) with fixed `blocked_reason` text per outcome — no judgment call decides which
  branch fires, only already-known return values do. This is the longest purely-Mechanical sequence
  in the file: 5 chained deterministic decision points, each currently a separate tool-call round
  today. Already scripted per-step (every sub-call is an existing helper); rough saving: ~4-5 turns
  collapsed to 1 (one script call returning which terminal branch applies, plus the commit already
  made).
- **### 3. Code Review loop** (lines 745-878) — broken down at numbered-step granularity:
  - **Per-batch-review-disabled shortcut** (line 747) — **Mechanical/collapsible**. A single
    config-gated approve-and-continue path, no judgment.
  - **Setup (state → reviewing, `min_batch_rounds`)** (lines 750-752) — **Mechanical/collapsible**.
  - **Convergence gate (min_rounds + demoted predicate)** (lines 754-765) — **Mechanical/
    collapsible**, identical reasoning to `mill-start`'s/`mill-plan`'s Convergence gate entries —
    pure boolean arithmetic.
  - **Per-round setup: tree-guard + `reviewing-{batch}-rN` append_phase + commit** (lines 769-772)
    — **Mechanical/collapsible**, the same append_phase+commit shape flagged cross-cuttingly.
  - **Step 1: crash-recovery check** (lines 774-795) — **Mechanical/collapsible**. Deterministic
    freshness comparison (`ref_ts` vs. file mtime) against a scanned `reviews_dir` glob, no judgment.
  - **Step 1.5: prior-notes digest** (lines 797-804) — **Mechanical/collapsible**. Deterministic
    text extraction (parse `### [NIT]` headings from the prior round's review file) and file write.
  - **Step 2: tree-guard + Agent-mode dispatch (code reviewer)** (lines 806-811) — the same
    **Borderline** "## Agent-mode dispatch" entry, called here for the code-review CLI specifically;
    not re-classified per call site.
  - **Step 3: read cost line, no findings read** (lines 813-819) — **Mechanical/collapsible**.
  - **Step 4: branch on verdict** (lines 821-856) — **mixed**. The `APPROVE`/`NEED_CONTEXT`/
    `REQUEST_CHANGES` dispatch itself is **Mechanical/collapsible** (deterministic verdict-field
    branch); the `APPROVE` branch's mandatory NIT-fix dispatch and the `REQUEST_CHANGES` branch's
    fixer dispatch are each the same **Borderline** "## Agent-mode dispatch" pattern (bracket a
    fixer Agent call), not re-classified per call site; `NEED_CONTEXT`'s missing-file existence
    check and its "same files as before" non-progress detection are **Mechanical/collapsible**
    (deterministic path-existence/set-comparison, no judgment).
  - **Step 4.5: ERROR-only-aggregate retry** (lines 858-874) — **Borderline**, identical reasoning
    and recommendation to `mill-plan`'s/`mill-start`'s equivalent ERROR-retry steps.
  - **Step 5: Max-rounds exhaustion** (lines 876-878) — **Mechanical/collapsible**. Unlike
    `mill-plan`'s step 5/6 (which are deliberately never auto-escaped), this is a fixed
    `_notify.notify`+`set_batch_field`+`append_phase`+commit sequence with one fixed message and no
    live-waiver escape hatch — no operator judgment is layered on top of the mechanical bookkeeping,
    so it stays Mechanical rather than Borderline.
- **### Stuck escalation** (lines 880-926) — per-`stuck_type` one-shot self-resolve-then-escalate
  rules (`infrastructure`, `transient`, `incomplete`, `verify`/`logic`) — **mixed**. The
  re-dispatch/escalation bookkeeping for `infrastructure`/`transient`/`incomplete` is
  **Mechanical/collapsible** (fixed retry-once-then-`blocked` shape, deterministic branch on
  `commits_made`); the `verify`/`logic` self-resolve is **Excluded** — "investigate the failure
  using the same judgment an implementer/fixer already applies" is explicitly a judgment call, and
  its optional plan-edit + new-card-append step is genuine authoring, not a fixed shape (though the
  `compute_next_card_number`/`_check_card_numbering` calls it may invoke are themselves
  Mechanical/collapsible helper calls, already scripted).
- **### Blocked** (lines 928-937) — notify, release builder lock, tell the user a fixed message —
  **Mechanical/collapsible**. Two deterministic calls plus one fixed string; already near the
  1-turn floor.
- **## Resume / ## Holistic code review / ## Handoff** (lines 939-949) — each a bare
  "read this file now" pointer into a companion `.md` file (`resume.md`, `holistic-review.md`,
  `handoff.md`) — **Excluded** from this file's own classification. These headings carry no inline
  step content of their own to classify; the companion files they point to are outside this card's
  `Context:` (mill-go-base/SKILL.md only) and are recorded in `## Follow-up backlog candidates`
  below as an explicit scope note, not silently folded into this audit.

## Cross-cutting recommendations

_Filled by card 4._

## Follow-up backlog candidates

_Filled by card 4._

## Coverage check

_Filled by card 4._
</content>
