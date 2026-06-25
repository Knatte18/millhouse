# Discussion: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation

```yaml
task: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation
slug: mill-spawn-and-workflow-integrity
status: discussing
parent: main
```

## Problem

Six real-world failures surfaced during live mill runs (GitHub issues #537, #540,
#541, #542, #543, #544 — #543 contains two distinct sub-bugs) expose integrity gaps
across three areas of the workflow:

1. **Spawn/teardown lifecycle (#543, #544).** Abandoning or cleaning up a task leaves
   `origin/<slug>` alive (abandon even pushes an `abandon` marker commit onto it), so
   re-spawning the same slug dies on a non-fast-forward push — and the half-built
   worktree/junctions/local-branch from the failed spawn are stranded. Separately, the
   multi-select spawn picker flipped an **un-selected** task to `active` with zero
   artifacts (no worktree/branch/portal), and there is no pre-check or rollback. On top
   of that, docs/CLI-help advertise an `[s]` "spawn-ready" status that the V3 wiki
   backend silently retired — marking a task `[s]` makes it *unspawnable*.

2. **Agent-mode dispatch async assumption (#537).** mill-go's "Agent-mode dispatch"
   pattern (inherited by mill-plan, mill-start, mill-merge-in) asserts the Agent tool is
   **synchronous** and returns the subagent's final message inline. In the Claude Code
   harness it launches **asynchronously** ("Async agent launched...") and the result
   arrives later via a `<task-notification>`. The documented "capture the return value
   and write `.out.md`" flow has nothing to capture at call time, and there is no
   documented handling for a stopped/interrupted background agent.

3. **Verify & failure-attribution integrity (#540, #541, #542).** The merge-in conflict
   sub-agent picks one side of a conflict **wholesale** when each side edits
   non-overlapping parts of the same region (e.g. different columns of one table row),
   silently discarding the other side. Per-batch verify in mill-go never re-checks
   already-approved batches, so a batch that edits a widely-imported shared test helper
   can break *other* packages undetected until a later batch happens to verify them. And
   the implementer brief lets a batch label an in-task regression as a "pre-existing"
   verify failure without ever checking it against the parent branch.

**Why now:** all six were hit in live `loomyard`/mill sessions in the last few days and
required manual recovery (hand-merging a discarded table row, manual junction/branch/
remote cleanup, `set_phase(slug, None)` to un-strand a falsely-claimed task, manual
Builder takeover for a mislabeled regression). They are consolidated into this one
hardening task.

## Scope

**In:**

- **#543a — remote-branch teardown.** Abandon deletes `origin/<branch>` instead of
  pushing an abandon-marker commit; cleanup deletes `origin/<branch>` after the local
  `branch -D`/`-d`. Both ignore "remote ref does not exist".
- **#543b — spawn atomicity.** Pre-check `origin/<branch>` existence and fail *before*
  creating worktree/junctions/branch; roll back any partial worktree/junctions/wiki-claim
  if a later spawn step (notably the `--set-upstream` push) fails.
- **#543b — picker over-claim.** Root-cause and fix the multi-select spawn path so only
  the slugs the user actually selected are ever claimed/removed.
- **#543b — reconciliation.** Cleanup resets any task that is `active` in Home.md but has
  **no worktree, no local branch, and no portal** back to unclaimed (`status None`).
- **#544 — drop `[s]`.** Remove every stale `[s]`/"spawn-ready" reference from
  `millpy-spawn.py`, `millpy-claim.py`, `mill-groom/SKILL.md`, and `_spawn_core.py`
  docstrings so docs match the already-retired backend behavior.
- **#537 — async dispatch docs.** Rewrite mill-go "## Agent-mode dispatch" (steps 3, 5,
  and "Agent-mode properties") to describe asynchronous launch + wait-for-notification +
  capture-from-notification + re-dispatch-on-interrupt; correct the synchronous /
  no-detached-worker / no-liveness assertions. Reconcile inheritor wording.
- **#540 — merge-in combine + reporting.** Strengthen `merge-in-conflict-brief.md` to
  combine non-overlapping intra-hunk edits, and add an optional discarded-content field
  to the success schema that `mill-merge-in` surfaces to the operator.
- **#541 — module-wide verify.** Wire the currently-dead top-level `verify:` slot in
  `plan-overview.md` as an optional module-wide check run at each batch boundary.
- **#542 — pre-existing validation.** Add a `<PARENT_BRANCH>` render token and require the
  implementer brief to validate any "pre-existing" failure against the parent branch
  before emitting `stuck_type: verify`.

**Out:**

- **Not** re-implementing `[s]` as a live status — the V3 backend deliberately retired it
  (parse→`None`, render→`None`); we make the docs honest, not resurrect the concept.
- **Not** redesigning the multi-select *fold-then-claim merge* semantics — merging several
  backlog entries into one is intended; we only guarantee no *unselected* slug is touched
  and that the claim is atomic with artifact creation.
- **Not** making the module-wide verify mandatory — it is opt-in via `plan-overview.md`'s
  `verify:` (null ⇒ skip), so existing plans are unaffected.
- **Not** changing the V3 wiki status grammar/parser/renderer, review cadence/rounds, or
  `mill-finalize` beyond what `mill-merge-in` newly surfaces.
- **Not** changing the Agent tool itself or `_agent_dispatch.resolve_dispatch_mode` — #537
  is a documentation-of-behavior fix to the SKILL, not a code change to dispatch.

## Decisions

### s-marker-drop (#544)

- Decision: Drop `[s]` entirely. Remove the stale references at
  `millpy-spawn.py:8,87,122-123`, `millpy-claim.py:13,144,176-177`,
  `mill-groom/SKILL.md:67,82,115`, and the fictional "[s] fast-path" docstrings at
  `_spawn_core.py:21,28`. Align the `millpy-spawn`/`millpy-claim` "No pickable tasks"
  messages with the already-corrected `pick_task_single` `BacklogEmpty` text
  ("Leave one unmarked").
- Rationale: The backend already collapses `[s]`→`None` on both parse (`wiki/_parse.py:61-65`)
  and render (`wiki/_render.py:154-155`), and never emits an `[s]` marker. The picker's
  `status is None` filters are correct for the V3 model; only the user-facing strings lie.
- Rejected: Re-implementing `[s]` as a real pickable state — would mean un-collapsing it in
  parser+renderer and adding `status in (None, "s")` to three filters, reintroducing a
  concept the backend intentionally removed, for no behavioral gain.

### remote-branch-teardown (#543a)

- Decision: Teardown deletes the remote branch. **Abandon** (`millpy-abandon.py:110-114`)
  replaces its `git push` (which currently pushes the `task: abandon <slug>` marker commit)
  with `git push origin --delete <branch>`, treating "remote ref does not exist" as success.
  **Cleanup** (`millpy-cleanup.py` `_apply_worktree_record` after the `branch -D` at ~484,
  and `_apply_inplace_record` after the `branch -d/-D` at ~422-424) adds the same
  `git push origin --delete <branch>` for the done/normal teardown path.
- Rationale: The canonical abandon record lives in the wiki (`Home.md` `[abandoned]`), not on
  the branch, so dropping the marker commit loses nothing. Deleting the remote on both paths
  makes re-spawn of the same slug a clean fast-forward and is idempotent (missing-ref ignored).
- Rejected: Keeping the abandon-marker commit and only deleting in cleanup — leaves a window
  where an abandoned-but-not-cleaned slug still blocks re-spawn, and keeps a remote artifact
  with no consumer.

### spawn-atomicity (#543b)

- Decision: (a) **Pre-check** — in `millpy-spawn.py`, right after `branch_name` is computed
  (~line 142) and before `_worktree.create` (~line 172), run a remote existence check
  (`git ls-remote --exit-code origin <branch>` or `git fetch`-free `ls-remote`); if the
  remote branch already exists, fail fast with a clear message before any worktree/junction/
  branch is created. (b) **Rollback** — wrap the side-effecting span (wiki claim → worktree →
  `.millhouse` copy → portal junction → hub links → `.active` junction + indicator → vscode →
  `write_initial_status` push at `_spawn_core.py:687-694`) so that if any step fails, the
  already-created artifacts are unwound in LIFO order: remove `.vscode` settings, strip the
  `.active`/portal/hub-link junctions, `_worktree.remove_safe(...)` (which also drops the local
  branch), and revert the Home.md claim via `wiki.set_phase(slug, None)`.
- Rationale: A push failure currently raises `RuntimeError` uncaught, stranding every artifact
  for `mill-cleanup` to later report as orphans. Pre-check turns the most common failure
  (surviving `origin/<branch>`) into a no-side-effect error; rollback covers the rest.
- Rejected: Pre-check only (no rollback) — still strands artifacts on any other mid-spawn
  failure. Rollback only (no pre-check) — does the work then immediately unwinds it; the
  pre-check is the cheap fast-path.

### picker-over-claim (#543b)

- Decision: Root-cause the multi-select path (`_spawn_core.pick_task_single_or_multi` →
  `_prompt_numbered_multi` → `millpy-spawn.multi_select_groom_then_claim` →
  `wiki.merge_tasks(remove_slugs=source_slugs, set_phase=(merged_slug,"active"))`) and
  guarantee that the set of slugs removed/claimed equals exactly the user's selection. The
  observed bug (un-selected `internal-mux` flipped to `active` with zero artifacts) means a
  slug outside the selection reached a claim/`set_phase("active")` — the implementer must
  trace where the selection→`source_slugs`→`merge_tasks` chain diverges (candidate suspects:
  `render_order` vs displayed order, a claim performed before selection at `millpy-spawn.py:134`,
  or `merge_tasks` set_phase target) and close it. The claim must be atomic with artifact
  creation (see spawn-atomicity) so a partial run never leaves a claimed-but-artifactless task.
- Rationale: Index→task mapping in `_prompt_numbered_multi` (`candidates[idx-1]`, line 377) is
  correct in isolation, so the divergence is upstream/downstream of it; the fix must be
  evidence-driven, not a guess. Atomicity is the structural guarantee the issue asks for.
- Rejected: Treating reconciliation alone as the fix — self-heals the symptom on the next
  cleanup but leaves the race that mis-claims tasks during the run.
- **Plannability (root cause is unlocated, so the batch is structured to ship regardless):**
  The plan's **first card for this batch is an explicit reproduce-and-locate step** with a
  concrete acceptance criterion — a regression test that drives the reported scenario (select
  one of two backlog tasks, assert the *other* stays `None`) and is **red** before the fix,
  **green** after. The implementer locates the divergence (suspects above) and closes it.
  Crucially, the **guaranteed-shipping deliverables are atomicity (spawn-atomicity decision)
  and reconciliation (orphan-reconciliation decision)**: even if the over-claim race turns out
  to be environmental/non-reproducible, those two structural guarantees alone prevent a
  claimed-but-artifactless task from persisting, so the batch is completable and the regression
  test still pins the picker's selection→claim contract. mill-plan should therefore write this
  batch with the locate-card first and atomicity+reconciliation as independent, always-landing
  cards, not contingent on root-causing the race.

### orphan-reconciliation (#543b)

- Decision: `millpy-cleanup.py` gains a reconciliation step: any task marked `active` in
  Home.md that has **no worktree, no local branch, and no portal junction** is reset to
  unclaimed (`wiki.set_phase(slug, None)` + rerender). This rides on cleanup's existing
  orphan-detection plan (`build_plan`, e.g. the orphan-worktree / orphan-Home.md-marker
  reports around `millpy-cleanup.py:219-264`).
- Rationale: A backstop that converges the board to a consistent state regardless of how a
  task got mis-claimed (the picker bug, an interrupted spawn, a manual edit).
- Detection seam (what cleanup already has vs. what to add): `build_plan` already enumerates
  every signal needed except local-branch presence — registered git worktrees
  (`_worktree.list_worktrees`), `wts/` dirs on disk (`wts_slugs_on_disk`), `.active`-junction
  slugs (`active_slugs`), Home.md markers (`marker_by_slug` / `home_tasks`), and orphan portals
  (`_scan_orphan_portals(container/portals, active_slugs)`). The **"orphan Home.md marker"**
  branch (`millpy-cleanup.py:255-264`) **already detects exactly the active-with-no-worktree
  case** (`marker in {active,ready-to-merge,pr-pending} and slug not in active_slugs and slug
  not in wts_slugs_on_disk`) — but today it only **appends a `REPORT:` line**, it does not reset.
  Reconciliation is therefore: **promote that existing detection from report-only to an actual
  `wiki.set_phase(slug, None)` reset**, gated narrowly on the orphan being `active` (not
  `ready-to-merge`/`pr-pending`, which are live PR states) AND having no portal
  (`_scan_orphan_portals` reuse — no new cross-platform junction probe) AND no local branch
  (the **one** signal not already enumerated: add a `git branch --list <branch>` check). Junction
  presence is probed via the existing portal scan, not a hand-rolled `os.path` test.
- Rejected: A standalone `millpy-reconcile.py` — cleanup already enumerates worktrees/branches/
  portals and is the natural teardown reconciliation point; a new CLI is redundant surface area.

### dispatch-async-docs (#537)

- Decision: Rewrite mill-go "## Agent-mode dispatch" (`mill-go/SKILL.md:105-141`):
  - Step 3: the Agent tool launches a **background** subagent and returns immediately
    ("Async agent launched..."); the orchestrator must **wait for the completion
    `<task-notification>`** for that agent and read the subagent's final message from it.
  - Step 5: write **the message captured from the notification** to `<brief_path>.out.md`
    (not "the Agent's returned value").
  - "Agent-mode properties": correct line 136 ("the Agent tool is synchronous") and line 137
    ("no detached worker") — a background agent *is* a detached worker that can be stopped/
    interrupted; document re-dispatch of a stopped/interrupted background agent via the
    existing `transient` one-retry path (step 4 already covers raw API errors).
  - Reconcile the inheritor references (`mill-plan/SKILL.md:138,144,176`,
    `mill-start/SKILL.md:131,159`, `mill-merge-in/SKILL.md:48,62`) so none of them locally
    re-assert synchronous return; they delegate to the corrected mill-go section.
- Rationale: The docs must match the harness's actual async behavior or every agent-mode
  dispatch repeats the #537 failure (nothing to capture inline, no interrupt handling).
- Rejected: A code shim that blocks until completion — the Agent tool's async contract is the
  harness's, not mill's; the fix is documentation of the real protocol, not fighting it.

### merge-in-combine (#540)

- Note on the current brief: step 3 (line 27) **already** reads "Write a resolution that
  preserves the intent of both sides", and line 36 already forbids `git checkout --ours/--theirs`.
  So the abstract instruction is present; the observed #540 failure was **model non-compliance**
  with that abstract guidance, not a missing instruction. The fix therefore **sharpens
  enforcement**, it does not add absent guidance.
- Decision: (a) In `templates/merge-in-conflict-brief.md` step 3 (line 27), **sharpen** the
  existing "preserve the intent of both sides" line with a **concrete worked example**: when
  both sides modify **different, non-overlapping parts of the same region** (e.g. different
  columns of one table row, different keys of one object), **combine both edits** into a single
  resolved line/structure; picking one side wholesale is correct only when the two sides are
  genuinely mutually exclusive. The worked example is what converts the abstract rule into
  something the model reliably follows. (b) Extend the success report schema
  (lines 38-50) with an optional `discarded` / `warnings` array; if the resolver must drop
  any content from one side it MUST list it. (c) `mill-merge-in/SKILL.md` step 3 (line 48)
  reads that field on `{"status":"success"}` and surfaces any discards to the operator
  rather than silently `merge --continue`.
- Rationale: Issue #540 asks for "combine both intents, or at minimum surface that one side
  was discarded" — doing both gives prevention *and* a non-silent safety net for the cases
  the model still gets wrong.
- Rejected: Instruction-only (a silent wholesale pick stays silent on model error) or
  reporting-only (surfaces losses but doesn't steer the model toward the correct merge).

### module-wide-verify (#541)

- Decision: Wire `plan-overview.md`'s currently-dead top-level `verify:` (line 33) as an
  **optional module-wide check** that runs at **each batch boundary**, after the batch's own
  `verify:` passes. Null ⇒ skip (no behavior change for existing plans). The check reuses the
  existing verify-gate machinery so a failure produces `stuck_type: verify`, pinpointing the
  *introducing* batch rather than surfacing two batches later. Preferred implementation seam:
  `millpy-implement.py` reads the overview `verify:` (it already has `OVERVIEW_FILE`) and
  `_implementer_common._run_verify_gate`/`_forward_output` runs it as a second gate after the
  batch verify; the alternative seam (mill-go orchestrating a module-wide verify between
  batches) is acceptable if mill-plan finds it cleaner — leave the final seam to the plan.
- Rationale: Language-agnostic (the plan author writes the command, e.g. `go vet ./...` or a
  Python `run-all.py`), opt-in, and catches cross-package regressions from shared-helper edits
  at the boundary where they are introduced. Reuses a dead schema slot instead of adding new
  config surface.
- Rejected: Handoff-only module-wide verify (intermediate batches still approve green; can't
  pinpoint the batch). Re-running the *union* of all prior batches' verify on a shared-helper
  touch (needs shared-helper-path detection config and grows cost per batch; the single
  overview-level command is simpler and the plan author already knows the cheap module check).

### pre-existing-validation (#542)

- Decision: Add a `<PARENT_BRANCH>` render token to the implementer brief
  (`millpy-implement.py:324-339`; the value is already resolved at ~line 224). In
  `templates/implementer-brief.md` `## Verify` (lines 68-75, before the `stuck_type: verify`
  emission at line 73) and the enum definition (line 103), require: before reporting any
  failure as "pre-existing"/"unrelated to my changes", confirm it reproduces on the parent
  branch — e.g. `git log <PARENT_BRANCH>..HEAD -- <files in the failure's import/dependency
  chain>` (a same-task commit touching those files ⇒ **not** pre-existing) or `git show
  <PARENT_BRANCH>:<path>` / stash+checkout-parent. If it does **not** reproduce on parent,
  treat it as in-scope: fix it, or escalate `logic` — never label it "pre-existing verify".
  The brief already permits `git -C <parent-path> ...` reads (`## Cross-worktree isolation`,
  lines 122-129).
- Rationale: An unverified "pre-existing" claim waves through regressions the current task
  caused (exactly what happened: a batch-2 `lyxtest→configreg` import cycle was mislabeled
  pre-existing by a later batch) and misdirects the orchestrator into a manual takeover.
- Rejected: Relying on the receive-review "Pre-existing issue" forbidden-dismissal
  (`mill-receiving-review/SKILL.md:45`) — that governs dismissing *reviewer findings*, not the
  `stuck_type: verify` self-report path, which has no validation requirement today.

## Technical context

Key files and the precise seams (verified during exploration):

**Spawn / claim / teardown**
- `plugins/mill/scripts/_spawn_core.py` — three pickability filters all on `status is None`:
  `pick_task_single` numbered (`~298-305`, `BacklogEmpty` `~302-305`), `--slug` (`~287-296`),
  `pick_task_single_or_multi` `--slug` + multi (`~411-432`). `_prompt_numbered_multi`
  (`~313-379`) maps indices via `candidates[idx-1]` (line 377). `multi_select_groom_then_claim`
  (`~435-483`) calls `wiki.merge_tasks(remove_slugs=source_slugs, upsert=..., set_phase=(merged_slug,"active"))`
  (`~477-482`). `write_initial_status` push at `~687-694`. Stale "[s] fast-path" docstrings
  `~21,28`.
- `plugins/mill/scripts/millpy-spawn.py` — `main` side-effect order with no rollback:
  claim_in_wiki (`158`; multi claim earlier at `134`), capture_parent_branch (`164`),
  `_worktree.create` (`171-172`), copy_millhouse (`181-185`), portal junction (`191-194`),
  `_setup.create_hub_links` (`200-201`), `.active`+indicator (`206-207`), vscode (`213-215`),
  `write_initial_status` (`227-235`). Multi branch `128-139`. Stale `[s]` strings `8,87,122-123`.
- `plugins/mill/scripts/millpy-claim.py` — stale `[s]` strings `13,144,176-177`.
- `plugins/mill/scripts/millpy-abandon.py` — appends `abandoned` phase, commits
  `task: abandon <slug>`, `git push` (`97-114`). Runs from the task worktree against
  `active_hub`.
- `plugins/mill/scripts/millpy-cleanup.py` — `_apply_worktree_record` local `branch -D`
  (`~475-484`), `_apply_inplace_record` `branch -d/-D` (`~421-424`), archive-tag push
  (`~570-575`); `build_plan` orphan detection (`~219-264`). No remote-branch delete anywhere.
- `plugins/mill/scripts/_worktree.py` — `remove`/`remove_safe` (`146-276`), junction-stripping
  + safe rmtree; **must** strip junctions before any deletion (see CLAUDE.md path invariants).
- Wiki backend (do **not** change): `wiki/_parse.py:40,61-65` (`[s]`→None), `wiki/_render.py:154-155,170`
  (renderable markers: active/done/pr-pending/ready-to-merge/abandoned; `s`→None),
  `wiki/_store.py:263-272` (`set_phase` does no enum validation), `_client.merge_tasks`/`set_phase`.

**Dispatch / verify / brief**
- `plugins/mill/skills/mill-go/SKILL.md:105-141` — canonical "Agent-mode dispatch"; inheritors
  at `mill-plan/SKILL.md:138,144,176`, `mill-start/SKILL.md:131,159`,
  `mill-merge-in/SKILL.md:48,62`.
- `plugins/mill/scripts/millpy-merge-in-subagent.py` — `_run_conflicts` (`223-261`) renders
  `templates/merge-in-conflict-brief.md`; just forwards the JSON verdict via `_forward_output`.
- `plugins/mill/templates/merge-in-conflict-brief.md` — instructions `21-36` (step 3 = line 27),
  report schema `38-50`.
- `plugins/mill/templates/plan-overview.md:33` — dead top-level `verify:`; per-batch `verify:`
  in `plan-batch.md:24-31` and mirrored in the overview Batch Index (`plan-overview.md:42-49`).
- `plugins/mill/scripts/millpy-implement.py` — reads single batch `verify` at `246-258` and
  `401-414`; brief render-token map `324-339` (no parent-branch token); `parent_branch`
  resolved `221-226`; `classify_stuck_type` `42-65`.
- `plugins/mill/scripts/_implementer_common.py` — `_run_verify_gate` (`328-390`), invoked from
  `_forward_output` (`534-856`) at `567,692-714,746,802`, all with the single batch `verify_cmd`.
- `plugins/mill/templates/implementer-brief.md` — `## Verify` `68-75`, stuck enum `## Report`
  `95,101-104`, cross-worktree git reads permitted `122-129`.

## Constraints

- **ASCII-only stdout** in `print()`/`_log()` (Windows cp1252): `—`→` -- `, `->`→` -> `.
- **Junctions stripped before any deletion** — rollback/cleanup paths must call
  `_junction.strip_all_in_worktree` / `_worktree.remove_safe`, never raw `rmtree`/`rmdir /s`,
  or they wipe the shared wiki/portals targets.
- **No direct wiki cd/edit** — claim reverts and reconciliation go through `wiki.set_phase` /
  `_client`, never by editing `Home.md` in the wiki clone.
- **Path resolution only through `_paths.py`**; helpers with path args must not consult cwd.
- **`verify:` command shape** — Python project: plan `verify:` commands start with
  `PYTHONPATH=` (literal, empty); the new module-wide overview `verify:` follows the same rule
  and is validated by `_plan_validate.py`'s `verify-not-isolated` check.
- **`mill-config.yaml` hub file and plugin template stay in sync** if any config key is added
  (none currently required — `[s]` removal and `verify:` wiring touch no config schema).
- Doc/SKILL edits are not unit-testable; they must stay internally self-consistent and pass
  the discussion/plan review gates.

## Testing

Add/extend unit tests under `plugins/mill/unit_tests/` (in-memory/tempfile fixtures, no real
git/LLM, run via `run-all.py`; `uv run --project plugins/mill`):

- **#544 `[s]` cleanup** — assert the spawn/claim "No pickable tasks" messages and `--slug`
  help no longer contain `[s]`; assert `_spawn_core` docstrings no longer claim a fast-path.
  (TDD candidate: cheap string assertions.)
- **#543a remote delete** — `millpy-abandon` issues `git push origin --delete <branch>` (not a
  marker push) and treats missing-ref as success; `millpy-cleanup` `_apply_worktree_record` /
  `_apply_inplace_record` issue the same delete after local branch deletion. Mock
  `_subprocess_util.run`; assert the argv sequence and missing-ref tolerance.
- **#543b spawn pre-check + rollback** (TDD candidate) — when `ls-remote` reports the branch
  exists, spawn fails before `_worktree.create` (assert no worktree/junction/claim side effects);
  when a later step (push) fails, all created artifacts are unwound in LIFO order and the wiki
  claim is reverted via `set_phase(slug, None)`. Use fakes/mocks for git + junction calls.
- **#543b picker over-claim** (TDD candidate) — drive `pick_task_single_or_multi` /
  `multi_select_groom_then_claim` with a fixture board and assert that the set of removed/
  claimed slugs equals exactly the selected indices; add a regression case mirroring the
  reported scenario (select one of two, assert the other stays `None`).
- **#543b reconciliation** — given a Home.md `active` task with no worktree/branch/portal,
  `millpy-cleanup` reconciliation resets it to `None`; a genuinely-active task with artifacts is
  left untouched.
- **#541 module-wide verify** — overview `verify:` set ⇒ runs as a second gate after batch
  verify and a failure yields `stuck_type: verify`; `verify: null` ⇒ no extra command runs
  (existing plans unaffected). Mock the verify subprocess.
- **#542 parent-branch token** — `millpy-implement` brief render includes the `<PARENT_BRANCH>`
  token populated from the resolved parent; assert the brief text contains the parent-branch
  name and the validation instruction.

Doc/template-only changes (**#537** mill-go async rewrite, **#540** merge-in brief + schema
prose, the **#541** and **#542** brief/template wording) have no unit harness — verify by
self-consistency and the discussion/plan/code review gates. For #540, optionally assert that
`mill-merge-in` reads a `discarded`/`warnings` field if the schema field is consumed in Python
(`_forward_output` / verdict parsing); otherwise it is prose-only and review-verified.

## Q&A log

- **Q:** How should mill-go catch cross-package regressions from shared-helper edits (#541)? **A:** [auto-pick] Module-wide check per batch boundary — wire `plan-overview.md`'s dead top-level `verify:` as an opt-in module-wide gate run after each batch's own verify. **Why:** Language-agnostic (plan author writes the command), reuses a dead schema slot, and catches the regression at the introducing batch (yielding `stuck_type: verify`) instead of two batches later; handoff-only can't pinpoint the batch and union-re-run needs shared-helper detection config.
- **Q:** Scope for the spawn/claim integrity fixes (#543b)? **A:** [auto-pick] All three — pre-check+rollback, root-cause the multi-select over-claim, and cleanup reconciliation. **Why:** The issue's comment requests all three (atomic claim/rollback, "only claim selected slugs", and reset orphaned-active tasks); reconciliation alone self-heals the symptom but leaves the mis-claim race, and pre-check alone still strands artifacts on other failures.
- **Q:** How far to fix the merge-in conflict sub-agent (#540)? **A:** [auto-pick] Instruction + reporting field — strengthen "combine non-overlapping edits" in the brief AND add an optional discarded-content field the operator sees. **Why:** Issue #540 asks for "combine both intents, or at minimum surface that one side was discarded"; doing both gives prevention plus a non-silent safety net for cases the model still gets wrong.
- **Q:** Direction for the `[s]` spawn-ready mismatch (#544)? **A:** [auto-pick] Drop `[s]` entirely — remove all stale strings/docstrings/help. **Why:** The V3 backend already retired `[s]` (parse→None, render→None, never emitted) and the `status is None` picker filters are correct; only the user-facing strings lie. Re-implementing `[s]` would reintroduce a deliberately-removed concept for no behavioral gain.
- **Q:** Should abandon delete `origin/<branch>` or only cleanup? **A:** [auto-pick] Abandon deletes the remote (replacing the marker-commit push) AND cleanup deletes it on the done path. **Why:** The canonical abandon record is the wiki `[abandoned]` marker, so the marker commit has no consumer; deleting on both paths makes re-spawn a clean fast-forward and is idempotent (missing-ref ignored), with no window where an abandoned-not-cleaned slug blocks re-spawn.
- **Q:** How to fix the #537 async assumption — doc rewrite or a blocking code shim? **A:** [auto-pick] Doc rewrite of mill-go "Agent-mode dispatch" (steps 3/5 + properties) plus inheritor reconciliation. **Why:** The Agent tool's async launch + task-notification result is the harness's contract; the fix is documenting the real protocol (launch → wait for notification → capture → write `.out.md`, re-dispatch on interrupt), not fighting it with a shim.
- **Q:** Where does the #542 parent-branch validation live and how is the parent named? **A:** [auto-pick] Add a `<PARENT_BRANCH>` render token (value already resolved in `millpy-implement.py`) and require the brief to confirm a "pre-existing" failure reproduces on the parent before `stuck_type: verify`. **Why:** The brief already permits `git -C <parent-path>` reads but can't name the parent today; a same-task commit touching the failing files proves it is a regression, not pre-existing.
- **Q:** Testing strategy across the seven fixes? **A:** [auto-pick] Unit tests for every Python-code change (spawn pre-check/rollback, abandon/cleanup remote delete, reconciliation, picker over-claim, module-wide verify gate, parent-branch token, `[s]` string cleanup); doc/template changes verified by self-consistency + review gates. **Why:** Python seams are deterministically testable with in-memory/tempfile fixtures per repo convention; SKILL/template prose has no unit harness and relies on the review gates.
```
