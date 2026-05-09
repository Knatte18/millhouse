# Discussion: 41 (A) — mill-start --auto flag

```yaml
task: 41 (A) — mill-start --auto flag
slug: mill-start-auto
status: discussing
parent: main
```

## Problem

`mill-start` is the only fully-interactive step in the mill task pipeline. It
runs codebase exploration, then loops on numbered-options prompts, waiting for
the operator to pick a number per question. For routine tasks where the
recommended option (always `1)` per the `mill:conversation` rule) is reliably
right, the operator's role is mechanical — they type `1` repeatedly.

The pipeline already has the surrounding pieces for hands-off operation:
`pipeline.auto_merge: true` lets `mill-go` chain into `mill-merge`
automatically, and task 39 just locked the "recommended is option 1" convention
across all `mill-start` prompts. What's missing is the entry point: a
`mill-start --auto` mode that does the same thorough exploration but answers
its own prompts by picking option 1 each time, logging the pick and rationale
to `task/discussion.md` so the operator can audit afterwards.

Combined with `pipeline.auto_merge: true`, this enables full claim-to-merge
autonomy on operator-launched routine tasks: `/mill-spawn → /mill-start --auto
→ /mill-plan → /mill-go` runs without operator intervention.

## Scope

**In:**

- New `argument-hint: "[--auto]"` line in `plugins/mill/skills/mill-start/SKILL.md` frontmatter.
- New prose subsection in `mill-start/SKILL.md` — "Auto mode" — declaring how `--auto` changes Phase: Discuss and Phase: Discussion Review behaviour.
- Phase: Discuss, when `--auto`:
  - Every operator prompt MUST be formatted as a numbered-options list (no free-text questions).
  - Instead of waiting for operator input, the assistant immediately auto-picks option `1)` (the recommendation, per `mill:conversation` rules).
  - Each auto-pick is appended to discussion.md's `## Q&A log` with the format:
    `- **Q:** <question> **A:** [auto-pick] <option-1-label>. **Why:** <rationale>.`
- Phase: Discussion Review, when `--auto`:
  - Review still runs up to `max_review_rounds`.
  - `mill-receiving-review` is still loaded before reading any review file (the existing non-negotiable rule still applies). Under `--auto` the PUSH BACK path is not available: there is no operator to escalate to. Every gap returned by the reviewer is treated as FIX regardless of the decision-tree outcome (factually-wrong gaps included — the assistant fixes by adding the missing information to discussion.md anyway, since arguing with a non-present operator achieves nothing).
  - On `GAPS_FOUND`, the assistant auto-resolves each gap: it adds the missing information to discussion.md using best judgment, commits, **pushes**, and re-runs the review.
  - If gaps remain after `max_review_rounds`: append `phase: blocked` via `_status.append_phase(status_path, "blocked", timestamp)`, set `blocked_reason: "auto: discussion review gaps unresolved after <N> rounds"` via `_status.update_field`, commit + push status.md, and halt with that message. Do NOT proceed to Handoff.
- Discussion.md template usage: every section is filled (no `_TODO:_` placeholders); auto-mode follows the existing template rules.

**Out:**

- No `millpy-start.py` CLI script. Argument handling stays prose-driven in SKILL.md (mirrors `/mill-self-report --auto`).
- No new fields in `task/status.md` for the `--auto` flag itself. The audit trail lives in discussion.md.
- No new helpers in `plugins/mill/scripts/`. No new unit tests. No new integration tests.
- No coupling to `pipeline.autonomous_mode` — that flag controls mill-go's stuck-handling and is orthogonal to mill-start's `--auto`.
- No `/mill-self-report --auto` invocation from mill-start. Self-report fires from mill-plan / mill-go's Handoff steps; mill-start has never fired it and continues not to.
- No "uncertainty check" or "destructive question pattern" detection. The operator opts into `--auto` knowing the task is routine; the audit log is the safety net.
- No changes to mill-spawn, mill-claim, mill-plan, mill-go, mill-merge, mill-cleanup, mill-autofix.
- No changes to the `discussion.md` template (`plugins/mill/templates/discussion.md`). The Q&A log format extension is documented in mill-start SKILL.md, not in the template.
- No changes to the discussion-review CLI (`millpy-review-discussion.py`) or any review helper.

## Decisions

### argument-shape

- Decision: bare `--auto` flag, parsed by SKILL.md prose.
- Rationale: matches the `/mill-self-report --auto` precedent (the only other auto-flag skill in mill). Prose-driven parsing keeps the change inside one file. Adding a `--auto=<reason>` string would require operators to invent rationales for routine flows — friction without value.
- Rejected: `--auto=<reason>`, config-driven `pipeline.start_auto: true` (requires editing config per invocation), positional argument.

### review-gaps-handling

