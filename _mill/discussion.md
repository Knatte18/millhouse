# Discussion: mill-go-base / mill-plan documentation gaps

```yaml
task: mill-go-base / mill-plan documentation gaps
slug: mill-go-plan-doc-gaps
status: discussing
parent: main
```

## Problem

Three orchestration docs leave behaviour implicit or read as something they do not do, and live runs tripped on each:

- **#1150** — `plugins/mill/skills/mill-go-base/SKILL.md` documents the `_status.append_inferred_success_log` audit call only inside two narrated branches (step 3(b) "Clean mid-work stop" and step 5.5.3 "After recovery").
  `millpy-implement.py --stage finalize` also returns `"inferred": true` on the plain success path (e.g. the full-history `card_commit_messages` fallback in `_implementer_common.finalize_from_output`, which emits an inferred success after a self-resolve re-fire minted a fresh `start_sha`).
  Step 6 ("Branch on verdict") gives no instruction for that case, so a literal reader skips the audit row on the most common success path.
- **#1145** — mill-go's Stuck-escalation self-resolve re-fires the implementer fresh (new session, no memory).
  A `Commit: none` card whose Requirements perform an external, hard-to-reverse side effect (e.g. `gh issue comment` + `gh issue close`) leaves no git-log trace, so the fresh session re-performs it — observed on task `deactivate-codeguide`, batch `close-issue`, where it would have posted a duplicate comment on a real GitHub issue.
  `plugins/mill/templates/implementer-brief.md` currently tells the implementer to treat a Commit: none card as complete once it has "(re-)performed" its Requirements — it actively invites re-performing.
- **#1148** — mill-plan's "Done-gate reminder" (`plugins/mill/skills/mill-plan/SKILL.md`, Phase: Plan) uses wording like "default `done_gate` to include it" and "author `done_gate: golangci-lint run`", which reads as mill-plan applying a config value.
  mill-plan never writes `mill-config.yaml`; a plan recorded a Shared Decision `done-gate-is-full-suite-not-lint`, and mill-go's Handoff pre-done gate still saw `pipeline.done_gate: null`, so the task's stated acceptance bar was never gated.

Why now: all three were filed on 2026-09-23 from live runs; #1145 nearly caused an externally visible duplicate action.

## Scope

**In:**

- `plugins/mill/skills/mill-go-base/SKILL.md` — consolidate the inferred-success audit call into step 6 as the single generic call site; replace the two narrated inline calls (step 3(b) `status: success` bullet, step 5.5.3 "After recovery") with a pointer to step 6.
- `plugins/mill/scripts/_status.py` — fix the stale caller reference in `append_inferred_success_log`'s docstring ("mill-go's step 4(b) and step 6.5 call sites") to name mill-go-base's Agent-mode dispatch step 6.
- `plugins/mill/templates/implementer-brief.md` — add a generic external-side-effect idempotency rule for Commit: none cards, applying on every dispatch (fresh, re-fired, resumed, warm-resumed), and reword the existing "(re-)performed" sentence so it no longer invites blind re-performance.
- `plugins/mill/skills/mill-plan/SKILL.md` — (a) card-authoring guidance: a Commit: none card with an external side effect must spell out, in its Requirements, the concrete external-state check that proves the action already happened; (b) reword the "Done-gate reminder" so it is explicitly advisory: mill-plan never writes `mill-config.yaml`; a done_gate recommendation is recorded as a Shared Decision labelled as not applied, stating the currently effective value; a task-specific acceptance bar (e.g. full suite must pass) is expressed as a batch `verify:` (using the existing `verify-full-suite` justification escape hatch) instead of a done_gate Decision.
- `plugins/mill/templates/plan-batch.md` — one-line addition next to the existing Commit: none convention paragraph, mirroring mill-plan's card-authoring rule (a).

**Out:**

