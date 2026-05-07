# Batch: Config and autonomous-mode wiring

```yaml
task: 16 (A) — Autonomous bug-fix pipeline (mill-autofix)
batch: Config and autonomous-mode wiring
number: 2
cards: 3
verify: null
depends-on: []
```

## Batch Scope

This batch makes three text-only edits: adds `pipeline.autonomous_mode: false` to `wiki/config.yaml` (bootstrap card — see Card 5 for safety rationale), and adds autonomous-mode auto-block guards to `mill-plan/SKILL.md` and `mill-go/SKILL.md`. No Python is written; the batch has no runnable verify surface. The external interface consumed by Batch 3: `pipeline.autonomous_mode` key exists in `wiki/config.yaml`, and both mill-plan and mill-go SKILL.md files contain the guard logic that mill-autofix depends on.

Batch-local decision — **autonomous-mode auto-block wording**: when `pipeline.autonomous_mode: true`, both skills set `phase: blocked` via `_status.append_phase(status_path, "blocked", ts)` and commit+push on the task branch before halting. This lets mill-autofix detect the block by reading `task/status.md` after the sub-skill returns.

## Cards

### Card 5: Add `pipeline.autonomous_mode` to `wiki/config.yaml`

- **Context:** none
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Requirements:** This is a bootstrap card. Safety rationale: `pipeline.autonomous_mode` is a brand-new key. Its absence is equivalent to `false` in every existing config reader (deep-merge returns `false` for a missing key). Zero existing Python files in `plugins/mill/scripts/` read `pipeline.autonomous_mode` (verify with `grep -r "autonomous_mode" plugins/mill/scripts/`). The consuming code — mill-autofix SKILL.md (Batch 3) and the guards in mill-plan/mill-go SKILL.md (Cards 6 and 7 below) — is shipped in this same plan. Adding the key to `wiki/config.yaml` mid-flight is safe because no code reads it until Batch 3 is deployed. Implementation: (1) resolve wiki path: `from _paths import resolve_git_root, resolve_wiki_path; wiki_path = resolve_wiki_path(resolve_git_root())`; (2) open `wiki_path / "config.yaml"`; (3) in the `pipeline:` section (currently contains `auto_merge: false` and `auto_report: true`), add `autonomous_mode: false` with an inline comment `# set to true by mill-autofix during autonomous runs; restored on cleanup`; (4) commit and push: `git -C <wiki_path> add config.yaml && git -C <wiki_path> commit -m "mill-autofix: add pipeline.autonomous_mode key" && git -C <wiki_path> push`.
- **Commit:** `feat(config): add pipeline.autonomous_mode key to wiki/config.yaml`

### Card 6: Add autonomous-mode guard to `mill-plan/SKILL.md`

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Two insertions in `plugins/mill/skills/mill-plan/SKILL.md` (Phase: Plan Review section): **Location 1 — step 5 (non-progress check):** Before the sentence "If the set is identical, halt with `BLOCKED: Plan review non-progress round {N}` and tell the user to look at the fixer reports.", insert the following block: `If the deep-merged config has `pipeline.autonomous_mode: true`: skip the user prompt; `_status.append_phase(status_path, "blocked", ts)`; write `blocked_reason: non-progress round {N}` via `_status.update_field(status_path, "blocked_reason", f"non-progress round {N}")`; commit `git -C <worktree> add task/status.md task/reviews/ && git -C <worktree> commit -m "mill-plan: blocked (autonomous-mode non-progress) for {slug}"` and push; halt with "Autonomous mode: plan blocked on non-progress at round {N}. Task left as [active] for manual review."` **Location 2 — step 6 (max-rounds escape):** Before the sentence "present the user with the prompt below verbatim", insert: `If the deep-merged config has `pipeline.autonomous_mode: true`: skip the user prompt; `_status.append_phase(status_path, "blocked", ts)`; write `blocked_reason: max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain` via `_status.update_field`; commit and push; halt with "Autonomous mode: plan blocked after {N} rounds, {M} BLOCKINGs remain. Task left as [active]."`
- **Commit:** `feat(mill-plan): add autonomous_mode auto-block at non-progress and max-rounds`

### Card 7: Add autonomous-mode guard to `mill-go/SKILL.md`

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Two insertions in `plugins/mill/skills/mill-go/SKILL.md`: **Location 1 — Stuck escalation section:** At the very top of the `### Stuck escalation` section (before the `transient` bullet), insert: `If the deep-merged config has `pipeline.autonomous_mode: true`: for any `stuck_type` (`transient` already-retried, `verify`, `logic`): skip the user prompt; set batch state → `blocked`, `blocked_reason: "autonomous-mode stuck: {stuck_type}"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; commit `git -C <worktree> add task/status.md && git -C <worktree> commit -m "mill-go: blocked on {batch_name} (autonomous-mode)"` and push; go to *Blocked*.` **Location 2 — Holistic code review, step 7 (rounds exhausted):** Before the "surface to user with a **blocked-task halt**" sentence in step 7, insert: `If the deep-merged config has `pipeline.autonomous_mode: true`: `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; `_status.update_field(status_path, "blocked_reason", f"holistic review exhausted {max_holistic_rounds} round(s) (autonomous-mode)")`; commit `git -C <worktree> add task/status.md && git -C <worktree> commit -m "mill-go: blocked on holistic review (autonomous-mode)"` and push; halt with "Autonomous mode: holistic review exhausted. Task left as [active]."`
- **Commit:** `feat(mill-go): add autonomous_mode auto-block at stuck escalation and holistic exhaustion`

## Batch Tests

Verify: null. This batch edits Markdown/YAML only — no runnable surface. Correctness is verified by Plan Review (the reviewer inspects the exact text inserted against the discussion's specification) and by integration testing when mill-autofix runs against a real bug.
