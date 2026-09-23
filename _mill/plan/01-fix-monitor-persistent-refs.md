# Batch: fix-monitor-persistent-refs

```yaml
task: 'Monitor tool: persistent:true still referenced in mill-go-base and mill-plan despite no such param'
batch: fix-monitor-persistent-refs
number: 1
cards: 3
verify: null
depends-on: []
```

## Batch Scope

This batch corrects the three files that still assert or rely on a `Monitor` tool `persistent: true` parameter, which does not exist in the tool's real schema (confirmed live during discussion, per `_mill/discussion.md`'s Problem section). Two `SKILL.md` files' entry-gate wait sections swap `persistent: true` for an explicit `timeout_ms: 1800000` and reframe their re-arm branch as the expected path rather than an edge case; the third file, `harness-tool-contracts.md`, is the "canonical write-up" both sections cite for this contract and currently asserts the opposite (that `persistent` was reconfirmed to exist), so it is corrected to match. All three cards are independent edits to independent files with no shared code path and no ordering requirement between them; they are grouped in one batch because they are the same fix applied to the same false premise across the doc family, not because any one depends on another. No external interface changes — this batch has no downstream consumer within this plan (it is the plan's only batch).

## Cards

### Card 1: Fix mill-go-base/SKILL.md's Monitor call to use timeout_ms instead of persistent:true

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the "### Entry-gate wait for upstream mill-plan" section:

  1. Find the bullet that begins "Call the `Monitor` tool with `command=cmd`, `persistent: true`, `description` naming the slug..." — it runs two sentences, the second beginning "Do not set a `timeout_ms` value distinct from the default...". Replace both sentences (the whole bullet) with:

     > - Call the `Monitor` tool with `command=cmd`, `timeout_ms: 1800000` (the tool's effective cap — no `Monitor` build holds a wait open indefinitely), `description` naming the slug and the target phase (e.g. "waiting for phase: planned (mill-plan handoff) for `<slug>`"), matching the existing "Waiting is never a decision point" convention already documented for Agent-mode dispatch elsewhere in this file: state what is being waited for, then wait, with no `AskUserQuestion` or free-text prompt in between.

  2. In the same section, find the bullet beginning "**Any other notification content**" (the one that recomputes `remaining_s` and rebuilds `cmd` for "planned"). Replace its full text with:

     > - **Any other notification content** (an <event> that is neither `READY` nor a `TIMEOUT after ...` line — e.g. a "Monitor expired after Nm with no events delivered..." notice) — the `Monitor` tool's own `timeout_ms` cap expiring with the poll script still running. This is the expected, normal outcome for any wait whose configured `giveup_s` exceeds 1800s, not an edge case: no `Monitor` build holds a wait open indefinitely, so a wait longer than 30 minutes re-arms at least once. Run `date +%s` again and compute `remaining_s = giveup_s - (<this reading> - wait_started_epoch)`. If `remaining_s <= 0`: treat exactly like the `TIMEOUT after <N>s` branch above — halt with the same give-up message. Otherwise: rebuild `cmd = _phase_wait.build_wait_command(status_path, "planned", 10, remaining_s)` and re-issue `Monitor(command=cmd, timeout_ms: 1800000, description=...)`, recording the newly returned `task_id` in place of the old one, then resume waiting for the next <task-notification>. This is a re-arm of the same wait — it does not re-run this Entry phase gate step; only `READY` does that.

  3. Do not change anything else in this section — the `READY` branch, the `TIMEOUT after <N>s` branch, the `wait_started_epoch` recording bullet, and the harness-level stop/interrupt bullet are all unaffected and stay exactly as written.
- **Commit:** `docs(mill-go-base): replace Monitor persistent:true with timeout_ms cap in entry-gate wait`

### Card 2: Fix mill-plan/SKILL.md's Monitor call to use timeout_ms instead of persistent:true

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the "### Entry-gate wait for upstream mill-start" section:

  1. Find the bullet that begins "Call the `Monitor` tool with `command=cmd`, `persistent: true`, `description` naming the slug..." followed by "Do not set a `timeout_ms` value distinct from the default — `persistent: true` makes it irrelevant." and a further continuation sentence starting "This is never a decision point...". Replace the whole bullet (all its lines) with:

     > - Call the `Monitor` tool with `command=cmd`, `timeout_ms: 1800000` (the tool's effective cap — no `Monitor` build holds a wait open indefinitely), `description` naming the slug and the target phase (e.g. "waiting for phase: discussed (mill-start handoff) for `<slug>`").
     >   This is never a decision point: state what is being waited for, then wait, with no `AskUserQuestion` or free-text prompt in between (mill-plan is autonomous outside its own documented escape hatches;
     >   this wait introduces no new one).

  2. In the same section, find the bullet beginning "**Any other notification content**" (the one that recomputes `remaining_s` and rebuilds `cmd` for "discussed", including `clean_tree_root`/`clean_tree_paths`). Replace its full text with:

     > - **Any other notification content** (an <event> that is neither `READY` nor a `TIMEOUT after ...` line — e.g. a "Monitor expired after Nm with no events delivered..." notice) — the `Monitor` tool's own `timeout_ms` cap expiring with the poll script still running. This is the expected, normal outcome for any wait whose configured `giveup_s` exceeds 1800s, not an edge case: no `Monitor` build holds a wait open indefinitely, so a wait longer than 30 minutes re-arms at least once. Run `date +%s` again and compute `remaining_s = giveup_s - (<this reading> - wait_started_epoch)`. If `remaining_s <= 0`: treat exactly like the `TIMEOUT after <N>s` branch above — halt with the same give-up message. Otherwise: rebuild `cmd = _phase_wait.build_wait_command(status_path, "discussed", 10, remaining_s, clean_tree_root=git_root, clean_tree_paths=[status_path, discussion_path])` and re-issue `Monitor(command=cmd, timeout_ms: 1800000, description=...)`, recording the newly returned `task_id` in place of the old one, then resume waiting for the next <task-notification>. This is a re-arm of the same wait — it does not re-run Entry step 4's phase-table evaluation; only `READY` does that.

  3. Do not change anything else in this section.
- **Commit:** `docs(mill-plan): replace Monitor persistent:true with timeout_ms cap in entry-gate wait`

### Card 3: Correct harness-tool-contracts.md's Monitor tool schema claim

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Read cards 1 and 2's now-updated `plugins/mill/skills/mill-go-base/SKILL.md` and `plugins/mill/skills/mill-plan/SKILL.md` (listed in Context: above) so this card's wording stays consistent with the design those two cards just landed. In the "## Monitor tool" section of `plugins/mill/docs/harness-tool-contracts.md`:

  1. Find the section's opening paragraph, beginning "The `Monitor` tool schema was directly reconfirmed via a live tool-schema read on 2026-09-21...". Replace the entire paragraph with:

     > The `Monitor` tool schema was directly reconfirmed via a live tool-schema read on 2026-09-23 (the same verification `_mill/discussion.md`'s Problem section records, for the task that corrected this section): parameters `command`/`ws`, `description`, `timeout_ms` (number, default `300000`, JSON `maximum: 3600000`, but the tool's own description states deadlines above `1800000` are capped to `1800000` — treat `1800000` as the real ceiling). There is no `persistent` parameter. This confirms the "no `persistent` parameter" claim common to ten independent field reports — GitHub issues #1058, #1062, #1066, #1067, #1078, #1085, #1088, #1096, #1100, #1108 — and supersedes this section's own prior claim (from an earlier, since-disproven 2026-09-21 read) that `persistent` existed; the two entry-gate wait sections cited at the bottom of this section now document the resulting design: every wait re-arms at least once whenever its configured `giveup_s` exceeds 1800s, since no `Monitor` build holds a wait open indefinitely.

  2. Find the line "A poll script run via `Monitor(command: ..., persistent: true, ...)`:" and replace it with:

     > A poll script run via `Monitor(command: ..., timeout_ms: 1800000, ...)`:

  3. Find the bullet beginning "An early, unrequested expiry (a notification whose <event> content is neither `READY` nor a `TIMEOUT after ...` line) is possible on a `Monitor` build where `persistent: true` does not hold the watch open for the full wait...". Replace it with:

     > - An expiry with no `<event>` content (a notification whose payload is neither `READY` nor a `TIMEOUT after ...` line) fires whenever the poll script is still running when `Monitor`'s `timeout_ms` cap is reached — expected for any wait exceeding 30 minutes, not build-specific. Both entry-gate wait sections below re-arm on this outcome, recomputing the remaining budget from wall-clock elapsed time rather than restarting it.

  4. Do not change the rest of the section: the two-notification-shape bullets (per-line event notification, then a separate terminal `<status>completed</status>` notification) and the final "See `mill-go-base/SKILL.md`'s..." cross-reference line are unaffected and stay accurate as written.
- **Commit:** `docs(harness-tool-contracts): correct Monitor schema -- no persistent param, 1800000ms cap`

## Batch Tests

`verify: null` — this batch edits three markdown documentation files (`SKILL.md` prose and a docs file) with no runnable code surface and no Python entry point. Verification is inspection-based: after the edits land, `grep -rn "persistent: true" plugins/mill/` must return no results, and `grep -rn "persistent" plugins/mill/docs/harness-tool-contracts.md` must no longer assert the parameter exists.
