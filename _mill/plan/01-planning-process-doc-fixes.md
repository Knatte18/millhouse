# Batch: planning-process-doc-fixes

```yaml
task: 'mill-plan: planning-process documentation/procedure gaps'
batch: planning-process-doc-fixes
number: 1
cards: 6
verify: null
depends-on: []
```

## Batch Scope

This batch fixes the four still-open documentation/procedure gaps bundled into this task (the fifth bundled item, `#988`, is already fixed — see the overview's "`#988` (done-gate re-validate) needs no card" Decision, no card here). All six cards are prose edits to `plugins/mill/skills/mill-plan/SKILL.md` and its two rendered templates; there is no external interface — this is the only batch.

## Cards

### Card 1: Resolve template paths via `${CLAUDE_PLUGIN_ROOT}`

- **Context:**
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace all three literal `plugins/mill/templates/` path references in `plugins/mill/skills/mill-plan/SKILL.md` with `${CLAUDE_PLUGIN_ROOT}/templates/`, matching this file's existing `${CLAUDE_PLUGIN_ROOT}/scripts/` convention for every script path (see the file's own "Interpreter-naming note"). Three sites: (1) Phase: Plan step 1's numbered instruction to render `plan-overview.md` into `<plan_dir>/00-overview.md`. (2) Phase: Plan step 3's numbered instruction to render `plan-batch.md` into `<plan_dir>/NN-<batch-slug>.md`. (3) Phase: Plan Review Step 1.5's fix table, `move-mechanic-missing` row, the parenthetical naming where the canonical `## Rename mechanic` section is copied from. `Context:` lists both template files only so their real on-disk location is confirmed before the path is rewritten — no read of their content is required for this card. After the edit, `grep -c "plugins/mill/templates/" plugins/mill/skills/mill-plan/SKILL.md` must return `0`.
- **Commit:** `docs(mill-plan): resolve template paths via CLAUDE_PLUGIN_ROOT`