- Any code change to `_implementer_common.py` finalize logic or to when `inferred` is emitted — the behaviour is correct; only the docs lag.
- Any runtime/structural idempotency mechanism (e.g. marker files, status.md records of performed side effects, a new `Commit: none` sub-field) — the fix is instruction-level.
- Making mill-plan write `pipeline.done_gate` into `mill-config.yaml` or `.millhouse/config.local.yaml`, and any per-plan done_gate override read by mill-go.
- The hub `mill-config.yaml` vs `plugins/mill/templates/mill-config.yaml` comment drift on `done_gate` (hub comment still says "even when a full test run is skipped"; template says "ONLY after first confirming").
  Real but separate; editing hub `mill-config.yaml` would also trip the `wiki-config-mutation` validator check.
- mill-go2 / mill-go wrapper SKILLs — they bind a variant contract; the affected text lives only in mill-go-base.

## Decisions

### inferred-log-single-call-site

- Decision: Step 6 ("Branch on verdict") of mill-go-base's `## Agent-mode dispatch` becomes the one place that states: whenever an implementer finalize envelope has `status: success` and `inferred: true` — on any path (plain first-turn success, clean mid-work stop, post-`incomplete`-recovery) — call `_status.append_inferred_success_log(status_path, batch_name, round, timestamp)` and commit `status.md` (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: log inferred-success for {batch_name}"`, with a ` (post-recovery)` suffix when the envelope came from step 5.5's recovery), before proceeding; skip when `inferred` is absent or `false`.
  Step 3(b)'s `status: success` bullet and step 5.5.3 keep their branch semantics but replace the inline call with "log per step 6's inferred-success rule, then proceed".
  Keep the signature line (`signature: _status.append_inferred_success_log(status_path: Path, batch_name: str, round: int, timestamp: str) -> None`) at the step 6 site.
- Rationale: prose rule "say it once"; a third inline copy at step 6 without removing the other two would double-log on the clean-mid-work-stop path, which already says "proceed normally to step 6".
  Keeps the existing post-recovery audit distinction via the commit-message suffix.
  Step 5.5.3's "structurally separate check" sentence becomes moot — a single step-6 site catches both first-turn and resumed-turn inference by construction; drop that sentence.
- Rejected: add a third inline call at step 6 only for the "plain" path (triplicates the rule, needs a fragile "not already logged" guard); leave the narrated sites and add a cross-reference (still misses the plain path unless step 6 itself states the rule).

### commit-none-external-idempotency-in-brief

- Decision: `implementer-brief.md` gains a rule in `## Implementation discipline` (outside the `<START_SHA>`-gated "Resume-after-incomplete" paragraph, since fresh re-fires have an empty `<START_SHA>`): before performing any external or hard-to-reverse side effect in a Commit: none card (network/API calls such as `gh issue comment`/`gh issue close`/`gh pr ...`, pushes to other remotes, messages, wiki/tracker mutations), first query the current external state and skip the action when it already reflects the intended outcome (e.g. `gh issue view <n> --json state,comments` before closing/commenting).
  This applies on every dispatch, because a prior session may already have performed it and the git log cannot show that.
  The existing sentence "Treat a Commit: none card as complete once you have (re-)performed its Requirements: verification step..." is reworded so completion means "its Requirements are satisfied — re-run pure verification freely; re-perform an external action only after the state check shows it has not yet happened".
- Rationale: the brief is the one text every implementer dispatch path shares (fresh start, transient retry, Stuck-escalation self-resolve re-fire, `--resume-incomplete`, warm `SendMessage`), so a single rule there covers the #1145 path and every sibling path; the Stuck-escalation text in mill-go-base need not change.
- Rejected: add the guard only to mill-go-base's Stuck-escalation re-fire text (the orchestrator does not execute cards — the implementer does, and other re-dispatch paths would stay unguarded); a runtime marker mechanism (out of scope, YAGNI).

### commit-none-external-check-in-plan

