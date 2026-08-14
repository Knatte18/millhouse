# Discussion: mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies

```yaml
task: mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies
slug: mill-plan-step6-and-fixtable-bugs
status: discussing
parent: main
```

## Problem

The wiki task consolidates six GitHub issues (#843, #844, #845, #852, #853, #854) reporting correctness bugs in `plugins/mill/skills/mill-plan/SKILL.md` and its validator (`_plan_validate.py`), all filed against runs of `/mill-plan` in **external repos** (`NORCE-DrillingAndWells/Models`, `Knatte18/loomyard`) using their locally cached copy of the mill plugin.

Cross-checking each issue against the **current millhouse worktree source** (not the plugin cache — this repo's own CLAUDE.md flags exactly this trap: "the cache and the worktree can silently diverge") found that **four of the six are already fixed** on this branch's history, by prior mill-plan runs on millhouse itself that predate these issue reports being filed against a stale external cache. Only two bugs are still live in the current source. See Decisions for the per-issue verdict and the fix design for the two live ones.

## Scope

**In:**
- `plugins/mill/skills/mill-plan/SKILL.md` Entry step 4 (`--revise` pre-check + phase table): add a resume path for `phase: blocked` (#852).
- `plugins/mill/skills/mill-plan/SKILL.md` Step 1.5 fix table, `verify-excludes-edited-tagged-test` row: correct the Go `-tags` remedy (#853).

**Out (already fixed — verify only, no code change):**
- #845 (missing `Otherwise` in step 6) — moot, see Decisions.
- #844 (bare CLI bypasses agent-mode dispatch) — moot, see Decisions.
- #854 (`wiki_root` unbound / `_load_root_from_overview` undefined) — moot, see Decisions.
- #843 (`context-completeness` fires on directory tokens) — moot, see Decisions.
- No new Python unit tests for the two in-scope bugs — both are pure `SKILL.md` prose/control-flow changes with no new executable code path (see Testing).

## Decisions

### already-fixed-issues (#845, #844, #843, #854)

- Decision: treat these four as already resolved. Do not modify code, tests, or `SKILL.md` prose for them. Do not re-litigate or re-verify beyond what's recorded here.
- Rationale, per issue:
  - **#845** (missing `Otherwise` running the `autonomous_mode` branch into the operator prompt): `mill-plan/SKILL.md`'s step 6 ("Max-rounds escape", currently lines ~515-519) no longer has any `pipeline.autonomous_mode` branch or operator-facing prompt at all — it is an unconditional `_status.set_blocked` halt. The Entry step 0 note even states this explicitly: "the former Max-rounds-escape prompt at step 6 is now an unconditional halt." The dual-branch contradiction the issue describes doesn't exist in the current text.
  - **#844** (bare CLI invocation bypassing agent-mode dispatch): the same removed prompt is what the issue's "Shallow — one more review round" bare-CLI option belonged to. With the prompt gone, there is no bare CLI invocation left to bypass agent-mode dispatch.
  - **#854** (`wiki_root` unbound / `_load_root_from_overview` undefined): current code (`mill-plan/SKILL.md` "Self-run the validator gate", ~lines 216-243) already binds and passes `wiki_root=wiki_path` (not the unbound `wiki_root=wiki_root` the issue quotes), and `from _review_common import _load_root_from_overview` imports a real, documented helper (`_review_common.py:1086`, matching the exact `root: str | None = None` parameter `_plan_validate.run` expects). Both parts of the issue are already correct in source.
  - **#843** (directory tokens in `Requirements:` demanding an illegal `Context:` fix): `_plan_validate.py`'s `_check_context_completeness` (line ~1533) already computes `existing_files = [p for p in existing if p.is_file()]` before deciding a token is `resolvable` — a directory-only match is never flagged, so the check never fires on the case the issue describes.
- Rejected: adding defensive regression tests for these four anyway. Three of the four already have dedicated test coverage from the commits that fixed them (e.g. `0e36d7e7` added 225 lines to `test-plan-validate.py`); re-touching already-tested, already-correct code/prose for a stale report risks unrelated churn with no bug to fix.

### revise-blocked-resume (#852)

- Decision: widen `--revise`'s existing pre-check (Entry step 4 of `mill-plan/SKILL.md`) to also accept `phase == "blocked"`, in addition to the existing `phase == "planned" and approved == true` condition. On the `blocked` branch:
  1. Do **not** touch the overview's `approved:` field (it's already `false`).
  2. `_status.append_phase(status_path, "planning", <timestamp>)`.
  3. Commit on the task branch: `git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-plan: --revise resume from blocked for {slug}"`; push.
  4. Bind a new local variable `blocked_resume_round = _review_common.discover_round(reviews_dir, "plan", "holistic")` (the next round number that will actually run).
  5. Fall through into the existing `phase: planning`/`plan-review-r{N}`/`plan-fix-r{N}` re-entry row (Phase: Plan Review; do NOT rewrite plan files) — same fallthrough target the existing `planned+approved` `--revise` branch already uses.
  - In Phase: Plan Review step 2's dispatch (both the Agent-mode branch's `<args>` and the subprocess/psmux branch's `millpy-review-plan.py` invocation via `millpy-bg`): when `blocked_resume_round` is bound **and** the current loop `round == blocked_resume_round`, thread `--max-rounds <blocked_resume_round>` into that round's dispatch only; omit it on every other round (mirrors the exact `--reviews-subdir revise-{N+1}` threading pattern already documented for the `planned+approved` `--revise` case, and mirrors mill-start's `--auto` extension-round mechanism, which threads `--max-rounds <max_review_rounds + 1>` the same way).
  - Do **not** reuse or extend the `revise-{N+1}` reviews-subdir namespacing (Phase: Plan Review's existing `revise_requested` override at lines ~266-270). That namespacing exists specifically for re-reviewing an *already-approved* plan without colliding with its original review files. A blocked-resume is a continuation of the *same never-approved* round sequence — reviews continue writing into the plain `reviews_dir`, picking up at `blocked_resume_round` via the normal `discover_round` mechanism.
  - Update the pre-check's existing "condition not met" halt message (today: names the current `phase:` and says revising an in-flight or unapproved plan is unsupported) to also cover this widened condition — i.e. it now fires only when `phase` is neither `planned+approved==true` nor `blocked`.
  - Add an explicit `blocked` row to the Entry step 4 phase table (mirrors `mill-go-base/SKILL.md`'s existing `| blocked | surface blocked_reason from status.md and halt |` row) for the **no-`--revise`** case: `phase: blocked` with no `--revise` flag surfaces `blocked_reason` and tells the operator to re-run `/mill-plan --revise` to resume with one extra round (or resolve manually), then halts. This is reached only when the `--revise` pre-check (which runs before the table) didn't intercept — i.e., plain `/mill-plan` with no flag.
  - No new state needs to persist across rounds (no `extension_used`-equivalent flag). Reasoning: the loop's own existing convergence-gate and step-6 max-rounds-escape logic both key off `round >= max_review_rounds` (the *original*, unbumped config value) to decide whether to keep looping — so the resumed round (`round == blocked_resume_round > max_review_rounds`) is *already* terminal by that existing logic regardless of its outcome: an `APPROVE` verdict hits the existing "implicit-approve-at-cap" branch in 4a/4b/4c; a `REQUEST_CHANGES` verdict with blocking findings re-triggers step 5 (non-progress) or step 6 (max-rounds escape) on that same round. The loop therefore never attempts a further round within the same `--revise` invocation, so the one-shot `--max-rounds` override never needs to be reissued mid-loop. A second block requires the operator to explicitly re-run `--revise` again, which recomputes `blocked_resume_round` fresh.
- Rationale: reuses existing, already-battle-tested machinery — `millpy-review-plan.py`'s own `--max-rounds` CLI override (already implemented, used nowhere in `mill-plan/SKILL.md` today) and mill-start's proven round-cap-extension shape — rather than inventing new mechanics. Bounded by construction: every resume grants exactly one additional round, with no risk of an unbounded auto-retry loop, since each resume requires an explicit operator-invoked `--revise`.
- Rejected:
  - A separate `--unblock` flag: unnecessary fragmentation — `--revise`'s existing meaning ("re-open this plan for another review pass") already covers "give the review loop another shot," whether the plan was previously approved or blocked.
  - A message-only Entry-table `blocked` row with no widened `--revise` (mirroring mill-go's existing row verbatim and stopping there): does not satisfy the issue's core ask (an actual resume path) — mill-go's `blocked` row was confirmed, while investigating this, to have exactly the same "surface and halt" dead end mill-plan has today, so it's not a working precedent to copy as the *complete* fix, only as the message-shape precedent for the no-`--revise` case.

### go-tags-chained-invocation (#853)

- Decision: in the Step 1.5 fix table's `verify-excludes-edited-tagged-test` row (`mill-plan/SKILL.md` ~line 326), replace the remedy text. Current text:
  > If a `-tags` flag already exists, append `,<tag>` to its value; otherwise append `" -tags <tag>"` to the command.

  New text (only the "already exists" branch changes; the "otherwise" branch is correct as-is per the issue's own note and is kept verbatim):
  > If a `-tags` flag already exists on the command: do not comma-join `<tag>` into its value. Note this is a defense-in-depth choice, not a correction of broken Go semantics — Go's `-tags` set is satisfied by ANY-membership (each file's own `//go:build` line is checked independently against the full enabled-tag set, so a plain single-tag `//go:build scout` file is compiled/run whenever `scout` is enabled, regardless of what else is also enabled; `-tags integration,scout` does NOT exclude it). The real risk is project-specific: some repos deliberately give tagged suites mutually exclusive semantics (a suite's own constraint combines its tag with a negation of a sibling suite's tag, e.g. to keep suites isolated for cost/reporting reasons) — comma-joining silently breaks that convention if it's in use, and this check cannot tell whether a given project relies on it. Instead, append a new ` && `-chained invocation of the same base command (same verb and package pattern as the existing invocation) carrying its own `-tags <tag>` flag — strictly safer, since it never assumes either way. Otherwise (no `-tags` flag anywhere in the command yet): append `" -tags <tag>"` to the command in place, unchanged.
- Rationale: verified against the actual check implementation (`_plan_validate.py`'s `_verify_command_has_any_tag`, ~line 2115) that this remedy round-trips cleanly: it scans the *entire* command string via `_RE_VERIFY_TAGS_FLAG.finditer(command)`, not just the first `-tags` occurrence, so a `&&`-chained second invocation's own `-tags <tag>` is correctly detected on re-validation — this fix will not trigger the two-pass validator-fix cap. The "no `-tags` yet" branch is left untouched because there is no existing tag to conflict with in that case — a single in-place `-tags <tag>` append is already correct, exactly as the issue states.
  **Correction (discussion-review r1, BLOCKING, confirmed accurate):** the first drafted version of this row claimed Go's `-tags` list is a conjunction (AND) that "satisfies neither" suite when comma-joined. That is factually wrong — this repo's own `_verify_command_has_any_tag` uses ANY-membership matching, which only makes sense because Go's `-tags` semantics are themselves ANY/union, not AND. The row text above was rewritten to ground the remedy in the real, narrower risk (project-specific mutual-exclusion conventions this check cannot detect) instead of a false universal semantics claim. The remedy (chain a new invocation) is unchanged — it remains strictly safer regardless of which theory justifies it — only the stated *reason* changed.
- Rejected: rewriting both branches to always chain a new invocation (even when no `-tags` exists yet) — unnecessary; the issue explicitly confirms the untagged case is already correct, and always chaining would produce a redundant untagged-plus-tagged invocation pair where one is unneeded.

## Technical context

- `plugins/mill/skills/mill-plan/SKILL.md` Entry step 4 (lines ~53-68) is the phase-table lookup; the `--revise` pre-check (lines ~56-60) runs *before* this table as a distinct branch.
- `plugins/mill/scripts/_review_common.py:496` (`discover_round`) — scans `reviews_dir` and returns `max(found) + 1` for a given `(review_type, scope)`; returns `1` if the dir doesn't exist. Use `scope="holistic"` for this hub (per-batch plan review is disabled: `roles.plan-review.batch.reviewer: null`).
- `plugins/mill/scripts/millpy-review-plan.py` already implements a `--max-rounds <N>` CLI flag (line ~59) that overrides both `roles.plan-review.batch.rounds` and `roles.plan-review.holistic.rounds` for that invocation only — not currently threaded from `mill-plan/SKILL.md` for the blocked-resume case; it needs to be added at the two step-2 dispatch call sites (Agent-mode `<args>`, subprocess `millpy-bg` invocation), matching how the existing `revise_requested` branch already threads `--reviews-subdir revise-{N+1}` at those same two call sites (lines ~266-270).
- `_review_plan.py:180` / `:990` — the CLI's own round-cap guard (`round_n > max_rounds` → hard error). This is *why* the override must be threaded through the CLI call, not just tracked in `SKILL.md` prose — without it, the resumed round's CLI invocation would itself reject the round before producing a review.
- `mill-go-base/SKILL.md:118` — the precedent for an Entry-table `blocked` row's message shape (`surface blocked_reason from status.md and halt`); confirmed by inspection that mill-go's own `blocked` handling is *also* just this surface-and-halt dead end (no resume mechanism), so it is copied only for the message shape of the no-`--revise` case, not as a template for the actual resume logic.
- `mill-start/SKILL.md`'s `--auto` mode extension-round mechanism (`prev_blocking_titles`/`extension_used`, and the `--max-rounds <max_review_rounds + 1>` threading rule) is the closest existing precedent for "grant exactly one more round past the cap" — mill-plan's design differs in that no `extension_used`-style flag is needed, because mill-plan's resume is explicitly operator-invoked per attempt (not an autonomous loop deciding whether to self-extend).
- `_plan_validate.py:2115` (`_verify_command_has_any_tag`) and `:2141` (`_check_verify_excludes_edited_tagged_test`) — the check this fix-table row responds to; Go-gated on `go.mod` presence (line ~2189).
- `_plan_dag.parse_verify_field` — the single normalizer for the `verify:` field (plain string or `{cwd, command}` mapping); a `&&`-chained multi-invocation string is still a single valid `command` string under this schema, executed as-is by whatever runs `verify:` (implementer/fixer via the Bash tool) — no schema change needed to support chaining.

## Constraints

None beyond what's captured in Decisions and Technical context — no `CONSTRAINTS.md` exists at the hub root.

## Testing

Both in-scope changes are pure `SKILL.md` prose/control-flow edits — neither adds a new Python code path, so neither needs a new `unit_tests/test-*.py` file. Existing coverage (`test-plan-validate.py`, `test-millpy-validate-plan.py`, `test-review-plan-flow.py`, `test-review-plan-finalize-round.py`, `test-status.py`) already exercises the underlying machinery this design reuses (`discover_round`, `--max-rounds`, `_verify_command_has_any_tag`, `_status.append_phase`) and needs no modification, since none of that machinery's *behavior* is changing — only how `mill-plan/SKILL.md` invokes/threads it.

What mill-plan's own plan should verify instead, as part of its own Phase: Plan Review self-checks (not a pytest file):
- **#852**: a manual control-flow trace confirming (a) the widened `--revise` pre-check's two conditions (`planned+approved==true` OR `blocked`) are mutually exclusive branches with a shared "neither met" halt; (b) the `blocked_resume_round` variable is bound only on the `blocked` branch and threaded into exactly one round's dispatch, both call sites (Agent-mode and subprocess); (c) the new Entry-table `blocked` row (no-`--revise` case) is reached only when the pre-check does *not* intercept.
- **#853**: a manual trace confirming the rewritten fix-table row still leaves the "no `-tags` yet" branch's example output identical to before (`go vet -tags scout ./...`), and that the "already exists" branch's example output for the issue's own repro (existing `-tags integration`, needs `scout`) produces `go vet -tags integration ./... && go vet -tags scout ./...` — matching the "correct fix was a third separate invocation" the issue states was applied by hand.

## Q&A log

- **Q:** Narrow scope to #852+#853, treating #843/#844/#845/#854 as already-resolved? **A:** [auto-pick] Yes — narrow scope; note the four as already-fixed. **Why:** all four already match current source with existing test coverage; re-touching them for a stale report risks unrelated churn.
- **Q:** How should mill-plan let an operator resume a `phase: blocked` task? **A:** [auto-pick] Widen `--revise` to accept `phase: blocked`, granting one extra round via a dynamically-computed `--max-rounds` override threaded into the resumed round's dispatch only. **Why:** reuses existing precedent (mill-start's round-cap-extension pattern, `millpy-review-plan.py`'s existing `--max-rounds` override flag) instead of inventing new machinery; bounded by construction (each resume grants exactly one more round; a repeat block requires another explicit `--revise`, no auto-loop risk); mill-go's own `blocked` row was confirmed to be an equally-inadequate "surface and halt" precedent, so it's reused only for message shape, not as the complete fix.
- **Q:** How should the fix-table row for Go `-tags` conflicts be corrected? **A:** [auto-pick] Keep the "no `-tags` yet" branch unchanged; rewrite only the "already exists" branch to chain a new invocation instead of comma-joining. **Why:** matches the issue's own explicit guidance ("the otherwise branch is fine as-is"); verified against `_verify_command_has_any_tag`'s implementation that a chained invocation round-trips cleanly through re-validation, so this fix won't trigger an endless validator-fix loop.