- Decision: under `--auto`, run review as normal; on `GAPS_FOUND`, auto-resolve each gap with best-judgment edits to discussion.md, then re-run; if gaps persist after `max_review_rounds`, halt to `blocked` rather than fall through to Handoff.
- Rationale: this matches mill-go's behaviour under `pipeline.autonomous_mode` (halt-on-stuck rather than ask-user). Skipping review entirely loses the safety net the reviewer provides; halting immediately on first gap defeats the point of `max_review_rounds > 1`. Auto-resolving by best judgment respects the configured round budget, which is the operator's pre-declared tolerance for review iteration.
- Rejected: skip review under `--auto`; halt immediately on first `GAPS_FOUND`.

### free-text-prompt-ban

- Decision: under `--auto`, every operator prompt MUST be a numbered-options list. Free-text questions are forbidden — the SKILL must coerce them into options.
- Rationale: `--auto` semantics is "pick option 1". A free-text question has no option 1 to pick; auto-resolving would mean fabricating an answer, which is hallucination. The conversation skill already says "Prefer multiple-choice (A/B/C with trade-offs) when there are distinct options"; `--auto` strengthens "prefer" to "require".
- Rejected: allow free-text and fabricate the answer; halt-to-blocked on encountering a free-text question.

### audit-log-format

- Decision: extend `## Q&A log` entries with an `[auto-pick]` marker. Format: `- **Q:** <question> **A:** [auto-pick] <option-1-label>. **Why:** <rationale>.`
- Rationale: keeps a single audit section per discussion file. Operator skim-audits via grep `[auto-pick]`. mill-plan readers ignore the marker. No new section to maintain across template + SKILL.
- Rejected: dedicated `## Auto-pick log` section; separate `task/auto-picks.md` file.

### no-self-report

- Decision: `mill-start --auto` does NOT fire `/mill-self-report --auto` at Handoff.
- Rationale: mill-start has never fired self-report. mill-plan and mill-go fire it (gated on `pipeline.auto_report`). Adding a self-report call from mill-start expands scope beyond the task's stated goal of "auto-pick + audit log". YAGNI.
- Rejected: fire `/mill-self-report --auto` from Handoff when `pipeline.auto_report: true`.

### implementation-shape

- Decision: pure prose change in `plugins/mill/skills/mill-start/SKILL.md`. Add `argument-hint: "[--auto]"` to frontmatter; add a new "Auto mode" subsection (or weave the `--auto` rules into Phase: Discuss + Phase: Discussion Review).
- Rationale: matches the `mill-self-report` precedent exactly. `mill-start` has no Python driver; all behaviour is prose Claude reads. Adding a Python helper or a `millpy-start.py` CLI for one boolean flag is over-engineering.
- Rejected: helper in `plugins/mill/scripts/_skill_args.py`; new `millpy-start.py` driver; config field `pipeline.start_auto_default`.

### no-status-field

- Decision: do NOT add an `auto: true` field, an `auto_started_at:` timestamp, or any other new key to `task/status.md`.
- Rationale: status.md is the orchestrator's state machine. The `--auto` choice is a per-invocation operator decision, not a phase. The audit trail lives in discussion.md (specifically the `[auto-pick]` markers in `## Q&A log`). Adding a status field would couple two unrelated layers.
- Rejected: add `auto: true` to status.md YAML; add `auto_started_at:` timestamp.

### orthogonal-to-autonomous-mode

