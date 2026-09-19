# Discussion: mill-plan: planning-process documentation/procedure gaps

```yaml
task: mill-plan: planning-process documentation/procedure gaps
slug: mill-plan-planning-process-documentation-gaps
status: discussing
parent: main
```

## Problem

`mill-plan/SKILL.md` and its two rendered templates (`plan-batch.md`, `plan-overview.md`) have accumulated five distinct documentation/procedure gaps, each reported from a real autonomous run that hit the contradiction or omission live. Four are still present in the current tree; the fifth turned out to already be fixed by the time this task was picked up (see the "done-gate-revalidate" decision below — verified against the actual current file content, not the original bug report, per this task's own dependency note).

The four still-open gaps:

1. The two rendered templates state the `PYTHONPATH= ` verify-command rule as an unconditional MUST, contradicting `SKILL.md`'s own language-conditional carve-out (Python/mill projects only) — a planner rendering these templates into a Go/C#/etc. repo reads a rule that doesn't actually apply to them.
2. Three `SKILL.md` sites (two in Phase: Plan's "Write the files" steps, one in the Step 1.5 fix table) tell the orchestrator to render `plugins/mill/templates/plan-overview.md` / `plan-batch.md` — a path relative to the millhouse repo, unresolvable from cwd in every real invocation (a task worktree of some *other* repo). Every other path reference in the file already uses `${CLAUDE_PLUGIN_ROOT}`.
3. `SKILL.md` has no guidance telling a plan author that a batch card authoring a hard `git status --porcelain`-must-be-empty gate needs to carve out the currently-executing batch's own untracked implementer brief (`_mill/briefs/<batch>-r1.md`) — that file is written by the orchestrator before the implementer session starts and isn't committed until the batch's own end-of-batch commit, so it is structurally, unavoidably untracked at any earlier clean-tree checkpoint in that same batch.
4. The blocked-resume `--max-rounds` threading is internally inconsistent: one prose paragraph (Phase: Plan Review, "`--max-rounds` threading for blocked-resume") says to pass it only on the single round equal to `blocked_resume_round` and omit it on every later round of the same resumed loop — but the actual dispatch-site instructions for the subprocess/psmux branch (both Step 2's initial dispatch and Step 3.5's retry) already correctly say to pass `--max-rounds <local_max_review_rounds>` on every round for the life of the resumed loop. Further reading (this task's own investigation, not in the original bug report) found the Agent-mode dispatch sites are missing the equivalent reminder entirely — only the subprocess/psmux branch's two dispatch sites have it.

## Scope

**In:**
- `plugins/mill/templates/plan-batch.md` and `plugins/mill/templates/plan-overview.md`: add the same non-Python-project carve-out `SKILL.md`'s "Verify command shape" section already states for the `PYTHONPATH= ` rule (by reference, not by duplicating the full conditional text — see Decision "pythonpath-carveout-pointer").
- `plugins/mill/skills/mill-plan/SKILL.md`:
  - Three template-path references (Phase: Plan steps 1 and 3, Step 1.5's `move-mechanic-missing` fix-table row) rewritten from `plugins/mill/templates/...` to `${CLAUDE_PLUGIN_ROOT}/templates/...`.
  - A new `## Principles` bullet documenting the clean-tree-gate / untracked-implementer-brief carve-out, so a future plan authoring a hard porcelain-empty gate has a stated exemption to point to instead of independently rediscovering it (as happened twice in the same task per the source report, #998).
  - The "`--max-rounds` threading for blocked-resume" paragraph (Phase: Plan Review) rewritten to match the already-correct subprocess/psmux blockquote behavior: thread `--max-rounds <local_max_review_rounds>` on every round for the duration of a resumed (blocked-re-entry) loop, not just the first round back.
  - The two Agent-mode dispatch sites (Step 2's initial dispatch, Step 3.5's ERROR-retry) gain the same blocked-resume `--max-rounds` reminder blockquote the subprocess/psmux branch already has at both its equivalent sites.

**Out:**
- The `_plan_validate.run` re-validate gate in Phase: Plan Review's steps 4b/4c/4d (originally the fifth bundled item, #988) — already fixed in the current tree; see "done-gate-revalidate" decision. No edit in this task.
- Any change to `mill-start/SKILL.md`'s own (structurally similar) discussion-review round-cap machinery — out of scope; this task is `mill-plan`-only per its title.
- Any `.py` script change. All five bundled items are documentation/procedure text in `SKILL.md`/templates; none require touching `_plan_validate.py`, `_review_common.py`, `millpy-review-plan.py`, or any other script.
- Any broader redesign of the round-cap/`local_max_review_rounds` mechanism itself — this task only removes the internal contradiction in how it's already meant to work, per the Entry-step computation at line 131 (`local_max_review_rounds = N + max_review_rounds - 1`).

## Decisions

### done-gate-revalidate-already-fixed

- Decision: no code change for this bundled item (#988 — "fix-pass steps 4b/4c/4d never re-run the full `_plan_validate` gate before committing"). Verified against the current worktree's `plugins/mill/skills/mill-plan/SKILL.md`: steps 4b (line ~565), 4c (line ~581), and 4d (line ~597) each already call `_plan_validate.run` with the full, correct 8-keyword-argument signature (`root`, `git_root`, `wiki_root`, `skip_checks=plan_skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`, `done_gate`) — identical to Phase: Plan's own self-validate call.
- Rationale: `git log` on this file shows the full-validate-gate call sites at 4b/4c/4d already existed before the dependent task (`mill-plan-done-gate-kwargs-count-drift`, merged to main, commit `6df67b5e`) ran — that task's only change was correcting the *documented* kwarg count from a stale "7 kwargs" (missing `done_gate`) to the accurate "8 kwargs" already used at Phase: Plan's own call. In other words, the substantive #988 fix (adding the re-validate gate to 4b/4c/4d at all) had already landed by the time this task's dependency was filed; the dependency task only fixed a doc-drift in that already-added code's own kwarg-count claim. This task's brief anticipated needing to *add* a new call site and warned it would otherwise use the wrong 7-kwarg count — reading the current file shows there is no new call site to add: it's already there, and already correctly enumerated at 8 kwargs.
- Rejected: writing a no-op/verification-only card for #988 anyway, to leave an audit trail — rejected as pure overhead; `git blame`/`git log` on the three call sites is already the audit trail, and mill's "Never require two separately-numbered cards to land in the same commit" / YAGNI principles argue against a card with no diff.

### template-path-fix

- Decision: replace all three `plugins/mill/templates/plan-overview.md` / `plugins/mill/templates/plan-batch.md` literal references in `SKILL.md` (Phase: Plan step 1, step 3, and the Step 1.5 `move-mechanic-missing` fix-table row) with `${CLAUDE_PLUGIN_ROOT}/templates/plan-overview.md` / `${CLAUDE_PLUGIN_ROOT}/templates/plan-batch.md`.
- Rationale: matches the file's own established convention — every script path in the same file is already written `${CLAUDE_PLUGIN_ROOT}/scripts/...`; the "Interpreter-naming note" (line ~244) exists specifically because a cold orchestrator reaching for an unresolvable/ambient path breaks. Verified `${CLAUDE_PLUGIN_ROOT}/templates/` resolves and contains both files in the plugin cache.
- Rejected: leaving the paths repo-relative with a comment explaining the millhouse-self-hosting exception — rejected because mill-plan runs against arbitrary non-millhouse task worktrees in the overwhelming majority of invocations; a self-hosting special case would be the one that needs the comment, not the other way around.

### pythonpath-carveout-pointer

- Decision: in `plan-batch.md` (after the existing "Non-null verify: commands MUST start with..." line) and `plan-overview.md` (after its "it follows the same `PYTHONPATH= ` shape rule..." line), add one sentence pointing at `mill-plan/SKILL.md`'s "Verify command shape" section for the non-Python-project carve-out, rather than re-stating the full conditional text in both templates.
- Rationale: `SKILL.md`'s "Verify command shape" section is the single source of truth for this rule (Python/mill projects: `PYTHONPATH= ` required; non-Python projects: use the native runner directly, e.g. `go test ./...`) and is already enforced conditionally by `_plan_validate.py`'s `verify-not-isolated` check. Restating the full conditional in two templates is exactly how this bug happened — one wording (SKILL.md) got the carve-out added, the other two (rendered from a template, stripped of comments before writing) didn't. A pointer can't drift out of sync the same way a restatement can.
- Rejected: duplicating the full conditional text (Python vs. non-Python) into both templates — rejected per mill:prose's "say it once": duplicated conditional logic in three places is the root cause being fixed here, not a pattern to extend to two more.

### clean-tree-gate-brief-carveout

- Decision: add a new bullet to `SKILL.md`'s `## Principles` section (alongside the existing card-writing guidance bullets) stating: a batch card that authors a hard `git status --porcelain`-must-be-empty gate must exempt `_mill/briefs/<currently-executing-batch>*.md` from that gate. State why inline (one sentence): that file is written by the orchestrator's `--stage prepare` before the implementer session starts and is committed only by the batch's own end-of-batch commit — so it is unavoidably untracked at any clean-tree checkpoint earlier in the same batch, in every plan run under mill-go, not just the reporting task's own matrix/benchmark-style batches.
- Rationale: the source report (#998) shows two independent implementers in the same task both had to treat the untracked brief as "out of scope" with no plan text to point to, and a holistic-review round then flagged the resulting dirty-tree entry as a rule violation, requiring a mid-task plan self-resolve. This is structural to mill's dispatch architecture (true for any batch, any plan, under mill-go) — exactly the kind of thing `## Principles` already exists to state once so future plans don't rediscover it.
- Rejected: adding the carve-out text to `plan-batch.md`'s template instead of `SKILL.md`'s Principles — rejected because the carve-out is planning *guidance* (what a card author must remember to write), not boilerplate every batch file needs verbatim; `## Principles` is where `SKILL.md` already keeps this class of authoring rule (see the adjacent `Context:`-is-an-allowlist and `Requirements:`-stable-identifiers bullets).

### max-rounds-blocked-resume-harmonization

- Decision: rewrite the "**`--max-rounds` threading for blocked-resume**" paragraph in Phase: Plan Review to state the rule the dispatch-site blockquotes already correctly implement: when the current loop was entered via the Entry `blocked` re-entry row, every prepare/finalize CLI invocation dispatched anywhere in this phase — for every round of that resumed loop, not just the round equal to `blocked_resume_round` — must additionally pass `--max-rounds <local_max_review_rounds>`. Additionally, add the missing blocked-resume reminder blockquote (mirroring the existing ones at the subprocess/psmux branch's Step 2 dispatch and Step 3.5 retry) to the two Agent-mode dispatch sites that currently lack it entirely (Step 2's initial Agent-mode dispatch, Step 3.5's Agent-mode ERROR-retry).
- Rationale: `millpy-review-plan.py` rejects `round_n > max_rounds` as a hard error, and every round of a resumed loop — not just the first — exceeds the original config-derived `max_review_rounds`. The subprocess/psmux branch's own blockquotes (Step 2, Step 3.5) already got this right, using `local_max_review_rounds` (the resumed loop's own extended budget, computed once at Entry as `N + max_review_rounds - 1` and already the substituted comparison value at every other site in this phase per the existing "Resumed-loop round-cap substitution" paragraph). The standalone prose paragraph higher up in Phase: Plan Review still states the original, narrower (and wrong) one-round-only rule, and the Agent-mode branch's two dispatch sites never got the reminder the subprocess/psmux branch has — an omission this task's own code reading surfaced, beyond what the source report (#994) described.
- Rejected: deleting the standalone prose paragraph and relying solely on the per-dispatch-site blockquotes — rejected because the paragraph is where the *why* (`round_n > max_rounds` hard error; this is a resource-relaxation, not a signal to run more rounds than convergence/step-6 logic already allows) belongs; the per-site blockquotes are terse "when to append this flag" reminders by design, matching the existing live-operator-override blockquote's own split between full-paragraph rationale and terse per-site notes.
- Rejected: using `blocked_resume_round` (the paragraph's current value) instead of `local_max_review_rounds` (the blockquotes' current value) as the harmonized value — rejected because `blocked_resume_round` is a single round number (the round the loop was blocked at), which would under-cap every later round in the same resumed loop exactly as the bug describes; `local_max_review_rounds` is the correct full extended-budget value and is already what every other round-cap comparison site in this phase uses per the "Resumed-loop round-cap substitution" paragraph.

## Technical context

- `plugins/mill/skills/mill-plan/SKILL.md` — the file under edit for four of the five items. Key existing anchors:
  - "Verify command shape" section (~line 217) — the accurate, language-conditional source of truth for the `PYTHONPATH= ` rule.
  - Phase: Plan "Write the files" steps 1/3 (~lines 200, 205) and the Step 1.5 fix table's `move-mechanic-missing` row (~line 382) — the three repo-relative template-path references.
  - `## Principles` section (~line 643) — existing card-authoring-rule bullets; the new clean-tree-gate carve-out bullet belongs here, alongside e.g. the `Context:`-is-an-allowlist bullet.
  - "`--max-rounds` threading for blocked-resume" paragraph (~line 324) — the stale, one-round-only prose.
  - "Resumed-loop round-cap substitution" paragraph (~line 346) — defines `local_max_review_rounds`'s substitution scope; the harmonized paragraph should read consistently with this one.
  - Subprocess/psmux branch blockquotes already correct: Step 2 (~line 479), Step 3.5 retry (~line 530) — `> Only when this loop was entered via the Entry \`blocked\` re-entry row..., append \` --max-rounds <local_max_review_rounds>\` ...; omit it on every other round.`
  - Agent-mode dispatch sites missing the equivalent reminder: Step 2's initial dispatch, just before `If \`agent\` (Claude provider only): follow the Agent-mode dispatch pattern...` (~line 430 currently only carries the live-operator-override blockquote); Step 3.5's Agent-mode retry (~line 515, same gap).
  - Entry step computing `local_max_review_rounds = N + max_review_rounds - 1` (~line 131).
- `plugins/mill/templates/plan-batch.md` (~lines 14–17) and `plugins/mill/templates/plan-overview.md` (~lines 16–18, 52) — the two templates needing the `PYTHONPATH= ` carve-out pointer.
- `_plan_validate.py`'s `run()` signature (confirmed 8 keyword args: `root`, `git_root`, `wiki_root`, `skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`, `done_gate`) — referenced only to confirm the done-gate-revalidate item needs no change; not edited by this task.
- Git history confirming the done-gate item's real state: commit `6df67b5e` ("mill-plan: Phase Plan Review's 4b/4c/4d re-validate gate says '7 kwargs', drops done_gate") shows the 4b/4c/4d full-validate-gate call sites already existed before that commit; the commit only corrected the documented kwarg count from 7 to 8.

## Constraints

- No `.py` script changes — this task is `SKILL.md`/template text only.
- `mill:prose`'s "say it once" rule governs the `pythonpath-carveout-pointer` decision: point at the single conditional-rule source rather than duplicating it a third time.
- Keep the fix scoped to `mill-plan`; do not touch `mill-start/SKILL.md`'s structurally similar (but out-of-scope) round-cap machinery even where the same class of bug could plausibly also exist there.

## Testing

No unit tests apply — every edit in this task is prose inside `SKILL.md`/`plan-batch.md`/`plan-overview.md`, not executable code, and none of `plugins/mill/unit_tests/` covers skill-file prose content.
Verification is a manual/grep-based consistency check per item, to be run by each batch's own `verify:` (or documented as `verify: null` with the check described in `## Batch Tests` if a meaningful `grep`-based command isn't practical for a given card):
- template-path-fix: `grep -rn "plugins/mill/templates/" plugins/mill/skills/mill-plan/SKILL.md` returns no results.
- pythonpath-carveout-pointer: both templates' `PYTHONPATH= ` paragraphs reference the SKILL.md section by name; `SKILL.md`'s own "Verify command shape" text is unchanged (this task only adds pointers in the templates, not new conditional text).
- clean-tree-gate-brief-carveout: the new `## Principles` bullet exists and names `_mill/briefs/<currently-executing-batch>*.md` explicitly.
- max-rounds-blocked-resume-harmonization: all four dispatch-site blockquotes (subprocess/psmux Step 2 and Step 3.5, Agent-mode Step 2 and Step 3.5) and the standalone prose paragraph agree on the same rule (`local_max_review_rounds`, every round of the resumed loop) — a reviewer/grep check for `local_max_review_rounds` appearing at all four dispatch sites plus the harmonized paragraph, and zero remaining occurrences of the paragraph's old `blocked_resume_round`-as-flag-value wording.

## Q&A log

- **Q:** For the `PYTHONPATH= ` template contradiction (#1035), should the fix duplicate the full Python/non-Python conditional text into both templates, or point at `SKILL.md`'s existing conditional section instead? 1) Point at `SKILL.md`'s "Verify command shape" section instead of duplicating (Recommended) 2) Duplicate the full conditional text into both templates **A:** [auto-pick] Point at `SKILL.md`'s "Verify command shape" section instead of duplicating. **Why:** the bug exists because the rule was stated in three places and only one got updated; a pointer has no second copy to drift out of sync, consistent with mill:prose's "say it once".
- **Q:** For the clean-tree-gate/untracked-brief carve-out (#998), should the new guidance live in `SKILL.md`'s `## Principles` section, or be added directly into `plan-batch.md`'s template text? 1) `## Principles` section in `SKILL.md`, alongside the existing card-authoring-rule bullets (Recommended) 2) Inline into `plan-batch.md`'s template **A:** [auto-pick] `## Principles` section in `SKILL.md`. **Why:** it's planning guidance a card author must remember, not boilerplate every batch file carries verbatim — matches where `SKILL.md` already keeps this class of rule.
- **Q:** For the blocked-resume `--max-rounds` inconsistency (#994), should the fix keep the paragraph's current `blocked_resume_round` value and instead correct the dispatch-site blockquotes to match it, or adopt the blockquotes' `local_max_review_rounds` value and correct the paragraph to match them? 1) Adopt `local_max_review_rounds` (matches the blockquotes, and matches every other round-cap comparison site's substitution per the "Resumed-loop round-cap substitution" paragraph) (Recommended) 2) Adopt `blocked_resume_round` (matches the paragraph as currently written) **A:** [auto-pick] Adopt `local_max_review_rounds`. **Why:** `blocked_resume_round` is a single round number — using it as the cap for every later round in the resumed loop reproduces the exact bug being fixed; `local_max_review_rounds` is the loop's actual extended budget and is already what every other comparison site in this phase substitutes.
- **Q:** Should the done-gate re-validate item (#988) get a plan card at all, given it's already fixed, so the plan has an explicit record of having checked it? 1) No card — the fix is already landed and `git log`/`git blame` on the three call sites is the audit trail (Recommended) 2) Add a zero-diff verification-only card confirming the 8-kwarg calls are present **A:** [auto-pick] No card. **Why:** a zero-diff card is exactly the "commit-none-with-content" anti-pattern `_plan_validate.py` already flags, and mill's own "Never require two separately-numbered cards to land in the same commit" / YAGNI principles argue against padding the plan with a no-op.
