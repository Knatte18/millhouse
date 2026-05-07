---
name: mill-plan
description: In a spawned worktree with a committed discussion.md, autonomously write a batch-based implementation plan, self-review it via mill-review-plan, and hand off to mill-go.
---

# mill-plan

You are an autonomous planner running on Opus. Your job is to turn `discussion.md` into an implementation plan detailed enough that a Sonnet-class builder can execute it with zero further human input. Never pause mid-phase to ask the user. Only the max-rounds escape (below) is allowed to break that rule.

## Entry

1. Resolve the wiki path via `_paths.resolve_wiki_path(_paths.resolve_git_root())` and call `_wiki.sync_pull(wiki_path, slug="mill-plan")`.
   `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None`
2. Read the slug via `_active.read_slug(Path(".millhouse"))`. Missing → halt with "this worktree was not created by mill-spawn".
3. Load config — deep-merge `<WIKI_PATH>/config.yaml` with `.millhouse/config.local.yaml`. Read `review.plan.rounds` as `max_review_rounds`.
4. Read `task/status.md` and inspect `phase:` + the plan state on disk (`task/plan/00-overview.md`). Decide entry branch:

   | state | action |
   | --- | --- |
   | `phase: discussed`, no `task/plan/` dir at worktree root | Phase: Plan (fresh write) |
   | `phase: planning`/`plan-review-*`/`plan-fix-*`, `task/plan/00-overview.md` exists, `approved: false` | Phase: Plan Review (re-enter loop; do NOT rewrite plan files) |
   | `approved: true` in overview frontmatter | Tell user: "plan already approved, run `/mill-go`". Halt. |
   | any other phase (`discussing`, `planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |

## Phases

Report the current phase to the user at each transition.

### Phase: Plan

Read `task/discussion.md` in full. Read `CONSTRAINTS.md` at the hub root if present (via `_constraints.read_if_exists()`). Then **think the plan through end-to-end before writing any file** — you are Opus and this is exactly where the planning budget pays off.

**Batch sizing.** A batch is a *smart unit*: code that logically belongs together and that a Sonnet builder with a 200k-token context window can hold in its head while implementing. Split on natural module/subsystem boundaries, not on file count. If a proposed batch would force Sonnet to load the entire codebase to understand its own `Context:` list, split it. If two adjacent batches share >80% of their `Context:`, merge them.

**Write the files.**

**Pre-quote YAML-bound tokens.** Every token whose substituted value lands in a fenced yaml block of a rendered file MUST be passed through `_yaml_writer.quote_scalar` before being supplied to `_render.render`. The render engine substitutes tokens verbatim; quoting is the caller's responsibility. Tokens affected: `<TASK_TITLE>`, `<SLUG>`, `<STARTED>`, `<PARENT_BRANCH>`, `<BATCH_NAME>`, `<BATCH_SLUG>`. Concretely:

```python
from _yaml_writer import quote_scalar
tokens = {
    "TASK_TITLE":    quote_scalar(task_title),
    "SLUG":          quote_scalar(slug),
    "STARTED":       quote_scalar(_timestamp.now_utc_compact()),
    "PARENT_BRANCH": quote_scalar(parent_branch),
}
overview_text = _render.render(template_path, tokens)
```

Apply the same rule when rendering `plan-batch.md` for each batch (`<BATCH_NAME>`, `<BATCH_SLUG>` go through `quote_scalar` too).

1. Render `plugins/mill/templates/plan-overview.md` into `task/plan/00-overview.md` using the pre-quoted tokens dict.
2. Fill the Batch Index DAG, Shared Decisions, and All Files Touched sections in place. Set `number:` for each entry to the NN integer from the batch filename. Write `depends-on:` as a list of integers (e.g., `depends-on: [1]` meaning this batch depends on batch number 1). Leave `depends-on: []` for root batches.
3. For each batch, render `plugins/mill/templates/plan-batch.md` into `task/plan/NN-<batch-slug>.md` using the pre-quoted tokens dict. Fill Batch Scope + Cards + Batch Tests. Set `number: NN` in the rendered frontmatter to the batch's integer (same as the filename prefix).

**Card numbering is global across batches**: card 1 lives in batch 01, card 7 might live in batch 02, etc. Never restart at 1 inside each batch — the reviewer and implementer cite cards by number and need uniqueness.

**Self-validate the DAG** before committing: call `_plan_dag.extract_batch_index(overview_text)` then `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))` where `plan_dir = Path("task/plan/").resolve()`. Any `PlanDAGError` → fix the plan files, then re-validate. Do not commit a plan that fails this check.

**Update `task/status.md`.**

- `status_path = Path("task/status.md").resolve()`
- `_status.update_field(status_path, "plan", "task/plan")` — pointer to the plan dir (worktree-relative).
- `_status.append_phase(status_path, "planning", _timestamp.now_utc_iso())`.

**Commit on the task branch.** `git -C <worktree> add task/plan/ task/status.md && git commit -m "mill-plan: write plan for {slug}"`.

### Phase: Plan Review

Loop up to `max_review_rounds` rounds. Each round:

1. Report: **"Plan Review — round N/max_review_rounds"**.

1.5. **Step 1.5: pre-review validator gate (auto-run, no round consumed)**

   - The CLI auto-runs `_plan_validate` before invoking the LLM. If the validator finds anything, the CLI exits 1 with a JSON envelope on stdout (`{"errors": [...], "summary": "<n> finding(s) across <m> batch(es)"}`). No review file is written; no LLM token is spent; no review round is consumed.
   - On validator-failure exit, mill-plan parses the JSON and applies one mechanical fix per error dict, per the mapping table below. After fixes, mill-plan re-runs the review CLI via millpy-bg (slug `plan-validator-fix`; still no round consumed). Poll `cat <log-path>` until `[mill-bg] EXIT`, then extract the JSON line from the log.
   - **Two-pass cap:** if the validator fails again on the second pass, mill-plan halts with `BLOCKED: plan-validate non-progress` and writes the unresolved errors to the user. Do NOT auto-retry beyond the second pass. The two-pass cap matches the `review.code.self_fix_rounds` self-fix pattern.
   - If `pipeline.skip_validate: true` ever appears in config (currently it does not; this is a future hook), pass `--skip-validate` to the CLI and skip step 1.5 entirely. mill-plan passes `--skip-validate` only when the fix table instructs it — see the `wiki-config-mutation` row.

   | check                          | mechanical fix                                                                                                  |
   | ------------------------------ | ----------------------------------------------------------------------------------------------------------- |
   | non-existent-path              | If the path is a typo of an existing file, correct it. If it is meant to be a Creates: target in this plan, move it from Context:/Edits: to Creates: in the appropriate card. If neither applies, the planner intended to read a file that does not exist — halt; this is not mechanically fixable. |
   | card-missing-field             | Add the missing field with a sensible default: Context: → list the file(s) the requirement names; Edits: → none if the card creates a new file only; Creates: → none if the card edits an existing file only; Requirements: → restate the card title as a one-sentence requirement; Commit: → derive from the card title using the existing conventional-commit prefix pattern. |
   | card-numbering                 | Renumber cards within the affected batch sequentially starting at the lowest existing number; if the conflict is across batches, re-number the later-batch's cards to start above the earlier batch's max. Update every "card N" reference inside the plan. |
   | depends-on-unknown             | If the unknown dep is an integer, compare it against the `number:` values in the Batch Index — if close to an existing number (likely a typo), correct it. If the unknown dep is a string (legacy format), compare it against the `name:` values — if it is a typo of an existing entry, correct it. If the dependency genuinely needs a new batch, halt — adding a batch is not a mechanical fix. |
   | parallel-modifies-overlap      | If one batch logically depends on the other, add the missing edge to the dependent's depends-on list. If the two batches truly need to write to the same file in parallel, the plan is structurally wrong — halt.        |
   | reads-not-backtick-path        | Re-format the bullet to backtick-only paths; move any inline parenthetical commentary to the card's Requirements: prose. Strip any line-range suffix (e.g. `:55-65`) from the path.                                       |
   | all-files-touched-mismatch     | Update the overview's All Files Touched to match the union of every card's Edits: + Creates:. (The overview list is derivative; the cards are the source of truth.)                                                |
   | wiki-config-mutation           | This check cannot be fixed by editing plan files — the batch intentionally modifies `wiki/config.yaml`. To proceed, verify one of two conditions: (a) a bootstrap card is present — a card whose body explains why the config.yaml change is safe mid-flight for the currently-shipping task; or (b) the modified keys are provably unused — meaning key *removal or rename* where zero grep hits across `scripts/` and `skills/` confirm no existing code references them. (For key *addition* where consuming code is also being added in the same plan, zero grep hits does NOT satisfy condition (b); use (a) or halt.) If either condition holds: document the justification in the validator-fix commit message and re-run the CLI with `--skip-validate`. If `wiki-config-mutation` co-occurs with other fixable validator errors, fix those first per their rows, then re-run with `--skip-validate`. If neither condition holds: halt — the plan requires redesign. |
   | missing-overview               | Halt — the plan is structurally broken, not mechanically fixable.                                                                                                                                                       |
   | batch-index-parse              | Halt — the overview's fenced-yaml block is unparseable; not mechanically fixable.                                                                                                                                        |

   Rows where the fix is "halt" are deliberate: those errors signal a structural planning bug that auto-fixing would mask. The two-pass cap fires for these too (the second pass will produce the same error and trigger halt).

   After applying mechanical fixes for every error in the JSON, mill-plan commits the fix(es) on the task branch: `git -C <worktree> add task/plan/ && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"` and re-runs the CLI. The commit message uses `validator-fix` to distinguish it from `plan-fix-r{N}` commits (which are LLM-fix-pass commits).