### Card 2: Point plan-batch.md's PYTHONPATH rule at SKILL.md's language carve-out

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately after the sentence "The validator check verify-not-isolated enforces this." (in the HTML-comment authoring-guidance block's `verify:` paragraph beginning "Non-null verify: commands MUST start with..."), add one new sentence: "This rule is Python/mill-project-specific -- for a non-Python project (e.g. Go, C#), see `mill-plan/SKILL.md`'s \"Verify command shape\" section for the native-test-runner alternative." Do not duplicate the full Python/non-Python conditional text from `SKILL.md` -- this sentence only points at that section.
- **Commit:** `docs(mill-plan): point plan-batch.md's PYTHONPATH rule at SKILL.md carve-out`

### Card 3: Point plan-overview.md's PYTHONPATH rule at SKILL.md's language carve-out

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/plan-overview.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately after the sentence "When set, it follows the same `PYTHONPATH= ` shape rule as per-batch `verify:` commands and should be a cheap whole-module compile/vet/smoke command (e.g. `PYTHONPATH= go vet ./...` or a scoped `run-all.py`) that catches cross-package regressions from shared-helper edits at the introducing batch." (in the HTML-comment authoring-guidance block's `verify:` paragraph), add one new sentence, using an em-dash ("—") to match this file's existing dash convention (not ASCII " -- "): "This rule is Python/mill-project-specific — see `mill-plan/SKILL.md`'s \"Verify command shape\" section for the non-Python-project carve-out." Do not duplicate the full Python/non-Python conditional text from `SKILL.md` — this sentence only points at that section.
- **Commit:** `docs(mill-plan): point plan-overview.md's PYTHONPATH rule at SKILL.md carve-out`

### Card 4: Add clean-tree-gate untracked-brief carve-out to Principles

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add one new bullet to the `## Principles` section, inserted immediately after the existing "Phrase Requirements: prohibitions on one line; avoid double negatives" bullet-block and before the `## Board discipline` heading:

  ```
  - **A hard clean-tree gate must exempt the current batch's own untracked brief** — a card that authors a `git status --porcelain`-must-be-empty gate must exclude `_mill/briefs/<currently-executing-batch>*.md` from it. That file is written by the orchestrator's `--stage prepare` before the implementer session starts and is committed only by the batch's own end-of-batch commit, so it is unavoidably untracked at any clean-tree checkpoint earlier in the same batch, in every plan run under mill-go — not just matrix/benchmark-style batches.
  ```
- **Commit:** `docs(mill-plan): add clean-tree-gate untracked-brief carve-out to Principles`

### Card 5: Thread blocked-reentry --max-rounds into Agent-mode dispatch

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Phase: Plan Review, add a new blockquote reminder to each of the two Agent-mode dispatch sites that currently lack it, mirroring the subprocess/psmux branch's existing blockquote at both its equivalent sites — adapt the wording to Agent-mode's own `<args>` phrasing (matching the sibling live-operator-override blockquote already present at both sites), not the subprocess/psmux-specific "inner invocation below" phrasing.

  Site 1 — Step 2's initial Agent-mode dispatch: immediately before the existing blockquote beginning "> When a live operator-raised round-cap override is active..., append \` --max-rounds <operator_max_review_rounds>\` to \`<args>\` for this and every remaining round.", insert this new blockquote line:
  ```
  > Only when this loop was entered via the Entry `blocked` re-entry row (see "Entry: resuming after a max-rounds block"), append ` --max-rounds <local_max_review_rounds>` to `<args>` for this and every remaining round; omit it on every other round.
  ```

  Site 2 — Step 3.5's Agent-mode ERROR-retry: immediately before the existing blockquote beginning "> When a live operator-raised round-cap override is active..., append \` --max-rounds <operator_max_review_rounds>\` to \`<args>\` for this retry too...", insert this new blockquote line:
  ```
  > Only when this loop was entered via the Entry `blocked` re-entry row (see "Entry: resuming after a max-rounds block"), append ` --max-rounds <local_max_review_rounds>` to `<args>` for this retry too; omit it on every other round.
  ```

  Do not touch the "`--max-rounds` threading for blocked-resume (`revise_from_blocked` only)" paragraph or the subprocess/psmux branch's existing blockquotes at its own Step 2/Step 3.5 sites — those are card 6's scope and are already correct, respectively.
- **Commit:** `docs(mill-plan): thread blocked-reentry --max-rounds into Agent-mode dispatch`

### Card 6: Fix revise_from_blocked --max-rounds threading; document known overlap limitation

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rewrite the "**`--max-rounds` threading for blocked-resume (`revise_from_blocked` only)**" paragraph (Phase: Plan Review, Path Setup section) to fix the one-round-only bug: replace its condition-and-scope sentence — currently "When `revise_from_blocked` is set **and** the current loop's `round == blocked_resume_round`: every prepare/finalize CLI invocation dispatched in step 2's dispatch below for that one round only ... must additionally pass `--max-rounds <blocked_resume_round>`" — and its following "Omit `--max-rounds` on every other round, including subsequent rounds within the same blocked-resume `--revise` invocation once `round` has advanced past `blocked_resume_round`." sentence, so that: when `revise_from_blocked` is set, every prepare/finalize CLI invocation dispatched **anywhere in this phase — both step 2's dispatch below and step 3.5's ERROR-only-aggregate retry dispatch (which re-fires the identical round `N` without consuming the round counter)** — for every round of this resumed loop (not just the round equal to `blocked_resume_round`), must additionally pass `--max-rounds <round>` (the current round number being dispatched) — both the Agent-mode branch's `<args>` and the subprocess/psmux branch's `millpy-review-plan.py` invocation via `millpy-bg`, at every one of those dispatch sites. Keep the paragraph's existing closing rationale sentence about the CLI's own `round_n > max_rounds` guard (it is never itself a signal to run more rounds than the loop's existing convergence/step-6 logic would otherwise allow), and add one sentence noting `revise_from_blocked` has no precomputed extended-budget variable (unlike the Entry-blocked-reentry flow's `local_max_review_rounds`) — passing the always-current round number satisfies the CLI's guard on every round, at every dispatch site, with no new state needed. This closes the same gap card 5 closes for the Entry-blocked-reentry flow's Agent-mode sites — `revise_from_blocked`'s existing text already named only "step 2's dispatch below", silently excluding Step 3.5's retry from the very start, not only after the one-round-only fix.

  Then add a new paragraph immediately after it, headed "**Known limitation.**": `revise_from_blocked`'s `--revise` pre-check (Entry step 4) fires on `phase == "blocked"` for any `blocked_reason`, including `"max-rounds exhausted"`, and takes precedence over the Entry-blocked-reentry table row whenever `--revise` is set; in that overlap case the orchestrator-level `round >= max_review_rounds` comparisons (Convergence gate, 4a/4b/4c implicit-approve-at-cap, step 6) are unaffected by this paragraph's per-round `--max-rounds` fix and still use the bare config `max_review_rounds`, since the "Resumed-loop round-cap substitution" paragraph's `local_max_review_rounds` substitution applies only to the Entry-blocked-reentry flow; a `--revise` resume of a plan blocked specifically for `"max-rounds exhausted"` may therefore have its very first resumed round immediately satisfy the implicit-approve-at-cap/max-rounds-escape branch without a real review round running; this is accepted as a known, out-of-scope limitation — extending `blocked_resume_round`'s handling to also carry an orchestrator-level extended budget is a separate fix.

  Do not change `blocked_resume_round`'s computation (`blocked_resume_round = _review_common.discover_round(reviews_dir, "plan", "holistic")`) or any other paragraph in this phase.
- **Commit:** `docs(mill-plan): fix revise_from_blocked --max-rounds threading; document overlap limitation`

## Batch Tests

This batch is a pure documentation/procedure fix — no runnable test surface (`verify: null` at both batch and overview level; none of `plugins/mill/unit_tests/` covers skill-file/template prose content). Verification is per-card:

- Card 1: `grep -c "plugins/mill/templates/" plugins/mill/skills/mill-plan/SKILL.md` returns `0`.
- Cards 2/3: both templates' `PYTHONPATH= ` paragraphs each gain one new sentence pointing at `mill-plan/SKILL.md`'s "Verify command shape" section; `SKILL.md`'s own conditional text is unchanged by this batch.
- Card 4: the new `## Principles` bullet exists and names `_mill/briefs/<currently-executing-batch>*.md` explicitly.
- Card 5: `grep -c "local_max_review_rounds" plugins/mill/skills/mill-plan/SKILL.md` increases by 2 versus the pre-batch count, and both new blockquotes use `<args>` phrasing, never "inner invocation below".
- Card 6: the rewritten paragraph contains no remaining instance of "for that one round only" or "Omit `--max-rounds` on every other round" tied to `revise_from_blocked`, names both step 2's dispatch AND step 3.5's retry dispatch, and both the Agent-mode and subprocess/psmux threading instructions at both sites read `--max-rounds <round>`.
