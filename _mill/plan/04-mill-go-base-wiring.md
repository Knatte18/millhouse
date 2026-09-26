# Batch: mill-go-base-wiring

```yaml
task: Ask the parent session when stuck (parent_thread)
batch: mill-go-base-wiring
number: 4
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-base-agent-only.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
depends-on: [2, 3]
```

## Batch Scope

Wires the four mill-go converted sites (`go-batch`, `go-holistic-cap`, `go-handoff-nits`, `go-handoff-done-gate`) to the `ask-parent` skill.
The per-batch site needs a restructure: today every `### Stuck escalation` bullet records the block and then jumps to `### Blocked`;
afterwards the bullets pass halt parameters to `### Blocked`, which escalates first and records the block only when the halt proceeds.
`mill-go2` loads `mill-go-base`, so it inherits every change here with no edit of its own.
The holistic and nits retries use batch 2's `--parent-guidance` flag.
Each card edits one file, so cards are independent within the batch.

## Cards

### Card 9: `go-batch` — parameterised `### Blocked` with parent escalation

- **Context:**
  - `plugins/mill/skills/ask-parent/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `## Execute — sequential loop`: before "For each batch in `order`:", add one sentence initialising `parent_escalated_batches = set()` (session-local; the batches that already used their one `go-batch` parent escalation this run).
  - `### Stuck escalation` intro: replace the clause "the bullet's own escalation path sets batch state → `blocked`, appends the phase, commits, and goes to *Blocked*" with: the bullet's own escalation path goes to *Blocked* with `escalate: true` plus its halt parameters (`blocked_reason`, `commit_suffix`, `push`), and *Blocked* asks the parent session first and records the block only when the halt proceeds.
    Add one sentence: a parent-guided retry (see *Blocked*) does not reset any bullet's one-shot self-resolve or auto-retry, so a stuck result after it is a repeat and goes straight to *Blocked*.
  - Rewrite each stuck bullet's terminal recording sequence (`set batch state → blocked`, `blocked_reason: ...`, `_status.append_phase(... "blocked" ...)`, commit[, push], go to *Blocked*) as "go to *Blocked* with `blocked_reason: <the bullet's existing string>`, `commit_suffix: <value>`, `push: <value>`, `escalate: true`", keeping every existing reason string unchanged:
    `infrastructure` (`"infrastructure: worker died (logout?)"`, `commit_suffix: ""`, `push: false`);
    `transient` no-commits-after-retry (`"transient: no commits after retry"`, `""`, `false`);
    `incomplete` still-incomplete (`"incomplete after resume"`, `" (incomplete after resume)"`, `push: true`);
    `verify`/`logic` unresolved-after-retry (`"verify/logic: unresolved after retry"`, `""`, `false`);
    the `verify`/`logic` card-numbering-collision route (the collision text from the exception, `""`, `false`).
  - In step 2b, each of the four cleanliness-gate entries (out-of-scope untracked files; dead parent branch `fallback`/`cycle`; parent diff unresolvable; dirty tree) keeps its record-then-jump order and its own recording lines unchanged, and its "Go to *Blocked*" becomes "Go to *Blocked* with `escalate: false`".
    Keep the dead-parent entry's existing parenthetical about not adding a second notify/release.
  - Rewrite `### Blocked` as a parameterised funnel.
    Opening: parameters `blocked_reason`, `commit_suffix`, `push`, `escalate`;
    `escalate: true` means entered from a `### Stuck escalation` bullet with nothing recorded yet;
    `escalate: false` means the caller (a step 2b cleanliness gate, or a step 5 stuck bullet in the holistic-review companion file, which card 10 updates) already recorded the block, so steps 1 and 2 are skipped.
    Step 1, parent escalation — only when `escalate` is true and `batch_name` is not in `parent_escalated_batches`: add `batch_name` to the set, then load the `ask-parent` skill with site `go-batch`, reason `f"batch {batch_name}: {blocked_reason}"`, actions `retry,halt`.
    On `retry`: append one bullet `parent guidance: <guidance verbatim>` to the batch file's `## Prior failure` section (placement and create-if-absent rule exactly as the `verify`/`logic` self-resolve bullet states), apply any plan-file edits the guidance calls for (plan files only; the orchestrator never edits task code), commit `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "<VARIANT_LABEL>: parent-guided retry ({batch_name})"` with no `_status.append_phase` call (no new phase string: a crash mid-retry leaves `phase:` at its pre-halt value, which the "Mid-execution phase-gate widening" routing already resumes), then re-fire the implementer for this batch — for `blocked_reason == "incomplete after resume"` via the `start_sha`-preserving `--resume-incomplete` cold re-dispatch documented in "## Agent-mode dispatch" step 5.5, otherwise a fresh `millpy-implement.py <batch_name>` dispatch per "### 1. Implement" (no `--resume`) — and process its result from "### 2. Parse implementer report" onward; skip steps 2–3 below.
    State that mill-go-base has no `Commit: none` idempotency guard, so a re-fire can repeat an uncommitted external action exactly as the self-resolve re-fire can.
    On `halt`: `blocked_reason = blocked_reason + halt_suffix`, continue to step 2.
    Step 2, record — only when `escalate` is true: `_status.set_batch_field(status_path, batch_name, "state", "blocked")`, `_status.set_batch_field(status_path, batch_name, "blocked_reason", blocked_reason)`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on {batch_name}{commit_suffix}"`, push only when `push` is true.
    Step 3: the existing `_notify.notify(...)`, builder-lock release, and tell-the-user bullets, unchanged in content, running only when the halt proceeds.
