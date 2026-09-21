# Batch: doc-fixes

```yaml
task: mill-plan/mill-start planning-process gaps, round 2
batch: doc-fixes
number: 1
cards: 8
verify: null
depends-on: []
```

## Batch Scope

This batch fixes seven of the eight planning-process gaps by editing prose only, in two files: `plugins/mill/skills/mill-plan/SKILL.md` (cards 1–7) and `plugins/mill/skills/mill-start/SKILL.md` (card 8). No script or test file changes. Each card is an independent, precisely-anchored text edit — none depend on another card's edit to make sense, so they can be applied in any order, though card numbering below gives a safe sequential order (cards 3 and 6 both touch the same two paragraphs; card 3 must land before card 6 reads its anchor text, so implement cards in ascending order within this batch). The next three batches (2–4) deliver the three code-level fixes; this batch's card 7 documents the check batch 4 implements, using the identical check name and remedy text so the two stay consistent regardless of landing order (see overview Shared Decisions).

## Cards

### Card 1: mill-plan Entry table — row for `phase: discussed` with an existing `plan_dir`

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the Entry step-4 table (the `| state | action |` table under "Decide entry branch:"), insert a new row immediately after the existing row whose state column reads `` `phase: discussed`, no `plan_dir` dir at worktree root `` and immediately before the existing row whose state column reads `` `phase: planning`/`plan-review-*`/`plan-fix-*`, `plan_dir/00-overview.md` exists, `approved: false` ``. Match the table's existing row indentation (3-space indent before the leading `|`, e.g. `   | ... | ... |`). New row text:

  ```
  | `phase: discussed`, `plan_dir/00-overview.md` exists at worktree root | Phase: Plan Review (re-enter loop; do NOT rewrite plan files) — Phase: Plan's file writes landed but its own `phase: planning` status commit did not; the validator gate (Step 1.5) still re-checks the plan before any reviewer runs |
  ```

  This closes the gap where `phase: discussed` plus an already-written `plan_dir` (from an interrupted Phase: Plan run, or a deliberate draft-now/finalize-later split) matched no table row and fell through to the catch-all.
- **Commit:** `docs(mill-plan): Entry table row for phase: discussed with existing plan_dir`

### Card 2: mill-plan batch-sizing guidance — split by edited-file union size

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Two edits in the "Batch sizing" section (under `### Phase: Plan`):

  1. Immediately after the sentence "If two adjacent batches share >80% of their `Context:`, merge them." (and before the sentence beginning "The planner must keep each batch within"), insert this new sentence:

     "When a batch's cards collectively cite several large pre-existing files whose combined `Context:`/`Edits:`/`Creates:` byte total exceeds `pipeline.max_batch_context_tokens` even though no single file does, split by which file each card edits rather than by feature/mechanism — this keeps each resulting batch's own file-union under cap even when the underlying mechanisms are tightly coupled."

  2. In the Step 1.5 fix table (under `### Phase: Plan Review`), the `batch-oversized` row currently begins "Before concluding a batch cannot be split, check whether a large `Context:` entry exists only to satisfy `context-completeness`..." and continues "For every other case: Halt — the batch exceeds...". Insert this new sentence into that same table cell, immediately before "For every other case: Halt":

     "When the overage comes from the combined size of several large pre-existing files (not any single one) and the `context-completeness` signature-inlining escape hatch doesn't apply to any of them, split the batch by edited-file union size rather than by feature — group cards so each resulting batch's own file-union stays under cap, even if that means separating cards that would otherwise belong together by every other batch-sizing heuristic."

  Keep the table's pipe-delimited single-line-per-row format — the inserted sentence goes inside the existing `batch-oversized` row's second column, not as a new row.
- **Commit:** `docs(mill-plan): batch-sizing guidance for combined-large-file overage`

### Card 3: mill-plan `discussion_sha` git command — nested-layout fix (3 sites)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  This file contains the exact literal substring `` git -C <git_root> rev-parse HEAD:_mill/discussion.md `` in exactly three places: Phase: Plan's initial `discussion_sha` capture sentence, Phase: Plan's "Pre-commit drift check" paragraph, and Phase: Plan Review's "Discussion drift guard" paragraph. Replace all three occurrences with:

  ```
  git -C <worktree_root> rev-parse HEAD:./<cfg['paths']['discussion_file']>
  ```

  i.e. run `-C` against `worktree_root` (the hub root, already bound at Entry step 1) instead of `git_root`, and prefix the path with `./` so git resolves it relative to the `-C` cwd instead of the repository top level, reading the path from `cfg['paths']['discussion_file']` instead of the literal string `_mill/discussion.md`. This form is correct both in a flat layout (`worktree_root == git_root`, this repo today) and a nested layout (`worktree_root` a subdirectory of `git_root`), with no branching logic needed. Do not change any surrounding prose in these three sites beyond this one substitution each — card 6 makes a separate, additional edit to two of these same three paragraphs; land this card first.
- **Commit:** `fix(mill-plan): discussion_sha drift guard uses hub-relative git path`

### Card 4: mill-plan Plan Review — "Finalize advances the round" paragraph

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### Phase: Plan Review`, step 2's dispatch instructions, insert a new paragraph immediately before the sentence beginning `` If `agent` (Claude provider only): follow the Agent-mode dispatch pattern `` (this is the branch line that starts the Agent-mode-vs-subprocess split; do NOT insert before step 2's earlier "Waiting is never a decision point" / dispatch-mode-resolution text, which precedes this branch line by several paragraphs). New paragraph:

  "**Finalize advances the round.** `--stage finalize` is what writes the review file into `reviews_dir` and is therefore what makes the next `--stage prepare`'s round-discovery advance past this round number — reading the reviewer's `.out.md` file directly is not equivalent to calling finalize. Always call `--stage finalize` before evaluating or acting on a round's findings, even when the findings are already fully visible in the `.out.md` file; skipping it silently re-issues the same round number next time, since `write_brief`'s own next call for this round unconditionally deletes the just-produced `.out.md` before writing a fresh brief (see `_agent_dispatch.write_brief` in `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" section)."