- Decision: `--auto` (mill-start, per-invocation) and `pipeline.autonomous_mode` (config, mill-go) are independent. `--auto` does not read or write `autonomous_mode`. Document the distinction in the mill-start SKILL "Auto mode" subsection.
- Rationale: they affect different skills and different decision points. `--auto` controls "should mill-start ask the operator during Discuss?"; `autonomous_mode` controls "should mill-go halt-or-ask when an implementer is stuck?". Coupling them would force operators who want one to accept the other.
- Rejected: `--auto` mutates `autonomous_mode` for the task (mill-autofix's mutate+restore pattern); `--auto` requires `autonomous_mode: true` already set.

### trust-the-recommendation

- Decision: under `--auto`, the assistant always picks option 1 regardless of stakes. No "uncertainty check", no "destructive pattern" halt, no `[uncertain]` marker.
- Rationale: the task description says the operator opts in for "routine tasks where the recommended choice is reliably right". Adding heuristic halts contradicts the contract. The audit log is the safety net — operator reviews after the fact, intervenes if needed.
- Rejected: halt-on-low-confidence; pattern-based halt for destructive picks; flag uncertain picks with an `[uncertain]` marker.

### fill-every-section

- Decision: under `--auto`, the assistant fills every section of discussion.md using best judgment. No `_TODO:_` placeholders. No halt-on-empty-section.
- Rationale: same posture as `mill-autofix`, which synthesises discussion.md programmatically with no operator interaction. mill-plan consumes discussion.md cold and needs every section to be self-contained. Placeholders defeat the contract.
- Rejected: allow `_TODO:_` placeholders for sections lacking signal; halt-to-blocked on empty section.

### no-new-tests

- Decision: pure prose change to one SKILL.md file. No new unit tests, no new integration tests.
- Rationale: there is no helper to test. The behaviour is prose Claude reads. The existing `_active`, `_status`, `_wiki`, `_paths` helpers are untouched. The discussion-review CLI is untouched. There is no surface where a unit test would catch a regression. Integration tests under `integration_tests/` already exist for the spawn → start → plan → go chain; if the operator wants end-to-end coverage, that is the right home — but it is out of scope for this task.
- Rejected: unit test exercising `--auto` against a tempdir worktree; integration test running `/mill-start --auto` end-to-end.

## Technical context

### Files mill-plan will touch

- `plugins/mill/skills/mill-start/SKILL.md` — the single file changed in this task.
  - Add `argument-hint: "[--auto]"` to the frontmatter (between `description:` and the closing `---`). Existing frontmatter has only `name:` and `description:`.
  - Add a new "Auto mode" subsection placed **immediately after the introductory paragraph** ("You are a collaborative solution designer…") — this frames the entire skill before any Phase begins, which keeps the auto-mode rules visible to readers regardless of which phase they jump into. The subsection must:
    - Define the `--auto` argument and its effect.
    - Specify the Phase: Discuss change (numbered-options-only; auto-pick `1)`; log per Q&A format below).
    - Specify the Phase: Discussion Review change (auto-resolve gaps; PUSH BACK unavailable; halt-to-blocked after `max_review_rounds`).
    - Specify the Q&A log format extension: `- **Q:** <question> **A:** [auto-pick] <option-1-label>. **Why:** <rationale>.`
    - Note the orthogonality to `pipeline.autonomous_mode`.

### Files mill-plan will NOT touch

- `plugins/mill/templates/discussion.md` — template stays as-is. The `--auto`-specific Q&A log format is a SKILL-level rule, not a template change.
- `plugins/mill/scripts/_active.py`, `_status.py`, `_wiki.py`, `_paths.py`, `_constraints.py` — no behavioural change.
- `plugins/mill/scripts/millpy-review-discussion.py`, `millpy-bg.py`, `_review_discussion.py` — discussion review CLI unchanged.
- `plugins/mill/skills/conversation/SKILL.md`, `mill-self-report/SKILL.md`, `mill-autofix/SKILL.md`, `mill-go/SKILL.md`, `mill-plan/SKILL.md` — no cross-skill changes.
- `wiki/config.yaml`, `.millhouse/config.local.yaml` — no new config keys.

### Reference patterns

- `mill-self-report --auto` argument handling — see `plugins/mill/skills/mill-self-report/SKILL.md` lines 4 (frontmatter), 21 (auto-fire description), 63 (skip-numbered-list rule). The pattern: `argument-hint:` declares the shape; prose elsewhere instructs the assistant on argument-conditional behaviour.
- mill-go's halt-to-blocked pattern under `pipeline.autonomous_mode` — see `plugins/mill/skills/mill-go/SKILL.md` lines 144 (stuck halt) and 197 (rounds-exhausted halt). The pattern: `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())` + `_status.update_field(status_path, "blocked_reason", "<reason>")` + commit + push + halt with operator-readable message.
- mill-autofix discussion.md synthesis — see `plugins/mill/skills/mill-autofix/SKILL.md` lines 250–300 (Step 5: Synthesise discussion.md). The pattern: fill every section using best judgment with codebase exploration evidence, no placeholders.
- Conversation skill numbered-options rule — see `plugins/mill/skills/conversation/SKILL.md` lines 31–38 (User Choices). Reference: option 1 is always the recommendation.
- Task 39's Q&A format work — see commit `6d66449` and the resulting line in mill-start SKILL.md: "Cap each batch at ≤5 questions; ask the rest in subsequent batches after the user answers." This task builds on the locked-in numbered-options convention.

### Q&A log: existing format

Template line 70: `- **Q:** … **A:** …`

Auto-mode entries extend this with the `[auto-pick]` marker and a `**Why:**` rationale clause:

```
- **Q:** <question> **A:** [auto-pick] <option-1-label>. **Why:** <rationale>.
```

Existing operator-driven entries keep the bare format. Mixed mode (operator interrupts auto mid-flow) is not specified separately — the assistant uses whichever format matches the actual answer source.

### Argument-string detection

`mill-start` SKILL.md prose checks the slash-command argument the same way `mill-self-report` does. From `mill-self-report/SKILL.md` line 63:

> If the skill argument is `--auto`: skip the numbered list entirely.

`mill-start` mirrors this: "If the skill argument is `--auto`: every Phase: Discuss prompt MUST be a numbered-options list, and the assistant immediately auto-picks `1)` instead of waiting for operator input."

## Constraints

(No `CONSTRAINTS.md` at hub root.)

Project-wide constraints inherited from `CLAUDE.md`:

- All intra-plugin paths reference `${CLAUDE_PLUGIN_ROOT}`, never `plugins/mill/...`. Not load-bearing here because this task only edits a SKILL.md file (no script paths emitted).
- Generated markdown uses fenced ```yaml for metadata, not `---` frontmatter — except SKILL.md, which uses `---` frontmatter. This task edits a SKILL.md file, so `---` is correct.
- Reviews match the tight v1 style: per-finding severity-label + 3–4 short bullets. Not load-bearing here (no review prompts changed).
- The `mill:conversation` skill rule: "the recommended option, if any, MUST be option 1; remaining options follow in any order. The `(Recommended)` suffix appears after the label of option 1." This is the foundational invariant that makes `--auto` deterministic. Any change to it would break `--auto`.

Operational constraints:

- Task-state writes commit on the task branch via `git -C <worktree> add … && git commit …` then push. Hand-editing the YAML block in `task/status.md` is banned (use `_status.append_phase` / `_status.update_field`).
- Phase progression is linear: `discussing → discussed → planning → planned → going → done` (or `blocked` from any active phase). The `--auto` flag does not introduce new phases — auto runs end at `discussed` (success) or `blocked` (review gaps unresolved).

## Testing

Per the `no-new-tests` decision: this task adds no unit tests and no integration tests.

The behaviour is prose in one SKILL.md file. Verification mode:

- mill-plan + mill-go's own discussion/plan/code review subsystems will exercise the wording during the implementation task itself (the discussion review running on this very `discussion.md` is the first verification pass).
- Manual smoke test (operator-driven, not a CI artifact): after merge, run `/mill-start --auto` against a small spawned task and audit the produced `task/discussion.md` for:
  - Every `## Q&A log` entry uses the `[auto-pick]` format with a `**Why:**` clause.
  - Every section is filled (no `_TODO:_` placeholders).
  - Phase progression: `discussing → discussed` on success, `discussing → blocked` on unresolved gaps.

Existing test surfaces (untouched):

- `plugins/mill/unit_tests/run-all.py` continues to pass — no helper code changed.
- Integration tests under `plugins/mill/integration_tests/` — no script paths or APIs changed; existing tests untouched.

TDD candidates: none. There is no helper to write a failing test against.

## Q&A log

- **Q:** Argument shape — bare `--auto`, `--auto=<reason>`, or config-driven? **A:** Bare `--auto`. **Why:** matches `/mill-self-report --auto` precedent; one-file change.
- **Q:** Discussion Review behaviour under `--auto` — skip / halt-on-first-gap / auto-resolve-then-halt? **A:** Auto-resolve gaps via best-judgment edits, halt to `blocked` after `max_review_rounds` of unresolved gaps. **Why:** matches mill-go's `autonomous_mode` halt-on-stuck pattern; preserves the configured round budget; doesn't lose the safety net.
- **Q:** Free-text prompts allowed under `--auto`? **A:** No — every prompt must be numbered options. **Why:** "pick option 1" has no meaning if there is no option 1; auto-resolving free-text is hallucination.
- **Q:** Audit log location — extend Q&A log, new section, or separate file? **A:** Extend `## Q&A log` with `[auto-pick]` marker. **Why:** single audit section per discussion file; grep-friendly; no template change needed.
- **Q:** Trigger `/mill-self-report --auto` at Handoff? **A:** No. **Why:** mill-start has never fired self-report; mill-plan/mill-go own that behaviour; YAGNI.
- **Q:** Implementation shape — prose, helper, or new CLI driver? **A:** Pure prose in mill-start SKILL.md. **Why:** mill-self-report precedent; no code logic to test; one-file diff.
- **Q:** New `task/status.md` field for `--auto`? **A:** No. **Why:** audit lives in discussion.md; status.md is the orchestrator's state machine.
- **Q:** Relation to `pipeline.autonomous_mode`? **A:** Orthogonal — independent flags affecting different skills. **Why:** different decision points (mill-start operator-prompt vs mill-go stuck-handling); operators should opt in to each separately.
- **Q:** Halt on destructive / high-stakes auto-picks? **A:** No — trust the recommendation. **Why:** operator opts in for routine tasks; the audit log is the safety net.
- **Q:** Allow `_TODO:_` placeholders in discussion.md sections? **A:** No — fill every section. **Why:** mill-plan consumes discussion.md cold; placeholders break the self-contained contract; mill-autofix synthesises sections the same way.
- **Q:** New unit / integration tests? **A:** None. **Why:** prose change; no helper code; existing tests untouched.