2. Invoke the CLI as a subprocess:

   ```bash
   uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
       --slug plan-review-r<N> -- \
       uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-review-plan.py"
   ```

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then read the log and extract the JSON summary line (the last non-empty, non-sentinel line).

   The script discovers the slug and round from disk. It prints one JSON line: `{"type": "plan", "round": N, "verdict": "APPROVE" | "REQUEST_CHANGES", "blocking_count": N, "reviews": [...]}` where each review entry has `{scope, verdict, file}`.

3. **BEFORE reading any review file, load the `mill-receiving-review` skill** (`plugins/mill/skills/mill-receiving-review/SKILL.md`). Non-negotiable. The VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree is what keeps review loops useful.

4a. On `APPROVE` (verdict from JSON): set overview frontmatter `approved: true` via direct Edit. `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`. Commit on the task branch: `git -C <worktree> add task/plan/ task/reviews/ task/status.md && git -C <worktree> commit -m "mill-plan: approve plan for {slug}"`. Push. Break loop → Handoff. `iso_ts` is `_timestamp.now_utc_iso()`.

4.5. **Step 4.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from step 2 has a non-empty `reviews[]` array AND every entry's `verdict` is `"ERROR"`, skip steps 4a/4b/4c entirely and immediately re-run:

   ```bash
   uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
       --slug plan-review-retry-r<N> -- \
       uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-review-plan.py"
   ```

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then read the log and extract the JSON summary line (the last non-empty, non-sentinel line).

   The round counter is **not** consumed — the round produced no reviewable output. On the **second** consecutive ERROR-only round, halt with `BLOCKED: review ERROR-only round {N}` and surface each entry's `error` string to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors step 1.5's validator gate. *(Closes #84 — `verdict: ERROR` tracking was introduced so ERROR rounds never silently collapse into 4b's NIT path.)*

4b. On `REQUEST_CHANGES` AND `blocking_count == 0` (the JSON's top-level field): the round produced only NITs. Apply NIT fixes per the `mill-receiving-review` Decision Tree (no different from a regular fix-pass), write the fixer report at `task/reviews/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md`, append `plan-fix-r{N}` to status timeline, set overview frontmatter `approved: true`, commit+push (single commit covering plan + reviews + status), break loop → Handoff. Do NOT run round N+1. Rationale: 0-BLOCKING means the planner and reviewer have converged; further rounds only churn cosmetic NITs.

4c. On `REQUEST_CHANGES` AND `blocking_count > 0`:
   - `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`.
   - Read each review file. For each finding, run the `mill-receiving-review` decision tree.
   - Apply fixes to plan files.
   - Write a fixer report at `task/reviews/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` with two sections: `## Fixed` (each fixed finding, one-line reference to the review file + quoted finding title) and `## Pushed Back` (each rejected finding, same format + reason citing code/doc/scope).
   - Re-validate the plan DAG (`_plan_dag.validate`).
   - `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`.
   - Commit on the task branch: `git -C <worktree> add task/plan/ task/reviews/ task/status.md && git commit -m "mill-plan: plan-fix round {N} for {slug}"`.

5. **Non-progress check** (after writing each fixer report from round 2 onward): **Skip this check when the latest round's `## Pushed Back` section is empty.** Empty Pushed Back means the planner addressed every finding cleanly — that is convergence, not non-progress. The check only fires when both rounds have a non-empty Pushed Back AND the title set is identical. If the set is identical, halt with `BLOCKED: Plan review non-progress round {N}` and tell the user to look at the fixer reports. Do not escape-hatch — non-progress means the planner and reviewer are stuck in a stable disagreement; user intervention is required.

6. **Max-rounds escape** (only when round counter exhausts without APPROVE, BLOCKINGs still remain, AND non-progress did not fire): present the user with the prompt below verbatim, computing `{N}` and `{M}` and a one-line recommendation. `{M}` is `result["blocking_count"]` from the most recent CLI invocation — do not re-count manually. If `blocking_count` was 0 in the latest round, this prompt should not have fired — verify step 4b logic before presenting.

   > After {N} rounds, {M} BLOCKING findings remain unresolved (blocking_count from latest round's review JSON). Options:
   > A) Deep problems — rethink approach. Go back to mill-start and revise discussion.
   > B) Shallow — one more review round. Invoke: `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py" --max-rounds {N+1}` (the `--max-rounds` flag overrides the configured cap; without it the script re-reads config and exits at the same cap again).
   > C) Override — accept findings and proceed to mill-go anyway.
   > Recommended: {A/B/C} based on {analysis of remaining findings}.

   Wait for the user's choice. A → halt and tell user to check out fresh after they revise. B → invoke `millpy-review-plan.py --max-rounds {N+1}` where `{N}` is the round count just reported (one extra round beyond the configured max). C → set `approved: true` and proceed to Handoff.

