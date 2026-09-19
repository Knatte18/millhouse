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

_Filled by card 2._

## mill-go-base

_Filled by card 3._

## Cross-cutting recommendations

_Filled by card 4._

## Follow-up backlog candidates

_Filled by card 4._

## Coverage check

_Filled by card 4._
</content>