- Decision: mill-plan's card-authoring guidance (a new `**Commit: none cards with external side effects.**` paragraph in Phase: Plan, placed per Technical context) and `templates/plan-batch.md`'s Commit: none convention paragraph each get one rule: a Commit: none card whose Requirements perform an external side effect must include, in those Requirements, the concrete state check that detects "already done" (the command and the expected state), so the implementer's generic rule has an exact check to run.
  Guidance only — no new `_plan_validate` check (external side effects are not mechanically detectable from card fields).
- Rationale: the #1145 incident was manually fixed by exactly this — adding a `gh issue view` state comparison to the card's Requirements; making the planner write it up front turns the implementer rule from judgment into a concrete step.
- Rejected: a validator check keyed on `gh`/`curl` substrings in Requirements (false positives/negatives, brittle).

### done-gate-reminder-advisory

- Decision: Reword mill-plan's "Done-gate reminder" to state plainly that mill-plan never writes `mill-config.yaml` (hub, committed, shared across every future task) and never writes `.millhouse/config.local.yaml` for this purpose.
  Rewrite the imperative phrasings ("default `done_gate` to include it", "author `done_gate: golangci-lint run`", "leave `done_gate: null`") as recommendations the plan records.
  When mill-plan's analysis recommends a done_gate value different from the currently effective `cfg["pipeline"]["done_gate"]`, it records a `### Decision:` under `00-overview.md`'s `## Shared Decisions` explicitly labelled a recommendation for the operator — naming the recommended command, the currently effective value, and the sentence "Not applied: mill-go gates on the effective config value, not this Decision."
  If the task itself needs a repo-wide suite as its acceptance bar, the plan expresses that as a batch `verify:` command (the existing `verify-full-suite` escape hatch, with its required justification) — never as a done_gate Decision, because only `verify:` is actually executed from the plan.
- Rationale: #1148 offered two fixes (make it self-apply, or make it clearly advisory).
  Self-applying to hub `mill-config.yaml` leaks a per-task judgment into every future task after merge and trips `wiki-config-mutation`; writing `config.local.yaml` is gitignored, invisible, and lost on `mill-resume`.
  The batch-`verify:` route already exists and is what actually gates the task.
- Rejected: mill-plan writes hub `mill-config.yaml`; mill-plan writes `config.local.yaml`; a new per-plan `done_gate` frontmatter field read by mill-go's Handoff (new mechanism for a docs task).

## Technical context

- `plugins/mill/skills/mill-go-base/SKILL.md`, `## Agent-mode dispatch`:
  step 3(b) "Clean mid-work stop (implementer only)" `status: success` bullet (currently ~line 339, holds the first inline call);
  step 5.5 item 3 "After recovery" (~lines 441-447, second inline call plus the "structurally separate check" sentence);
  step 6 "Branch on verdict" (~lines 449-450) — gains the single rule.
  Commit messages use the literal `<VARIANT_LABEL>` placeholder — keep it.
- Where `inferred: True` is emitted: `plugins/mill/scripts/_implementer_common.py` `finalize_from_output` — no-JSON commit-count recount paths and the `card_commit_messages` full-history fallback on a self-reported success (docstring ~line 1845-1850). Some `inferred: True` envelopes are `status: stuck` (dirty tree, scope violations); the step-6 rule applies only to `status: success`.
- `plugins/mill/scripts/_status.py` `append_inferred_success_log` (~line 1388); docstring lines ~1400-1404 carry the stale "step 4(b) and step 6.5" caller reference.
- `plugins/mill/templates/implementer-brief.md` `## Implementation discipline`: "Resume-after-incomplete" paragraph (~lines 59-66) including the "(re-)performed" sentence; Commit: none also appears at ~lines 143-144 and ~167 (count/commit_sha rules — unchanged).
- `plugins/mill/skills/mill-plan/SKILL.md`: "Done-gate reminder" block (~lines 245-248); Commit: none appears in the Step 1.5 fix table row `commit-none-with-content` (~line 385). No dedicated Commit: none authoring paragraph exists in Phase: Plan.
  Place the new rule as its own bold-titled paragraph, `**Commit: none cards with external side effects.**`, in Phase: Plan's card-authoring area: immediately after the `**Renames and Moves.**` block (i.e. after its trailing "**Card numbering is global across batches**" line) and before `**Verify command shape.**`.
