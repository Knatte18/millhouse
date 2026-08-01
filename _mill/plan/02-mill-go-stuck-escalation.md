# Batch: mill-go-stuck-escalation

```yaml
task: 'Non-interactive pipeline: only mill-start''s interview may prompt the operator'
batch: mill-go-stuck-escalation
number: 2
cards: 1
verify: null
depends-on: []
```

## Batch Scope

`mill-go/SKILL.md`'s `### Stuck escalation` section (the per-batch implement/review stuck-handling routed to from `## Implement` step 4.5 and `## Execute`) is rewritten as one coherent unit — it is a single interdependent numbered-bullet list where every bullet's escalation path references the bullets around it, so splitting it into multiple cards risks corrupting cross-bullet anchors. Three sub-cases (`infrastructure`, `transient` with `commits_made > 0`, `incomplete`) already have a fully-specified `pipeline.autonomous_mode: true` branch today; this batch makes that branch the *only* behavior and deletes the sibling interactive numbered-prompt branch next to it. Two sub-cases (`transient` with no commits, `verify`/`logic` on first occurrence) have no existing autonomous branch today — they block immediately even under `autonomous_mode: true` — and get new one-shot self-resolve logic per Shared Decision `self-resolve-then-escalate-on-repeat`. This batch depends on nothing but is depended on by batch 3 (holistic review) and batch 4 (Handoff), which edit later sections of the same file — that dependency chain exists purely to avoid two batches editing `mill-go/SKILL.md` without an ordering edge between them (the `parallel-modifies-overlap` validator check), not because the sections' content overlaps.

## Cards

### Card 3: Rewrite Stuck escalation to unconditional self-resolve-then-escalate

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Find the `### Stuck escalation` section (the heading itself is unchanged by this card — only its body, everything below the heading, is replaced). The body currently reads exactly:

```
If the deep-merged config has `pipeline.autonomous_mode: true`: for any `stuck_type` (`transient` already-retried, `verify`, `logic`, `infrastructure`, `incomplete`): skip the user prompt; auto-handle according to the stuck_type rules below. **For `infrastructure` and `incomplete` only**, skip straight to the autonomous-mode handling in the relevant branch below (each has its own auto-resume/auto-retry step). For all others, set batch state → `blocked`, `blocked_reason: "autonomous-mode stuck: {stuck_type}"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name} (autonomous-mode)"` and push; invoke the per-batch cleanup block; go to *Blocked*.

- **`infrastructure`** (bg worker died, likely logout) — **interactive** mode: surface to user with options `1) Re-fire fresh (Recommended)` / `2) Block`; user picks. On re-fire: invoke the per-batch cleanup block, then re-invoke `millpy-bg` with a fresh CLI (no `--resume` flag — the killed session is dead). If the re-fire also reports `infrastructure`: set batch state → `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit, and go to *Blocked*. **`autonomous_mode: true`**: auto-retry ONCE with a fresh re-fire (no `--resume`). If the re-fire also fails with `infrastructure`: set batch state → `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit, and go to *Blocked*. State explicitly that the re-fire matches the existing `running`-state Resume (fresh start; killed session cannot be reattached).
- **CLI emits `stuck_type: transient`** (LLM-layer failure surfaced as the synthetic stuck JSON described in Implement step 2; the CLI exits 1 in that case but stdout carries the JSON) → apply the one-retry policy: re-invoke `millpy-implement.py <batch_name>` once with no `--resume` flag (a fresh session). If the second invocation also reports `stuck_type: transient`, escalate per the routing below.
- `transient` (already retried once):
  - **If `commits_made > 0` in the stuck JSON** (the implementer timed out after committing some work):
    - Interactive mode: present options:
      1) Skip to cleanliness gate (Recommended) — commits were made before the timeout; proceed directly to the cleanliness gate then code review
      2) Retry from scratch — re-fire the implementer as a fresh batch start
    - On option 1: skip re-invocation of the implementer; proceed to the per-batch cleanliness gate (scope violations check) then code review as if the implementer had reported success.
    - `autonomous_mode: true`: auto-pick option 1 (skip to cleanliness gate).
    - If `commits_made == 0` or the field is absent: use the existing three-option path below.
  - **Otherwise** (no commits made or timeout before any commit) → surface to user with three options: retry fresh, edit plan and retry, block. User picks.
- **`incomplete`** (batch provably partial — some cards committed, not all; reached here only when the in-line recovery already ran once and the batch is still partial) — resume preserving the original `start_sha`, never retry-fresh (Shared Decisions `stuck_type: incomplete is a new first-class classification` and `resume must preserve the original start_sha`; discussion `warm-resume-mechanism`, `start-sha-preserving-resume`):
  - **Interactive** mode: resume **once** and only escalate if that resume also returns `incomplete`. The resume is the warm-`SendMessage` path in agent mode (Agent-mode dispatch step 6.5) or a single `millpy-implement.py <batch_name> --resume-incomplete` re-dispatch in subprocess/psmux mode — both preserve the original `start_sha`. If the resume produces `success` (or inferred success), continue to the cleanliness gate then code review. If it is **still** `incomplete`, surface to user with three options: resume once more (`--resume-incomplete`), edit plan and resume, block. User picks. Never re-fire with a fresh `start_sha`.
  - **`autonomous_mode: true`**: auto-resume **once** via the same `start_sha`-preserving path (warm-`SendMessage` in agent mode, `millpy-implement.py <batch_name> --resume-incomplete` in subprocess/psmux mode). If the auto-resume yields `success`, continue normally. If it is **still** `incomplete`, set batch state → `blocked`, `blocked_reason: "incomplete after resume"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name} (incomplete after resume)"` and push, invoke the per-batch cleanup block, and go to *Blocked*.
