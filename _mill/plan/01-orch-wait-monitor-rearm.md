# Batch: orch-wait-monitor-rearm

```yaml
task: 'Entry-gate wait: drop nonexistent Monitor persistent:true'
batch: 'orch-wait-monitor-rearm'
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-orch-review-mill-path.py
depends-on: []
```

## Batch Scope

Rewrites the wait step of the two orch skills to the `Monitor(..., timeout_ms: 1800000)` plus wall-clock re-arm design already merged for the mill-plan and mill-go-base entry-gate waits, and updates the harness contract doc so its consumer references cover the orch skills.
One batch: three small markdown edits sharing the same reference material and the same verify test.
No batch-local decisions differ from `## Shared Decisions`.

## Cards

### Card 1: orch-wait Step 2 uses Monitor with timeout_ms and re-arm

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/skills/orch-wait/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rewrite the first paragraph of `## Step 2 — Blocking wait for the file` in `orch-wait/SKILL.md`; leave its second paragraph (the `On timeout:` block) and every other step unchanged, and keep the string `_mill/orch-review.md` present in the file.
  The rewritten paragraph must state, in semantic line breaks (one sentence per line):
  - The wait uses the `Monitor` tool as in the "Entry-gate wait for upstream mill-plan" section of `mill-go-base/SKILL.md`, called as `Monitor(command=cmd, timeout_ms: 1800000, description=...)`; the word "persistent" no longer appears in the file.
  - `giveup_s` is `pipeline.entry_wait_timeout_minutes * 60`, read from config the same way that `mill-go-base` section does (default 240 when absent), not hardcoded.
  - Before the first arm, record `wait_started_epoch` from `date +%s` once, and record the `task_id` the `Monitor` call returns.
  - `cmd` is this inline file-exists poll, with `<orch_review_path>` being the orch-review file under `<worktree_root>/_mill/` and `<giveup_s>` substituted:
    ```bash
    elapsed=0
    while true; do
      if [ -f "<orch_review_path>" ]; then
        echo "READY"
        exit 0
      fi
      if [ "$elapsed" -ge <giveup_s> ]; then
        echo "TIMEOUT after ${elapsed}s waiting for orch-review.md"
        exit 2
      fi
      sleep 30
      elapsed=$((elapsed + 30))
    done
    ```
  - Branch on the `<event>` content with the same rules as the `mill-go-base` section: `READY` continues to Step 3; a `TIMEOUT after <N>s ...` line takes the existing `On timeout:` block below; any other event content is an unexpected early expiry, handled by running `date +%s`, computing `remaining_s = giveup_s - (now - wait_started_epoch)`, taking the `On timeout:` block when `remaining_s <= 0`, and otherwise re-issuing the same `Monitor` call with the poll script's `<giveup_s>` replaced by `remaining_s`, recording the new `task_id`, and waiting again.
  - The second, event-less `<status>completed</status>` notification needs no branch; refer to `plugins/mill/docs/harness-tool-contracts.md` for the two-notification contract.
- **Commit:** `docs(orch-wait): arm Monitor with timeout_ms and re-arm on expiry instead of persistent`

### Card 2: orch-review Step 2 uses Monitor with timeout_ms and per-slug re-arm

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/docs/harness-tool-contracts.md`
  - `plugins/mill/skills/orch-wait/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/orch-review/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rewrite the first paragraph of `### Step 2 — Arm a \`Monitor\` wait per slug, in this session` in `orch-review/SKILL.md` (the paragraph beginning "For each remaining slug"); leave the fenced "Tell the user once" block, `### Step 3`, and every other section unchanged.
  Apply the same wording rules as card 1's requirements: semantic line breaks, and no "persistent" left in the file.
  The rewritten paragraph must state:
  - Each slug's wait is armed in this session via `Monitor(command=cmd, timeout_ms: 1800000, description=...)`, where `cmd` is the same inline file-exists poll `orch-wait` Step 2 gives, polling `<worktree>/_mill/discussion.md` for that slug (30-second interval, echoing `READY` or `TIMEOUT after <N>s ...`).
  - `giveup_s` is read from `pipeline.entry_wait_timeout_minutes` exactly as `orch-wait` reads it, not hardcoded.
  - `wait_started_epoch` (from `date +%s`, recorded once per slug before that slug's first arm) and `task_id` are tracked per slug, so each slug's expiry is handled independently.
  - On an event-less expiry for a slug, the orchestrator recomputes that slug's `remaining_s = giveup_s - (now - wait_started_epoch)`; `remaining_s <= 0` takes the existing timeout branch in Step 3, otherwise it re-arms that slug's `Monitor` with the poll bounded by `remaining_s` and records the new `task_id`.
  - The remaining `<event>` branching (`READY`, `TIMEOUT after ...`) follows the "Entry-gate wait for upstream mill-plan" section of `mill-go-base/SKILL.md`, with `plugins/mill/docs/harness-tool-contracts.md` cited for the two-notification shape.
  - All slugs' waits are still armed before ending the turn so they run concurrently.
  Additionally, in `### Step 3 — On each slug's trigger: timeout, or fork`, change the sentence "When a given slug's `Monitor` wait fires:" so it reads that the branches apply when a slug's wait delivers a `READY` or `TIMEOUT after ...` event (an event-less expiry is re-armed per Step 2 and never reaches this step).
- **Commit:** `docs(orch-review): arm Monitor with timeout_ms and per-slug re-arm instead of persistent`

### Card 3: harness-tool-contracts consumer references include the orch skills

- **Context:**
  - `plugins/mill/skills/orch-wait/SKILL.md`
  - `plugins/mill/skills/orch-review/SKILL.md`
- **Edits:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `harness-tool-contracts.md`, update every place that enumerates the entry-gate consumers so it also covers the two orch skills, keeping all other text unchanged:
  - The intro sentence "Four skill files already carry inline copies of this material" becomes "Six skill files", and the count stays accurate.
  - The re-arm sentence in the `## Monitor tool` section's schema-confirmation paragraph, currently ending "the two entry-gate wait sections cited at the bottom of this section now document the resulting design", names all four wait sections (the two entry-gate sections plus the `orch-wait` Step 2 wait and the `orch-review` Step 2 wait) instead of "the two entry-gate wait sections".
  - The last bullet of the Monitor tool bullet list (the expiry bullet ending "Both entry-gate wait sections below re-arm on this outcome") says all four wait sections re-arm.
  - The closing "See ..." line lists four consumers: the `mill-go-base` entry-gate section, the `mill-plan` entry-gate section, `orch-wait` Step 2, and `orch-review` Step 2 (with `orch-review` tracking `wait_started_epoch` and `task_id` per slug), replacing "two independent consumers".
  Use semantic line breaks in every new or reworded sentence.
- **Commit:** `docs(harness-tool-contracts): list orch-wait and orch-review as Monitor wait consumers`

## Batch Tests

`verify:` runs `test-orch-review-mill-path.py` via `run-all.py --only`, which asserts both edited skill files still contain `_mill/orch-review.md` and no stale `.scratch/orch-review.md`.
The batch is markdown-only, so that is the only runnable surface.
Manual grep check after implementation: no line mentioning `persistent` remains in `orch-wait/SKILL.md`, `orch-review/SKILL.md`, `mill-plan/SKILL.md`, or `mill-go-base/SKILL.md` in connection with `Monitor`.