- `plugins/mill/templates/plan-batch.md` ~line 63: the Commit: none convention paragraph.
- No unit test pins the text of any of these SKILL/template passages (checked `unit_tests/` for the affected phrases).
- mill-go-base Stuck escalation re-fire text (~lines 886, 917) stays unchanged — the brief rule covers it.

## Constraints

- No `CONSTRAINTS.md` at the hub root.
- CLAUDE.md: never `sed`; semantic line breaks (one sentence per line) in markdown per the `prose` skill; `print()`/`_log()` ASCII-only (not touched here).
- The plan must not edit hub `mill-config.yaml` (out of scope; would trip `wiki-config-mutation`).
- Edits target the task worktree's `plugins/mill/**`, not the plugin cache.

## Testing

- Doc-only change plus a docstring edit; no behaviour change, no new unit tests.
- Regression guard: the `_status.py` docstring edit is covered by running `plugins/mill/unit_tests/test-status.py` (import + existing `append_inferred_success_log` tests).
- Batch verify commands must follow CLAUDE.md's `PYTHONPATH=` prefix convention, e.g. `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py`.
- Manual acceptance (reviewer checks): exactly one `append_inferred_success_log` call instruction remains in mill-go-base/SKILL.md (at step 6), both former sites point to it; the brief's idempotency rule sits outside the `<START_SHA>`-gated paragraph; the Done-gate reminder contains no imperative that implies mill-plan applies a config value.

## Q&A log

- **Q:** #1150 — where should the inferred-success logging rule live? 1) single generic rule at step 6, former inline sites point to it; 2) add a third inline copy at step 6; 3) cross-reference only. **A:** [auto-pick] Single generic rule at step 6. **Why:** says it once and avoids double-logging on the clean-mid-work-stop path that already flows into step 6.
- **Q:** #1150 — keep the ` (post-recovery)` commit-message suffix? 1) keep as a conditional suffix at the step-6 site; 2) drop it. **A:** [auto-pick] Keep as conditional suffix. **Why:** preserves the existing audit distinction at no cost.
- **Q:** #1145 — where does the idempotency guard go? 1) implementer brief (all dispatch paths) plus a planner rule to spell the check in Requirements; 2) brief only; 3) mill-go-base Stuck-escalation text only. **A:** [auto-pick] Brief plus planner rule. **Why:** the brief covers every re-dispatch path; the planner rule gives the implementer a concrete check, matching the manual fix used in the incident.
- **Q:** #1145 — add a `_plan_validate` check for external side effects in Commit: none cards? 1) no, guidance only; 2) yes, substring heuristic. **A:** [auto-pick] No, guidance only. **Why:** side effects are not reliably detectable from card text.
- **Q:** #1148 — make the done_gate Decision self-applying or advisory? 1) advisory, labelled "not applied", task acceptance bars go in batch `verify:`; 2) mill-plan writes hub `mill-config.yaml`; 3) mill-plan writes `config.local.yaml`; 4) new per-plan override read by mill-go. **A:** [auto-pick] Advisory. **Why:** hub writes leak per-task judgment hub-wide and trip `wiki-config-mutation`; local writes are invisible and non-durable; batch `verify:` already gates the task.
- **Q:** Fold in the hub-vs-template `done_gate` comment drift in `mill-config.yaml`? 1) out of scope; 2) include. **A:** [auto-pick] Out of scope. **Why:** separate hygiene item that would trip `wiki-config-mutation` and needs a bootstrap justification.