- `verify` / `logic` → surface to user with three options: edit plan to clarify then retry fresh, skip this batch (block the task), block the task. User picks.
- On user-chosen block: set batch state → `blocked`, `blocked_reason: <reason>`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name}"`. Invoke the per-batch cleanup block. Go to *Blocked*.
```

  Replace the whole body (from the paragraph beginning "If the deep-merged config has..." through the final "On user-chosen block" bullet — keep the `### Stuck escalation` heading itself unchanged) with:

```
For any `stuck_type` (`transient` already-retried, `verify`, `logic`, `infrastructure`, `incomplete`): auto-handle according to the stuck_type rules below — mill-go never surfaces a numbered prompt and waits for an operator reply here. Each stuck_type gets its own one-shot self-resolve or auto-retry step per the rules below; on a repeat of the same failure after that one-shot attempt, the bullet's own escalation path sets batch state → `blocked`, appends the phase, commits, invokes the per-batch cleanup block, and goes to *Blocked*.

- **`infrastructure`** (bg worker died, likely logout) — auto-retry ONCE with a fresh re-fire: invoke the per-batch cleanup block, then re-invoke `millpy-bg` with a fresh CLI (no `--resume` flag — the killed session is dead). If the re-fire also reports `infrastructure`: set batch state → `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name}"`, invoke the per-batch cleanup block, and go to *Blocked*. The re-fire matches the existing `running`-state Resume (fresh start; killed session cannot be reattached).
- **CLI emits `stuck_type: transient`** (LLM-layer failure surfaced as the synthetic stuck JSON described in Implement step 2; the CLI exits 1 in that case but stdout carries the JSON) → apply the one-retry policy: re-invoke `millpy-implement.py <batch_name>` once with no `--resume` flag (a fresh session). If the second invocation also reports `stuck_type: transient`, escalate per the routing below.
- `transient` (already retried once):
  - **If `commits_made > 0` in the stuck JSON** (the implementer timed out after committing some work): skip re-invocation of the implementer; proceed directly to the per-batch cleanliness gate (scope violations check) then code review as if the implementer had reported success — commits were made before the timeout, so there is nothing left to retry.
  - **Otherwise** (no commits made, the field is absent, or the timeout happened before any commit) → self-resolve once: re-fire the implementer fresh (no `--resume`) — a first-occurrence timeout with no commits is most often a transient LLM/network hiccup, so no plan edit is needed for this attempt. If the retry ALSO reports `transient` with no commits made: set batch state → `blocked`, `blocked_reason: "transient: no commits after retry"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name}"`, invoke the per-batch cleanup block, and go to *Blocked*.
- **`incomplete`** (batch provably partial — some cards committed, not all; reached here only when the in-line recovery already ran once and the batch is still partial) — resume preserving the original `start_sha`, never retry-fresh (Shared Decisions `stuck_type: incomplete is a new first-class classification` and `resume must preserve the original start_sha`; discussion `warm-resume-mechanism`, `start-sha-preserving-resume`): auto-resume **once** via the same `start_sha`-preserving path (warm-`SendMessage` in agent mode, `millpy-implement.py <batch_name> --resume-incomplete` in subprocess/psmux mode). If the auto-resume yields `success`, continue normally. If it is **still** `incomplete`, set batch state → `blocked`, `blocked_reason: "incomplete after resume"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name} (incomplete after resume)"` and push, invoke the per-batch cleanup block, and go to *Blocked*. Never re-fire with a fresh `start_sha`.
- `verify` / `logic` (first occurrence) → self-resolve once: investigate the failure using the same judgment an implementer/fixer already applies when picking "edit plan and retry" — read the verify/review output that produced this stuck signal, edit the plan file(s) if the failure traces to an ambiguous or incorrect card, then re-fire the implementer fresh for this batch. If the retry produces the *same* `verify`/`logic` failure on this batch: set batch state → `blocked`, `blocked_reason: "verify/logic: unresolved after retry"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name}"`, invoke the per-batch cleanup block, and go to *Blocked*.
```

  Note the final "On user-chosen block" bullet from the original is intentionally NOT carried forward — its logic is now inlined into each bullet's own escalation path above (there is no more "user-chosen" block; every escalation is the agent's own decision after one self-resolve attempt).
- **Commit:** `docs(mill-go): make stuck escalation unconditionally self-resolve-then-escalate`

## Batch Tests

`verify: null` — this batch edits only `plugins/mill/skills/mill-go/SKILL.md`'s `### Stuck escalation` section, a prose file interpreted by Claude Code at skill-invocation time, not executable Python. There is no runnable test surface. Correctness is verified by plan review (byte-exact old/new text matching against the actual worktree source) and, downstream, by mill-go's code review reading the resulting diff.
