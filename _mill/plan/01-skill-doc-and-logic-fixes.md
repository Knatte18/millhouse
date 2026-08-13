# Batch: skill-doc-and-logic-fixes

```yaml
task: 'mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps'
batch: skill-doc-and-logic-fixes
number: 1
cards: 8
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
depends-on: []
```

## Batch Scope

This batch fixes all seven GitHub issues named in `_mill/discussion.md` (#839, #832, #831, #827, #826, #821, #815) by editing `plugins/mill/skills/mill-plan/SKILL.md`'s prose/logic, plus one docstring-only line in `plugins/mill/scripts/_paths.py`. No shared script's behavior, signature, or call contract changes — every helper referenced by the new/edited prose already exists and already does the right thing today. There is no external interface for a downstream batch to consume; this is the only batch. Cards are ordered by first-touched position in `SKILL.md` (Entry section, then Phase: Plan, then Phase: Plan Review, then `## Principles`), except card 2 (the `_paths.py` docstring), which is sequenced right after card 1 since both resolve the same pair of issues (#839/#826).

## Cards

### Card 1: Entry: bind `worktree_root` before its first use; fix its stray "hub root" label (#839, #826)

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/git-commit/SKILL.md`
  - `plugins/mill/skills/mill-quick/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `## Entry` section's numbered list (Entry step 1, "1. Resolve and bind the path variables:"), the two existing bullets are:
  ```
   - `git_root = _paths.resolve_git_root()`
   - `wiki_path = _paths.resolve_wiki_path(git_root)`
   `signature: _paths.resolve_git_root(start: Path | None = None) -> Path`
   `signature: _paths.resolve_wiki_path(git_toplevel: Path) -> Path`
  ```
  Add one new bullet immediately after the `wiki_path` bullet and before the `signature:` lines:
  - `` `worktree_root = _paths.resolve_hub_path()` `` (the task worktree root; used to anchor `_mill/` paths in nested layouts)

  Do not add a `signature:` line for `resolve_hub_path` here — the file does not document signatures for helpers it already calls elsewhere without one (`resolve_hub_path` is already called in `## Phases`), and no new helper is being introduced by this card.

  In Entry step 2 ("2. Load config — deep-merge..."), the paragraph currently ends with the `` `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict` `` sentence. Insert a new sentence immediately before that signature sentence: "Call `cfg = _config.load_config(worktree_root, git_root)`." — matching the established call-site convention used by every other skill that calls this helper (`mill-go-base/SKILL.md`: `hub_root = _paths.resolve_hub_path(); cfg = _config.load_config(hub_root, git_root)`; `git-commit/SKILL.md`: identical shape; `mill-quick/SKILL.md`: `worktree_root = _paths.resolve_hub_path(); cfg = _config.load_config(worktree_root, git_root)` — the same local variable name this card uses). `_config.load_config`'s own first parameter is named `hub_root` in its signature but means "the directory where `mill-config.yaml` lives," i.e. `resolve_hub_path()`'s result — which this file's own Entry step 2 prose already calls "the hub root" ("deep-merge `<hub_root>/mill-config.yaml`"). Do not introduce a second, separately-bound `hub_root` variable to mirror `_config.load_config`'s parameter name; feeding `resolve_hub_path()`'s result as the first positional argument (regardless of its local variable name in this file) and `git_root` as the second is what makes the call correct — this makes explicit that step 2's `load_config` call now has its `worktree_root` argument already bound by step 1 above, closing the "referenced before bound" gap.

  In the **Path Setup.** section, the current bullet list is:
  ```
Derive:
- `git_root = _paths.resolve_git_root()`
- `worktree_root = _paths.resolve_hub_path()` (the hub root;
  used to anchor `_mill/` paths in nested layouts)
- `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` (resolves against the hub root)
  ```
  Remove the `worktree_root` bullet entirely (it is now bound at Entry step 1, not re-derived here). Keep the `git_root` bullet unchanged. Change the `status_path` bullet's trailing parenthetical from `(resolves against the hub root)` to `(resolves against the task worktree root; `worktree_root` is already bound at Entry step 1 above)` — dropping the stray "hub root" label on `worktree_root`'s result directly resolves the naming confusion GitHub issue #839 warns about ("note the naming collision that makes this easy to get wrong: `resolve_hub_path()` returns the worktree, not the hub"): the file's prose should call this variable what it is (the task worktree root), not "the hub root," even though `_config.load_config`'s own parameter name for the conceptually equivalent argument happens to be `hub_root`.

  Do not change any other Entry-section or Path Setup text in this card (the sentence beginning "`plan_dir` and `reviews_dir` will be derived..." stays as-is).
- **Commit:** `docs(mill-plan): bind worktree_root before its first use; fix load_config argument order`

### Card 2: `_paths.py`: correct `resolve_hub_path`'s "main worktree" docstring mislabel (#839, #826)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `resolve_hub_path`'s docstring first line currently reads:
  ```
    """Return the hub directory (the main worktree, where mill-config.yaml lives).
  ```
  Change it to:
  ```
      """Return the hub directory (the task worktree root where mill-config.yaml lives,
      not the git checkout's main worktree — see resolve_main_worktree_root for that).
  ```
  This is a docstring wording correction only — do not change the function signature, its resolution logic, its return value, or any other line of its docstring body. `resolve_hub_path` genuinely returns the task worktree root (confirmed empirically per `_mill/discussion.md`'s Technical Context: "in a flat (non-nested) layout this is the current task worktree, not the main worktree"), so the prior wording mislabeled its own result — the same mislabel Card 1 corrects inside `mill-plan/SKILL.md`'s own comment.
- **Commit:** `docs(_paths): correct resolve_hub_path docstring's "main worktree" mislabel`

### Card 3: Widen the entry-gate wait trigger to cover `discussion-fix-r{N}` (#821)

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the Entry step 4 phase table, the `phase: discussing` row's left cell currently reads exactly `` `phase: discussing` `` (bare phase value only). Widen it to also cover `discussion-fix-r{N}` by changing the cell to `` `phase: discussing`, or matching `^discussion-fix-r\d+$` `` — mirroring `mill-go-base/SKILL.md`'s own widened row's exact cell-text pattern (`` `discussed` / `discussing` / `planning`, or matching `^plan-review-r\d+$` / `^plan-fix-r\d+$` ``). This is required, not cosmetic: the `### Entry-gate wait for upstream mill-start` subsection this card also edits (below) only ever runs "Whenever the phase-table lookup above lands on the `phase: discussing` row" — without widening the table row itself, a `discussion-fix-r{N}` phase value falls through to the catch-all "any other phase" row and halts before `matches_wait_trigger`'s widened regex is ever evaluated, making the rest of this card's fix dead code. Leave the row's right cell (the action column) unchanged.

  In the `### Entry-gate wait for upstream mill-start` subsection's first bullet, change the fenced python block from:
  ```python
  matched = _phase_wait.matches_wait_trigger(phase, {"discussing"}, [])
  ```
  to:
  ```python
  matched = _phase_wait.matches_wait_trigger(phase, {"discussing"}, [r"^discussion-fix-r\d+$"])
  ```
  Then replace the four sentences that follow the code block (starting "No regex widening on this side." and ending "...as separate, independently observable commits.") with corrected justification prose that:
  1. States the trigger is now widened to also match `discussion-fix-r{N}`.
  2. Explains why: GitHub issue #821 has a concrete repro (commit `ab1786d6`) showing mill-start's own convergence-gate not-converged branch (Phase: Discussion Review step 4b, per `mill-start/SKILL.md`) appends+commits+pushes `discussion-fix-r{N}` and continues to the next round *without* the `discussed` phase following in the same commit — so `discussion-fix-r{N}` genuinely is pushed as a standalone, externally observable phase.
  3. Notes this mirrors mill-go's own copy of this exact wait pattern for mill-plan's own phases (`mill-go-base/SKILL.md`: `{"discussed", "discussing", "planning"}, [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"]`) — same mechanism, same file family.

  Do not carry forward the disproven claim that `discussion-fix-r{N}` "is never itself pushed as a standalone, externally observable phase" anywhere in the rewritten prose. Do not touch the `- Read entry_wait = ...` bullet or anything below it in this subsection — only the match-computation bullet and its justification prose change.
- **Commit:** `fix(mill-plan): widen entry-gate wait trigger to cover discussion-fix-r{N} (#821)`

### Card 4: Add Entry `blocked` re-entry row for max-rounds resumption (#832, part 1 of 2)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the Entry step 4 phase table, the current rows (in order) are `phase: discussed` (no plan_dir), `phase: planning`/`plan-review-*`/`plan-fix-*`, `approved: true`, `phase: discussing`, and the catch-all `any other phase (planned, …)` row. Insert one new row immediately before the catch-all row (i.e. after the `phase: discussing` row):
  ```
  | `phase: blocked` | see "Entry: resuming after a max-rounds block" below |
  ```

  Add a new subsection titled `### Entry: resuming after a max-rounds block`, placed immediately after the existing `### Entry-gate wait for upstream mill-start` subsection and before the `## Phases` heading. Its full body:

  ```
  Whenever the phase-table lookup above lands on the `phase: blocked` row, run this procedure instead of jumping straight to its listed action:

  - Read `blocked_reason = _status.read_full(status_path)["yaml"].get("blocked_reason")`.
  - **If `blocked_reason` does not start with `"max-rounds exhausted"`:** this is a hard stop exactly as today — surface `blocked_reason` to the operator and halt.
    Manual `status.md` intervention is required (matches this file's own "## Board discipline" ban on hand-editing the status.md yaml block — the operator investigates and clears `blocked_reason` themselves, mill-plan does not).
  - **If `blocked_reason` starts with `"max-rounds exhausted"`:** this is a resource-exhaustion block, safe to resume automatically now that the operator has explicitly re-invoked `/mill-plan`.
    - Derive `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])` (the same expression Phase: Plan Review's own "**Path Setup (Plan Review).**" section uses — `worktree_root` and `cfg` are already bound by this point in Entry step 4).
    - **`--revise` mid-block detection (check before deriving `N`):** list any `reviews_dir/revise-*` subdirectories.
      If the most-recently-modified review file across all of them is newer than the most-recently-modified review file directly in the plain `reviews_dir` (or the plain directory has no review files at all), the block occurred mid-`--revise`.
      Halt: state the block occurred during a `--revise` session and that resuming it is unsupported (the ordinary `--revise` pre-check cannot be re-supplied to recover the namespace, since it requires `phase == "planned"`, which is false once `phase: blocked`).
      Do not derive `N` or proceed below when this fires.
    - Otherwise, derive `N = _review_common.discover_round(reviews_dir, "plan", "holistic")` (the file's own established round-discovery helper — scans `reviews_dir` for existing review files and returns `max(found) + 1`, or `1` if none exist).
    - Compute `local_max_review_rounds = N + max_review_rounds - 1` (a fresh, full `max_review_rounds`-sized budget starting at round `N`).
      Because `set_blocked`'s `"max-rounds exhausted"` reason is only ever written when `round == max_review_rounds`, `N` will typically equal `max_review_rounds + 1` — without this extension, every one of Phase: Plan Review's existing `round >= max_review_rounds` checks would already be satisfied on the very first resumed iteration, immediately re-triggering an implicit-approve-at-cap or a fresh max-rounds halt without ever running a real review round.
      `local_max_review_rounds` substitutes for `max_review_rounds` at every site named in Phase: Plan Review's "Resumed-loop round-cap substitution" paragraph, for the remainder of this resumed loop only — the config-derived `max_review_rounds` value itself is never mutated, and a subsequent fresh `/mill-plan` invocation (no `blocked` re-entry involved) uses the unmodified config value as always.
    - Call `_status.append_phase(status_path, "planning", <timestamp>)` — **not** `f"plan-review-r{N}"`, since round `N` has not run yet; `_status.append_phase` never dedupes against an existing identical Timeline row, so pre-writing round N's own completion marker before round N has even run would leave two identical `plan-review-r{N}` entries with different timestamps once the round actually completes and 4a/4d append it again for real.
      `"planning"` is already one of the phase values the Entry step-4 table's ordinary re-entry row matches, so it correctly signals "resume the review loop" without claiming a round completed.
      This call also auto-clears `blocked_reason` per `_status.append_phase`'s existing transition-away-from-blocked behavior — no separate clearing step is needed.
    - Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: resume plan review after max-rounds block for {slug}"`. Push.
    - Fall through into Phase: Plan Review, entering the loop at round `N` with `local_max_review_rounds` in effect.
  ```

  (The literal timestamp/backtick formatting above should match the existing file's established conventions for such sentences — e.g. `_timestamp.now_utc_iso()` where the file already uses that pattern for `iso_ts`/`<timestamp>` placeholders elsewhere in Phase: Plan Review.)
- **Commit:** `feat(mill-plan): add blocked re-entry row for max-rounds resumption (#832)`

### Card 5: Thread `local_max_review_rounds` through the resumed Plan Review loop; reword step 6's halt message (#832, part 2 of 2)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### Phase: Plan Review`, immediately after the sentence "Loop up to `max_review_rounds` rounds." and before "Each round:", insert a new paragraph:
  ```
  **Resumed-loop round-cap substitution.** When this loop was entered via the Entry `blocked` re-entry row (see "Entry: resuming after a max-rounds block"), `local_max_review_rounds` substitutes for `max_review_rounds` at every site in this phase that compares against it, for the remainder of that resumed loop only: the loop-length cap just stated above, the step 1 round-report line ("Plan Review — round N/max_review_rounds" prints as "round N/local_max_review_rounds" instead), the Convergence gate's two `round >= max_review_rounds` / `round < max_review_rounds` bullets, every 4a/4b/4c inline `round >= max_review_rounds` (implicit-approve-at-cap) / `round < max_review_rounds` restatement, and step 6's `{N} rounds` in its halt message. The config-derived `max_review_rounds` value itself is never mutated by this substitution — a subsequent fresh `/mill-plan` invocation (no `blocked` re-entry involved) uses the unmodified config value everywhere, as always.
  ```

  **Subprocess/psmux CLI-flag threading.** (Agent-mode is unaffected: `_review_plan.py`'s `prepare()`/`finalize()` — the functions Agent-mode's `--stage prepare`/`--stage finalize` calls — accept no `max_rounds` parameter and perform no round-cap check of their own; `millpy-review-plan.py` never reads `args.max_rounds` outside the `--stage full` path, so passing `--max-rounds` on an Agent-mode dispatch would be inert. This card's substitution rule therefore never touches the Agent-mode dispatch sentences edited by Card 7.) Under the Subprocess/psmux branch, `millpy-review-plan.py` defaults to `--stage full`, which calls `_review_plan.run()` — the one function in this CLI that actually enforces a round cap (`if round_n > holistic_max_rounds: raise ReviewError(...)`), where `holistic_max_rounds` is the CLI's own `--max-rounds` flag when passed, else the config value. Without threading `local_max_review_rounds` into that flag, the very first resumed round (`round_n == N == max_review_rounds + 1` in the typical case) raises `ReviewError` before any LLM call — the SKILL.md-prose substitution above does not, by itself, reach the actual subprocess invocation. Immediately before both existing Subprocess/psmux bash blocks in this phase — the step 2 dispatch (`--slug plan-review-r<N>`) and the Step 4.5 ERROR-retry re-dispatch (`--slug plan-review-retry-r<N>`) — insert a blockquote note of the same shape `mill-start/SKILL.md` already uses for its own analogous extension-round flag (e.g. `mill-start/SKILL.md`'s "Only when this round is the Auto mode non-progress-extension round... append ` --max-rounds <max_review_rounds + 1>` to the inner `millpy-review-discussion.py` invocation below; omit it on every other round."):
  ```
  > Only when this loop was entered via the Entry `blocked` re-entry row (see "Entry: resuming after a max-rounds block"), append ` --max-rounds <local_max_review_rounds>` to the inner `millpy-review-plan.py` invocation below; omit it on every other round.
  ```
  Place each note immediately before its bash block, after the existing `> **Before invoking millpy-bg**:` note that already precedes each of those two blocks (so the new note is the second blockquote, directly above the code fence).

  Separately, in step 6 ("**Max-rounds escape**..."), the current halt text is:
  ```
   halt with "Plan blocked after {N} rounds, {M} BLOCKINGs remain.
   Task left as [active] for manual review." `{M}` is `result["blocking_count"]` from the most recent CLI invocation — do not re-count manually.
  ```
  Change the quoted halt message's second clause from `{M} BLOCKINGs remain.` to `the last round's {M} BLOCKING finding(s) were acted on (fixed or pushed back) but not yet re-reviewed.` (so the full quoted string reads `"Plan blocked after {N} rounds, the last round's {M} BLOCKING finding(s) were acted on (fixed or pushed back) but not yet re-reviewed. Task left as [active] for manual review."` — "acted on (fixed or pushed back)", not "addressed", since step 4d's fixer pass may legitimately push back some findings per `mill-receiving-review`'s decision tree rather than fixing every one, and "addressed" would overclaim that all were fixed). Immediately after the existing "`{M}` is `result["blocking_count"]`... do not re-count manually." sentence, add: "Step 4d's fixer pass already ran on those exact findings before this round-cap check fires, so \"BLOCKINGs remain\" would be misleading at the moment this halt prints — this operator-facing halt text is reworded accordingly; `_status.set_blocked`'s own `blocked_reason` argument keeps its existing, unreworded text (a machine field consumed only by the Entry `blocked` re-entry row's `.startswith(\"max-rounds exhausted\")` prefix check, never read verbatim by a human at that point)." Do not change `_status.set_blocked`'s call itself (the `f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain"` string passed as `reason`) — only the human-facing quoted halt message changes.

  Do not add per-site parentheticals inline at the loop header, step 1's report line, the Convergence gate's two bullets, or 4a/4b/4c's own inline restatements — the single paragraph above is the sole substitution rule for all of them, per this card's Requirements.
- **Commit:** `docs(mill-plan): thread local_max_review_rounds through resumed Plan Review loop; reword max-rounds halt (#832)`

### Card 6: Step 1.5 fix table: add four missing rows; formalize `verify-full-suite` skip-check escape hatch (#827)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### Phase: Plan`'s "**Self-run the validator gate**" subsection, the current text (in order) is: the `` **`wiki-config-mutation` skip-check override.** `` paragraph, then the fenced python block containing `errors = _plan_validate.run(...)`. That paragraph's second sentence currently reads "If either condition holds, set `skip_checks = frozenset({"wiki-config-mutation"})`..." — change `skip_checks = frozenset({"wiki-config-mutation"})` to `skip_checks = skip_checks | frozenset({"wiki-config-mutation"})` (union instead of replace), so this override no longer silently clobbers a `skip_checks` value another paragraph in this same section may have already set.

  Insert a new paragraph immediately after the (now-updated) `` **`wiki-config-mutation` skip-check override.** `` paragraph and before the `errors = _plan_validate.run(...)` python block:
  ```
  **`verify-full-suite` skip-check escape hatch.** Keep the "Verify command scope" section's carve-out (a batch that legitimately touches a cross-cutting helper every test imports MAY use the unbounded `run-all.py`) — but only when the batch's own `## Batch Tests` section documents that justification. If it does, set `skip_checks = skip_checks | frozenset({"verify-full-suite"})` and record the justification in the plan commit message (see "Commit on the task branch" below). If the justification is absent or unconvincing, leave `skip_checks` unchanged for this check — let it fire and halt per the `verify-full-suite` fix-table row (Phase: Plan Review Step 1.5) instead.
  ```

  In `### Phase: Plan Review`'s Step 1.5 fix table, add four new rows (matching the existing table's exact column format: `| check | mechanical fix |`):
  - Immediately after the `depends-on-unknown` row:
    ```
    | depends-on-batch-mismatch      | The payload's `batch:` field names the batch whose per-batch file frontmatter `depends-on:` disagrees with the overview's Batch Index entry for that same batch (payload's `message:` field shows both sides). Edit whichever side is stale so the per-batch file's `depends-on:` and the overview Batch Index entry's `depends-on:` name the identical dependency set. |
    ```
  - Immediately after the `verify-excludes-edited-tagged-test` row and before the `wiki-config-mutation` row, add three rows in this order:
    ```
    | verify-malformed-cwd           | Open the offending `verify:` field named by the error payload's `path:` field (a batch file path or the overview path) and `batch:` field (batch stem, or `None` for the overview). Fix the malformed `{cwd, command}` mapping per the payload's `message:` field (e.g. a bad `cwd` value that isn't `hub`/`git_root`, or a mapping missing `command:`). |
    | verify-mixed-cwd               | Each error dict's `message:` field states only that batch's own resolved cwd plus the sorted list of conflicting batch names; read all `verify-mixed-cwd` error dicts emitted for this plan together to see every batch's individual cwd. Change the outlier batch(es)' `verify:` mapping's `cwd:` value (or convert to the plain-string form, which implies `cwd: git_root`) so every batch in the plan resolves the `{cwd, command}` mapping form to the same root — all `hub` or all `git_root`. |
    | verify-full-suite              | The payload's `path:` field carries the offending `verify:` command (`batch:` names the offending batch, or `None` for the overview's module-wide `verify:`). If the batch's own `## Batch Tests` section already documents the cross-cutting-helper justification (see the `verify-full-suite` skip-check escape hatch in Phase: Plan), re-run with `--skip-check verify-full-suite`. Otherwise scope the command via `-k <pattern>` or `--only <every affected test file>`. |
    ```
  Match the existing table's column padding style loosely (exact alignment is cosmetic, not load-bearing) but keep every row a single `|`-delimited line, consistent with every other row already in the table.
- **Commit:** `docs(mill-plan): add missing Step 1.5 fix-table rows and formalize verify-full-suite escape hatch (#827)`

### Card 7: Document `--agent-output` for both finalize invocations (#831)

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add the following sentence, verbatim, at two locations in `### Phase: Plan Review`:
  ```
  Thread `--round <round>` from the prepare envelope into the finalize invocation unchanged (finalize has no round-cap check and never needs `--max-rounds`), and also pass `--agent-output <output_path>`, where `<output_path>` is the prepare envelope's `output_path` field read verbatim (extracted at the general Agent-mode dispatch pattern's step 1 in `mill-go-base/SKILL.md`, used verbatim at its step 5) — `millpy-review-plan.py --stage finalize` exits 1 with `"ERROR: --agent-output required for finalize stage"` when this flag is omitted.
  ```
  This documents the same requirement `mill-start/SKILL.md`'s existing sentence documents at its own two Agent-mode finalize call sites (for `millpy-review-discussion.py`), adapted for `millpy-review-plan.py` — with one deliberate improvement over copying it verbatim: `mill-start/SKILL.md`'s own sentence cites "step 2" of the general Agent-mode dispatch pattern for where `output_path` comes from, but in `mill-go-base/SKILL.md` `output_path` is extracted at step 1 ("Run prepare stage") and used at step 5 ("Run finalize stage"), never mentioned at step 2 ("Call Agent tool") — so this card's sentence cites the pattern's actual step numbers instead of reproducing that pre-existing inaccuracy. Do not edit `mill-start/SKILL.md` itself in this card; its own citation is out of this plan's scope.

  Location 1: step 2's Agent-mode dispatch paragraph — immediately after the sentence "If `agent` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `mill-go-base/SKILL.md`) with `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`."

  Location 2: Step 4.5's ERROR-retry re-dispatch — immediately after the sentence "**Agent-mode:** follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `mill-go-base/SKILL.md`) with `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`."

  Do not add this sentence anywhere else (e.g. not at Step 1.5's validator-fix re-run, which is a `--stage prepare` re-invocation with no finalize step).
- **Commit:** `docs(mill-plan): document --agent-output requirement for finalize invocations (#831)`

### Card 8: New Principle: existing-test-impact check for contract changes (#815)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `## Principles`, insert a new bullet immediately after the "**`Requirements:` must use stable identifiers**" bullet (which ends "...the rule is 'no *extra* indentation beyond the source's own,' not 'no indentation at all'.") and before the "**Express renames as `Moves:` pairs**" bullet:
  ```
  - **Existing-test-impact check for contract changes** — when a card's `Requirements:` states that it changes an exported function's, method's, or class's existing behavior/contract (not just adding new code), grep the codebase for existing callers and tests of that symbol before finalizing the plan, and add any found to that card's `Context:` (read-only) or `Edits:` (if the test itself needs updating to match the new contract). "Intentionally changes an exported symbol's contract" is a judgment call about the card's own stated design intent — only the planning agent, already reading the full `Requirements:` prose, can reliably make it; a mechanical validator check can't distinguish an intentional contract change from an incidental edit to the same function.
  ```
- **Commit:** `docs(mill-plan): add existing-test-impact authoring principle for contract changes (#815)`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-skill-helper-drift.py`, which scans every `SKILL.md` file (including `mill-plan/SKILL.md`, edited by cards 1, 3, 4, 5, 6, 7, and 8) for `_<module>.<fn>(`-shaped prose references and asserts each resolves to a real, currently-shipped function signature. This batch's edits add one such reference that doesn't already appear in the file (`_review_common.discover_round(`, card 4) plus reuse existing ones (`_status.append_phase(` at a new call site, `_phase_wait.matches_wait_trigger(`, `_status.read_full(`, `_status.set_blocked(`) — the drift test catches a typo'd or renamed helper reference, or a reference to a module/function that no longer exists. It does not check argument count or order, so `_config.load_config(worktree_root, git_root)`'s exact 2-argument order (card 1) was verified manually against `_config.py`'s actual signature and every existing call site's established convention (`mill-go-base`, `git-commit`, `mill-quick`) during planning, not by this test. Card 2 (`_paths.py` docstring) has no runnable surface of its own — no signature or behavior changes — so it rides along on the same single-file verify command rather than needing a second one.