- **Commit:** `feat(mill-go): escalate per-batch stuck halts to the parent session`

### Card 10: `go-holistic-cap` — parent escalation at holistic round-cap exhaustion

- **Context:**
  - `plugins/mill/skills/ask-parent/SKILL.md`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Next to the existing `max_holistic_rounds` / `min_holistic_rounds` / `auto_approve_on_cap` bindings, add `parent_escalated_holistic = False` and `holistic_cap_extended = False` (session-local).
  - Step 3's dispatch and step 3.5's retry dispatch (both `<cli> = millpy-review-code.py`): add "When `holistic_cap_extended` is true, also append `--max-rounds <max_holistic_rounds>` to `<args>`", repeated inline at both sites so the review CLI's round-cap check accepts the extra round.
  - Step 5's four stuck bullets (`infrastructure`, `transient`, the card-numbering-collision route, `verify`/`logic` unresolved-after-retry) keep their recording lines and change "go to *Blocked*" to "go to *Blocked* with `escalate: false`" (they record their own block; holistic fixer stuck is not a converted site).
  - Step 7, "**Otherwise**" branch (`auto_approve_on_cap` is `False`): before the existing _status.set_blocked, when `parent_escalated_holistic` is false, set it true and load the `ask-parent` skill with site `go-holistic-cap`, reason `f"holistic review exhausted {max_holistic_rounds} round(s)"`, actions `approve,retry,halt`.
    On `approve`: run the same terminal actions the `auto_approve_on_cap` `True` branch runs, with commit message `"<VARIANT_LABEL>: holistic approve {slug} (approved by parent)"`, and proceed to Handoff.
    On `retry`: let `H_last = max_holistic_rounds` and `review_file_path` be the `file` field of round `H_last`'s `reviews[0]`;
    write the guidance to `<briefs_dir>/parent-guidance-holistic-r{H_last}.txt`;
    dispatch the holistic fixer via the Agent-mode dispatch pattern with `<cli> = millpy-fix.py` and `<args> = --scope holistic --review-file <review_file_path> --round {H_last} --parent-guidance <briefs_dir>/parent-guidance-holistic-r{H_last}.txt` — step 5's `REQUEST_CHANGES` fixer shape, never step 4's `--nits-only` shape, since this round still has unresolved BLOCKINGs — handling its stuck results with step 5's bullets;
    on success set `max_holistic_rounds = H_last + 1` (session-local; config untouched) and `holistic_cap_extended = True`, then run one more loop iteration at `H = max_holistic_rounds` (steps 0–6; no new phase string is appended beyond what those steps already append).
    If that extra round again exhausts the cap, this step 7 runs again and halts without asking (the escalation is spent).
    On `halt`: the existing halt, with `halt_suffix` appended to both the set_blocked reason and the halt message.
