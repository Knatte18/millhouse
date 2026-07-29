# Discussion: mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push

```yaml
task: mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push
slug: mill-plan-skill-doc-gaps
status: discussing
parent: main
```

## Problem

Two small, mechanical documentation gaps in `mill-plan/SKILL.md` and `mill-go/SKILL.md`, both self-discovered during an autonomous `/mill-plan` run this session (originally filed as GitHub issues #747 and #748, now closed and consolidated into this task).

**Gap A (was #748):** Neither `plugins/mill/skills/mill-plan/SKILL.md` nor `plugins/mill/skills/mill-go/SKILL.md` ever loads the `mill:conversation` skill. `plugins/mill/skills/mill-start/SKILL.md` loads it unconditionally at its Step 0, explicitly because its operator-facing prompts depend on `mill:conversation`'s numbered-options-with-recommended-first convention (and its ban on `AskUserQuestion`) being active in context. mill-plan and mill-go present structurally identical operator-facing prompts without ever loading that skill.

Verified during discussion (this is not speculative — both files were read in full):
- `mill-plan/SKILL.md` line 246-254 (the "Max-rounds escape" in Phase: Plan Review) presents a lettered options prompt (`A) ... B) ... C) ...` with a `Recommended:` line) — the same shape `mill:conversation` documents, but the file never loads that skill anywhere.
- `mill-go/SKILL.md` has several such prompts, none preceded by a load: the `infrastructure` stuck-type prompt (`1) Re-fire fresh (Recommended)` / `2) Block`, around line 490), the `incomplete` stuck-type prompt (`1) Skip to cleanliness gate (Recommended)` / `2) Retry from scratch`, lines 495-496), the `verify`/`logic` stuck-type prompts (lines 500, 502, 504), and the holistic-review-rounds-exhausted prompt (`1) Rethink` / `2) Skip holistic` / `3) Block`, lines 769-774).
- `mill-go/SKILL.md`'s Entry section (`## Entry`, line 12) currently opens with "**Step 0: Verify `CLAUDE_PLUGIN_ROOT`.**" (lines 14-18) — a natural insertion point for a new unconditional skill-load step, structurally mirroring mill-start's Step 0.
- `mill-plan/SKILL.md`'s Entry section (`## Entry`, line 12) currently opens directly with step 1 ("Resolve and bind the path variables...", line 14) — no existing Step 0 to extend; a new Step 0 must be inserted before it.

Risk named in the original issue: not just that today's hardcoded prompts might coincidentally already match the convention (they do, on inspection), but that a *future* prompt added to either file could silently violate the `AskUserQuestion` ban with no skill active in context to catch it.

**Gap B (was #747):** `mill-plan/SKILL.md`'s Phase: Plan "Commit on the task branch" step (line 116, the line immediately before the `### Phase: Plan Review` heading) reads:

> `git -C <worktree> add <plan_dir> <status_path> && git commit -m "mill-plan: write plan for {slug}"`

with no explicit "Push." — unlike every other commit-producing step in the same file. `## Board discipline` (near the end of the file) states task-state writes are "committed on the task branch via `git add` + `git commit`, then pushed to remote" as a general principle, but Phase: Plan's own literal step text doesn't say so. An executor following the literal step text (rather than inferring the general Board-discipline principle) could leave the initial plan commit unpushed until Plan Review's first round commit — a window where local and remote silently diverge, e.g. if the session is interrupted right after Phase: Plan.

Verified during discussion, a related gap not named in the original issue text: Phase: Plan Review's step **4d** (`On REQUEST_CHANGES AND blocking_count > 0`, ends at line 242) also has no explicit "Push." after its commit bullet:

> `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> _mill/briefs/ && git commit -m "mill-plan: plan-fix round {N} for {slug}"`

— unlike 4a (line 205, ends "...Push. Break loop..."), 4b (line 207, ends "...Push. Break loop..."), 4c (line 233, "commit+push (single commit covering plan + reviews + status + `_mill/briefs/`)"), and Handoff (line 260, "Commit+push."). 4d is the only one of the five commit-producing steps in Phase: Plan / Phase: Plan Review / Phase: Handoff missing the word "push" entirely.

## Scope

**In:**
- Add an unconditional `mill:conversation` load step to `mill-plan/SKILL.md`'s Entry, as a new step inserted before the current step 1, mirroring mill-start's Step 0 wording and placement exactly (load first, before any other Entry step or phase; state which prompts in this file depend on it).
- Add an unconditional `mill:conversation` load step to `mill-go/SKILL.md`'s Entry, at/immediately after the current Step 0 (`Verify CLAUDE_PLUGIN_ROOT`), same load-before-anything-else framing.
- Add "Push." to `mill-plan/SKILL.md`'s Phase: Plan commit step (line 116), matching the wording pattern used by 4a/4b (a separate "Push." sentence immediately after the commit instruction).
- Add "Push." to Phase: Plan Review's step 4d's commit bullet (line 242), same wording pattern, for consistency with 4a/4b/4c/Handoff.

**Out:**
- No change to `mill-start/SKILL.md` — it already loads `mill:conversation` correctly; it is the reference pattern, not a target of this fix.
- No change to any other commit-producing step in `mill-plan/SKILL.md` (4a, 4b, 4c, Handoff, the plan-review-skip branch at line 126, the validator-fix commit at line 167) — all of these already say "Push." or "push" explicitly; verified during discussion, no further gaps found among them.
- No change to `mill-go/SKILL.md`'s commit/push wording elsewhere in the file — this task's mill-go scope is limited to adding the missing `mill:conversation` load; mill-go's push wording was not flagged as a gap and was not audited for that separately in this task.
- No new validator/lint rule to mechanically enforce "every commit step must say push" or "every prompt-bearing file must load mill:conversation" going forward — this task fixes the two (now three, with 4d) known instances; a general enforcement mechanism is out of scope and not requested by either source issue.
- No behavioral change to any dispatch, review, or commit logic — this task is documentation-only (SKILL.md prose edits), touching no `.py` scripts.

## Decisions

### mill-conversation-load-placement

- Decision: In `mill-plan/SKILL.md`, insert a new numbered step at the very start of `## Entry` (before the existing step 1), worded to parallel mill-start's Step 0: load `mill:conversation` via the Skill tool, unconditionally, immediately, before any other Entry step or phase, with a one-sentence rationale naming that this file's prompts (the Phase: Plan Review max-rounds escape) depend on the skill's numbered-options/no-`AskUserQuestion` convention. In `mill-go/SKILL.md`, extend/adjoin the existing Step 0 (currently "Verify `CLAUDE_PLUGIN_ROOT`") with the same unconditional load, keeping it the first substantive action in Entry, with a rationale naming this file's stuck-escalation and rounds-exhausted prompts.
- Rationale: mill-start's own Step 0 already establishes the pattern and its justification word-for-word ("because prompts depend on [it] being active"); reusing that exact framing keeps the three orchestrator-tier skills (mill-start, mill-plan, mill-go) consistent and gives future skill authors one pattern to copy. Placing the load first (not lazily at each call site) means it protects prompts not yet written, which is the exact risk the source issue named.
- Rejected: Lazy-loading only immediately before each currently-known prompt call site — rejected because it requires enumerating every current AND future call site correctly, reproducing the exact maintenance burden the issue flags, and both mill-plan and mill-go have multiple scattered call sites (see Problem section) making a single lazy-load point impossible without picking one arbitrarily. Documenting-only (no load) — rejected because both files were independently verified in this discussion to have genuine numbered-options prompts today, not merely borderline cases; a documentation-only resolution would leave the `AskUserQuestion` ban unenforced in these files' context.

### push-wording-scope

- Decision: Fix Phase: Plan's commit step (line 116) AND Phase: Plan Review's step 4d's commit bullet (line 242) in the same task, both by appending "Push." as a separate sentence immediately after the existing `git commit` instruction — matching 4a's and 4b's exact wording pattern, not the "Commit+push." shorthand used by Handoff/4c.
- Rationale: Phase: Plan's commit step and step 4d's commit bullet are both single-purpose, single-commit steps structurally closest to 4a/4b's shape (a `git add ... && git commit -m "..."` followed by a bare "Push." sentence), so matching that exact pattern is the more natural fit than introducing the "Commit+push." shorthand seen in Handoff/4c. 4d was found during this discussion's verification pass (see Problem section) — same file, same category of gap (missing push instruction on an otherwise-complete commit step), trivial additional edit; leaving it unfixed immediately next to the Phase: Plan fix would be an obvious remaining inconsistency on next read of the same file, and it is exactly the kind of gap `mill-self-report` would likely re-file as a new issue afterward.
- Rejected: Scoping strictly to issue #747's literal text (Phase: Plan's commit step only) and filing 4d as a separate issue — rejected as needless process overhead for a one-line, same-file, same-root-cause fix already fully specified by this discussion. Using the "Commit+push." shorthand instead of a separate "Push." sentence — rejected only for consistency with the nearest structural siblings (4a/4b); no functional difference either way.

## Technical context

- Both target files: `plugins/mill/skills/mill-plan/SKILL.md` and `plugins/mill/skills/mill-go/SKILL.md` (paths relative to repo root; resolve via `${CLAUDE_PLUGIN_ROOT}` for any script invocation, but this task edits the skill files themselves — mill-plan's own project convention (CLAUDE.md) draws a line between `${CLAUDE_PLUGIN_ROOT}` for script/skill invocation vs. the task-worktree path for source verification; since these SKILL.md files ARE the source being edited, edit them at their task-worktree path, e.g. `plugins/mill/skills/mill-plan/SKILL.md` under the current worktree root, not the plugin cache).
- Reference pattern to mirror: `plugins/mill/skills/mill-start/SKILL.md`'s `## Entry` section, "**Step 0: Load `mill:conversation`.**" — read this verbatim before writing the two new Entry steps, to match its exact phrasing style (imperative, one short paragraph, names *why* prompts in that file depend on it).
- `mill-plan/SKILL.md` line numbers referenced above (116, 205, 207, 233, 242, 246-254, 260) and `mill-go/SKILL.md` line numbers referenced above (12, 14-18, 490, 495-496, 500, 502, 504, 769-774) are current as of this discussion but WILL drift once this task's own edits land — the plan should locate insertion/edit points by the quoted text/heading anchors given in the Problem section (e.g. "the line immediately before `### Phase: Plan Review`", "step 4d's commit bullet", "Entry section's current Step 0"), not by hardcoded line numbers.
- No other SKILL.md in `plugins/mill/skills/` was audited for either gap in this discussion — this task's scope is the two named files only (see Scope: Out).

## Constraints

No `CONSTRAINTS.md` present at hub root — none to enumerate.

- Documentation-only change: no `.py` script, template, or config file is touched. No `verify:` command is needed beyond confirming the edited SKILL.md files still parse as valid markdown with intact frontmatter (`---\nname: ...\ndescription: ...\n---`) — a plain read-back is sufficient; there is no automated SKILL.md linter in this repo today.
- Per CLAUDE.md's ASCII-only convention for generated output, keep any new prose ASCII (no em-dashes if hand-typing raw text is a risk — the existing files already use em-dashes in prose extensively, so match existing style; the ASCII rule in CLAUDE.md targets `print()`/`_log()` runtime output, not SKILL.md prose, so no constraint violation either way — noted here only to confirm it does not apply).

## Testing

Not applicable in the unit/integration-test sense — this is a prose-only edit to two markdown skill files with no executable code path. Verification is a manual read-back:
- Confirm `mill-plan/SKILL.md`'s new Entry step 0 appears before the existing step 1, and Phase: Plan's commit step (and 4d's commit bullet) each now end with an explicit "Push." sentence.
- Confirm `mill-go/SKILL.md`'s Entry Step 0 now includes the `mill:conversation` load alongside (or immediately after) the existing `CLAUDE_PLUGIN_ROOT` check.
- Confirm neither file's frontmatter (`---\nname: ...\ndescription: ...\n---`) was disturbed by the edits.
- No TDD candidates; no scenarios beyond the above to cover.

## Q&A log

- **Q:** Where/how to add the mill:conversation load for #748? **A:** [auto-pick] Add an unconditional load to both mill-plan/SKILL.md Entry (new step, before step 1) and mill-go/SKILL.md Entry (as part of/right after Step 0), mirroring mill-start's Step 0 pattern exactly. **Why:** Both files have multiple genuine numbered-options prompts today, and issue #748 explicitly worries about a future prompt silently violating the AskUserQuestion ban without the skill active — an unconditional Entry-time load (matching mill-start's own justification) is the only option that covers prompts not yet written.
- **Q:** Wording for the #747 fix (Phase: Plan's commit step)? **A:** [auto-pick] Append a separate "Push." sentence after the existing commit instruction, matching 4a/4b's exact wording pattern. **Why:** Phase: Plan's commit line is structurally closest to 4a/4b's single-commit-then-push shape; matching their exact wording keeps the file internally consistent rather than introducing a third phrasing style.
- **Q:** Include the newly-found 4d push gap (not in the original issue text) in this task's scope? **A:** [auto-pick] Yes — fix 4d alongside Phase: Plan in the same task. **Why:** Same root cause, same file, same review loop, negligible extra work — leaving 4d inconsistent immediately after fixing the sibling branches would be an obvious miss on next read, and mill-self-report would likely just re-file it as a new issue anyway.
- **Q:** Should the mill:conversation load be truly unconditional, or conditional on dispatch mode/expected prompt? **A:** [auto-pick] Unconditional at Entry, exactly like mill-start. **Why:** Matches mill-start's own precedent exactly, keeps the rule simple, and the load cost is negligible next to Implementer/reviewer dispatch costs already dominating both skills.