- **Commit:** `docs(mill-plan): state the finalize-advances-the-round contract`

### Card 5: mill-plan Plan Review — number the "Unconditional round-recorded append" step

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### Phase: Plan Review`, the paragraph heading currently reads exactly `**Unconditional round-recorded append.**` (sitting between the Step 3.5 section and step 4a). Replace that heading text with:

  ```
  **Step 3.6: Unconditional round-recorded append (no round consumed).**
  ```

  Change only the heading text itself — the paragraph body that follows it (describing the `_status.append_phase(status_path, f"plan-review-r{N}", ...)` call and commit) is unchanged. This matches the file's existing `1.5.`/`3.5.` numbering convention for a same-round side-step between two main numbered steps, so the step reads as a mandatory action in sequence rather than as background prose explaining 4a/4b/4c's own appends.
- **Commit:** `docs(mill-plan): number the round-recorded-append step 3.6`

### Card 6: mill-plan drift-guard halts — point at `/mill-descope-batch` for pure narrowing

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Two of the three `discussion.md`-drift halt sites edited by card 3 above (Phase: Plan's "Pre-commit drift check" paragraph, and Phase: Plan Review's "Discussion drift guard" paragraph — NOT the initial `discussion_sha` capture sentence, which is not a halt site) each end with the sentence `Delete _mill/plan/ and re-run /mill-plan for a fresh plan against the current discussion.md.` followed by the rest of that paragraph. In BOTH of these two paragraphs, append this new sentence immediately after that "Delete _mill/plan/..." sentence (before whatever prose follows it in each paragraph):

  "If the drift is a pure scope narrowing (dropping something the plan hasn't started yet) rather than a new requirement, `/mill-descope-batch` may be the cheaper fix instead of discarding this plan — see `mill-descope-batch/SKILL.md`."

  Land this card after card 3 (card 3 must already have rewritten the `discussion_sha` git command in these same two paragraphs).
- **Commit:** `docs(mill-plan): point drift-guard halts at /mill-descope-batch for narrowing`

### Card 7: mill-plan Step 1.5 fix table — new `cross-batch-build-break` row

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the Step 1.5 fix table (under `### Phase: Plan Review`), insert a new row immediately after the `batch-oversized` row and before the `out-of-worktree-target` row, matching the table's existing pipe-delimited single-line-per-row format:

  ```
  | cross-batch-build-break        | The payload's `path:` field names the stale symbol; `batch:` names the batch whose card still references it; `message:` names the batch that renamed/removed it. Add the missing `depends-on` edge (both the per-batch file's frontmatter and the overview's Batch Index entry, per the existing `depends-on-batch-mismatch` discipline) if the later batch's card genuinely needs the rename to land first. If the sequencing is intentional (an accepted degrade), record it as a `### Decision:` subsection under `00-overview.md`'s `## Shared Decisions` (mirroring the plan's existing acknowledged-degrade pattern, e.g. `windows-status-line-is-an-unbranched-accepted-degrade`) stating the intermediate batches will not build, then re-run with `--skip-check cross-batch-build-break` — mirrors the `wiki-config-mutation`/`verify-full-suite` rows' skip-check escape-hatch shape. |
  ```

  This documents the `cross-batch-build-break` validator check that batch 4 (`04-cross-batch-build-break.md`) implements in `_plan_validate.py`; the check name and remedy text here must match that batch's implementation exactly (both were derived from `_mill/discussion.md`'s `1056-cross-batch-build-break-check` Decision).
- **Commit:** `docs(mill-plan): fix-table row for cross-batch-build-break check`

### Card 8: mill-start Phase: Handoff — Post-Handoff immutability of discussion.md

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### Phase: Handoff`, insert a new paragraph immediately after the sentence "Do not invoke `/mill-plan` yourself — handoff is always an explicit user decision." and immediately before the `## Principles` heading. New paragraph:

  "**Post-Handoff immutability.** Once this phase's `_status.append_phase(status_path, "discussed", timestamp)` commits, `discussion_path` must not be edited again by mill-start, in this session or a later one. `phase: discussed` is mill-plan's entry-gate signal (see mill-plan/SKILL.md's "Entry-gate wait for upstream mill-start") — a mill-start that keeps mutating discussion.md after raising it races mill-plan and makes the gate meaningless. If a genuine correction surfaces after Handoff, do not edit discussion.md directly; report the correction to the operator as a note for the next task/gap instead."
- **Commit:** `docs(mill-start): state Post-Handoff immutability of discussion.md`

## Batch Tests

`verify: null` — every card in this batch is a prose edit to a `SKILL.md` file (an orchestrator-read instruction document, not executed code); no unit test in this repo exercises `SKILL.md` content. Verified by re-reading each edited section after the card lands, confirming: the new/changed text reads correctly in context, no existing cross-reference (e.g. card 4's pointer to "## Agent-mode dispatch" step 4, card 6's pointer to `mill-descope-batch/SKILL.md`) is broken, and card 3's three-site substitution left no stray unedited occurrence of the old `git -C <git_root> rev-parse HEAD:_mill/discussion.md` form (`grep -n "rev-parse HEAD:_mill/discussion.md" plugins/mill/skills/mill-plan/SKILL.md` should return no matches once card 3 lands).
