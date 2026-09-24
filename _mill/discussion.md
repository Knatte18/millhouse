# Discussion: Entry-gate wait: drop nonexistent Monitor persistent:true

```yaml
task: 'Entry-gate wait: drop nonexistent Monitor persistent:true'
slug: monitor-persistent-entry-wait
status: discussing
parent: main
```

## Problem

Issues #1140, #1141 and #1149 report that mill-plan's and mill-go-base's entry-gate waits told the orchestrator to call `Monitor` with `persistent: true`.
The harness `Monitor` tool has no such parameter and caps `timeout_ms` at 1800000 (30 minutes), well below the default `pipeline.entry_wait_timeout_minutes` of 240.

Commit `f6966798` (already on `main`, and in this branch's history) fixed the two named sections.
`mill-plan/SKILL.md` "Entry-gate wait for upstream mill-start" and `mill-go-base/SKILL.md` "Entry-gate wait for upstream mill-plan" now call `Monitor(command=cmd, timeout_ms: 1800000, ...)`, record `wait_started_epoch`, and re-arm on an event-less expiry using the remaining budget.
`plugins/mill/docs/harness-tool-contracts.md` documents the same contract.

What remains is the same defect in two sibling skills that copy the idiom.
Both still say "persistent bash poll" and give no re-arm rule, so a wait past 30 minutes silently ends early:

- `plugins/mill/skills/orch-wait/SKILL.md` line 19 (Step 2, waits for `_mill/orch-review.md`).
- `plugins/mill/skills/orch-review/SKILL.md` line 34 (Step 2, waits for `_mill/discussion.md` per slug).

## Scope

**In:**
- Rewrite the wait idiom in `orch-wait` Step 2 and `orch-review` Step 2: drop "persistent", arm `Monitor` with `timeout_ms: 1800000`, and add the wall-clock re-arm rule for an event-less expiry.
- Cross-reference `plugins/mill/docs/harness-tool-contracts.md` from both.
- Update `harness-tool-contracts.md` so every consumer reference includes the two orch skills: the intro at line 3 ("Four skill files already carry inline copies"), the re-arm sentence at line 26 and line 35, and the consumers line at line 37.

**Out:**
- `mill-plan` and `mill-go-base` entry-gate sections: already fixed by `f6966798`; do not touch.
- `_phase_wait.py` and `build_wait_command` (no change to the status-phase poller).
- The `persistent` hits in `mill-setup/SKILL.md`, `_subprocess_util.py`, `_winenv.py`, `wiki/_client.py`: unrelated meanings of the word.
- Changing the default `entry_wait_timeout_minutes` or the config template.

## Decisions

### Re-arm rather than persistent

- Decision: each orch wait uses `Monitor(command=..., timeout_ms: 1800000, description=...)`, records `wait_started_epoch` once via `date +%s`, and on an event-less expiry recomputes `remaining_s = giveup_s - (now - wait_started_epoch)`.
  If `remaining_s <= 0` it takes the existing timeout branch, otherwise it re-arms with a poll script bounded by `remaining_s`.
  For `orch-review`, which arms several concurrent waits, `wait_started_epoch` and `task_id` are tracked per slug, and each slug re-arms independently.
- Rationale: identical to the already-merged mill-plan/mill-go-base design; no `Monitor` build holds a wait open indefinitely.
- Rejected: a detached background `Bash` run (one uncapped notification, per #1141) — diverges from the documented `Monitor` contract and from the two sibling sections.

### Reference, don't duplicate

- Decision: the orch skills say "same re-arm rule as `mill-go-base/SKILL.md`'s `Entry-gate wait for upstream mill-plan`" and state only what differs (the file-exists poll condition, per-slug `task_id` for `orch-review`).
- Rationale: a single canonical write-up avoids a third and fourth copy that can drift.
- Rejected: pasting the full branch-on-`<event>` text into both skills.

### File-exists poll script

- Decision: the poll is an inline bash loop (`until [ -f <path> ] ...`, 30 s interval, echo `READY` or `TIMEOUT after <N>s`, bounded by `giveup_s`), since `build_wait_command` only polls `status.md` phases.
- Rationale: keeps event vocabulary (`READY` / `TIMEOUT after ...`) identical to the other waits, so the same branch logic applies.
- Rejected: extending `_phase_wait` with a file-exists mode (scope creep; code change for a docs defect).

## Technical context

- Reference implementation to mirror: `plugins/mill/skills/mill-plan/SKILL.md` lines ~101-117 and `plugins/mill/skills/mill-go-base/SKILL.md` lines ~207-222.
- `plugins/mill/docs/harness-tool-contracts.md` "Monitor tool" section is the canonical contract; it already states the two-notification shape and the re-arm rule.
- `plugins/mill/unit_tests/test-orch-review-mill-path.py` asserts both orch skills reference `_mill/orch-review.md`; keep those path strings intact.
- `SKILLS.md` at the repo root indexes skill frontmatter descriptions only; no change needed unless a description is edited (do not edit them).
- Per CLAUDE.md, verify the source text in this task worktree, not the plugin cache.

## Constraints

- Never use `sed`; use Edit/Write.
- Semantic line breaks in edited markdown.
- Plan `verify:` commands for Python tests must start with `PYTHONPATH=`.

## Testing

- Docs-only change; no TDD candidates.
- Run `plugins/mill/unit_tests/test-orch-review-mill-path.py` (via `run-all.py` or `uv run --project plugins/mill`) to confirm the path assertions still pass.
- Grep check: no remaining `persistent` in `orch-wait/SKILL.md`, `orch-review/SKILL.md`, `mill-plan/SKILL.md`, `mill-go-base/SKILL.md` referring to Monitor.

## Q&A log

- **Q:** Is the reported defect still present in mill-plan and mill-go-base? **A:** [auto-pick] No; already fixed by `f6966798`, so scope narrows to the orch skills. **Why:** grep shows those sections now use `timeout_ms: 1800000` plus re-arm; only `orch-wait` and `orch-review` still say "persistent".
- **Q:** How should the orch skills express the re-arm rule? **A:** [auto-pick] Reference `mill-go-base`'s section and state only the differences. **Why:** avoids further copies of a long paragraph.
- **Q:** Extend `_phase_wait` with a file-exists mode? **A:** [auto-pick] No; inline bash loop. **Why:** docs-only fix, no new code surface.