- **Commit:** `feat(mill-go): escalate holistic round-cap exhaustion to the parent session`

### Card 11: `go-handoff-nits` and `go-handoff-done-gate` parent escalation

- **Context:**
  - `plugins/mill/skills/ask-parent/SKILL.md`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add one sentence at the top of the file (after the H1): initialise `parent_escalated_nits = False` and `parent_escalated_done_gate = False` for this Handoff run; each gate may ask the parent session at most once per Handoff run (the two gates fail for unrelated reasons, so each has its own flag).
  - Nit-enforcement gate, "If it is STILL non-empty" paragraph: before the existing `_notify.notify` + builder-lock release, when `parent_escalated_nits` is false, set it true and load the `ask-parent` skill with site `go-handoff-nits`, reason `f"unfixed nits in scope(s): {scope_list}"`, actions `retry,halt`.
    The builder lock stays held during the wait (it is per-worktree and blocks nothing else).
    On `retry`: write the guidance to `<briefs_dir>/parent-guidance-holistic-r<H>.txt` (same `<H>` and directory as the prior-blocking digest above), re-dispatch the same NIT-fix pass (identical `--scope holistic --review-file <review-file-abs-path> --round <H> --nits-only --prior-blocking <digest-path>` args) with `--parent-guidance <briefs_dir>/parent-guidance-holistic-r<H>.txt` added, run its `--stage finalize` as before, then re-run `_nit_gate.compute_unfixed_nits(worktree_root, reviews_dir, status_path)`: empty -> proceed to the terminal cleanliness gate; still non-empty -> the existing notify/release/halt with no second escalation.
    On `halt`: the existing notify/release/halt, with `halt_suffix` appended to the `BLOCKED:` message and the notify text.
  - Fixer-dispatch check, step 2's still-`blocked` branch (the `mill-done-gate-fixer` agent exists): before the existing release/notify, when `parent_escalated_done_gate` is false, set it true and load the `ask-parent` skill with site `go-handoff-done-gate`, reason `f"done gate failed: {reason}"` (the re-run's `reason` field), actions `retry,halt`.
    On `retry`: dispatch `Agent(subagent_type: "mill-done-gate-fixer")` once more with the same brief plus, appended at the end, a `Parent guidance:` heading followed by the guidance verbatim; wait for it, re-run the "0. Pre-done gate" snippet; `ok` -> numbered step 1; still `blocked` -> the existing release/notify/halt with its "already attempted" note.
    On `halt`: the existing release/notify/halt with `halt_suffix` appended to the `BLOCKED:` message.
  - Step 3 (no `mill-done-gate-fixer` agent) stays user-only: add one sentence saying it never escalates, since there is nothing to re-dispatch.
  - The terminal cleanliness gate and the scope-violations cleanup gate stay user-only; do not change them.
- **Commit:** `feat(mill-go): escalate handoff nit and done-gate halts to the parent session`

## Batch Tests

Pure skill text, so `verify:` runs the existing lint tests that scan these files, as chained direct invocations (see the overview's `skill-text-verify-uses-direct-invocations` Decision):
`test-skill-helper-drift.py` (every `_<module>.<fn>(` reference in `mill-go-base/SKILL.md` and its companion files resolves to a shipped function),
`test-mill-go-base-agent-only.py` (companion-file references and no dead dispatch literals),
`test-mill-go-variants.py` (mill-go/mill-go2 variant contract against `mill-go-base`).