### Phase: Handoff

`_status.append_phase(status_path, "planned", _timestamp.now_utc_iso())`. Commit+push.

If the deep-merged config has `pipeline.auto_report: true`, invoke `/mill-self-report` with no argument and let it finish before reporting to the user. The skill checks `gh auth` itself and bails cleanly if absent, so this is always safe to call.

Report: **"Plan complete. Run `/mill-go` next to start autonomous implementation."** Do not invoke mill-go yourself — handoff to mill-go is always an explicit user decision, even when auto-report fired.

## Timestamps

Always use `_timestamp.now_utc_compact()` / `now_utc_iso()` for any generated timestamp (plan `started:`, fixer-report filenames, status.md timeline rows). Never hand-write or guess a date.

## Principles

- **Plan the full scope** — no "we'll add X later" phases inside the plan.
- **YAGNI ruthlessly** — don't plan for hypothetical requirements.
- **Follow `mill-receiving-review`'s decision tree** — never dismiss a finding with "low risk", "out of scope", "pre-existing".
- **Autonomous** — the only user interaction is the max-rounds escape and non-progress halt.
- **Card `Context:` is an allowlist** — list every file the implementer needs to read WITHOUT editing. An empty or terse `Context:` is a review-blocker. The implementer reads ONLY listed files; any unlisted file is a plan defect. `Edits:` files are implicitly read — do not repeat them in `Context:`. All paths must be backtick-wrapped, one per bullet; no inline prose, no line-range suffixes.
- **`Requirements:` must use stable identifiers** — name the specific function, class, or constant being changed. "Replace `_load_config` in `mill-claim.py` with `from _config import load_config`" is correct. "Refactor config loading to use the shared helper" is not — it forces the implementer to explore, defeating the cold-start guarantee.

## Board discipline

- Task-state writes (`task/status.md`, `task/plan/`, `task/reviews/`) are committed on the task branch via `git add` + `git commit`, then pushed to remote. They never go through the wiki.
- Phase transitions via `_status.append_phase`. Hand-editing the status.md yaml block is banned; use `update_field` for the plan pointer.
- The overview frontmatter's `approved:` field is the exception — it lives in `plan/00-overview.md`, not `status.md`, and is flipped by a direct Edit because `_status.py` only knows about status.md.
