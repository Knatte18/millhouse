# Discussion: mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references

```yaml
task: mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references
slug: mill-go-skilldoc-accuracy-gaps
status: discussing
parent: main
```

## Problem

A cluster of four confirmed SKILL.md accuracy gaps in `mill-go/SKILL.md` and `mill-plan/SKILL.md`, each backed by a closed GitHub issue with a live incident:

- **#810**: `mill-go/SKILL.md`'s holistic-review "ERROR-only-aggregate retry" halt (step 3.5) and its rate-limit-fallback-exhausted halts (step 3.6) tell the orchestrator to "halt with BLOCKED: ..." but never document the actual state-mutation sequence (status/commit/notify/lock-release), unlike every sibling escalation branch in the same file. An operator hit this live on task `plan-format-drop-v3-suffix` and had to improvise by copying the generic `### Blocked` section's pattern.
- **#809**: `mill-go/SKILL.md`'s holistic step 7 ("Rounds exhausted") calls `_status.update_field(status_path, "blocked_reason", ...)`, which raises `ValueError` the first time a task is ever blocked, because `update_field` requires the key to already exist. The correct helper, `_status.set_blocked`, already exists and is used elsewhere for exactly this purpose. Hit live on the same task.
- **#792**: `mill-go/SKILL.md`'s "0.5. Baseline pre-flight" step (`--stage baseline`) lacks the extended 600000ms Bash-tool timeout note that its three sibling call sites (verify-replay-heavy, potentially-slow commands) all carry. Hit live: a 300000ms timeout wasn't enough and the call hit "Exit code 143 / Command timed out after 5m 0s".
- **#806**: `mill-plan/SKILL.md` has 6 literal `plugins/mill/...`-rooted cross-references to other skill files/docs that don't resolve in a consuming repo (the plugin lives under a versioned cache path there, not at a `plugins/mill/` repo-relative path). An operator hit this live in the `loomyard` repo and it caused a `cd`-into-cache cwd corruption cascade.

All four are pure documentation-accuracy fixes to `SKILL.md` prose — no application/script code changes.

## Scope

**In:**
- `plugins/mill/skills/mill-go/SKILL.md`: add explicit mutation sequences to holistic steps 3.5 and 3.6's halt branches (#810).
- `plugins/mill/skills/mill-go/SKILL.md`: swap the broken `_status.update_field(..., "blocked_reason", ...)` call in holistic step 7 for `_status.set_blocked(...)` (#809).
- `plugins/mill/skills/mill-go/SKILL.md`: add an extended-timeout note to "0.5. Baseline pre-flight" (#792).
- `plugins/mill/skills/mill-plan/SKILL.md`: convert 6 non-portable `plugins/mill/...` cross-references to skill-base-relative form (#806).

**Out:**
- `plugins/mill/skills/mill-start/SKILL.md:276` has the identical `#806`-shaped bug (`plugins/mill/skills/mill-receiving-review/SKILL.md` literal path) but is **not** in scope — it's a different file, not named in this task's source issues.
- The `plugins/mill/templates/...`, `plugins/mill/unit_tests/...`, and `plugins/mill/.claude-plugin/plugin.json` references elsewhere in `mill-plan/SKILL.md` (lines 166, 171, 195, 196, 317, 319) are **not** touched — those are legitimate repo-relative paths used inside `verify:` commands / render instructions that execute from `git_root` in this self-hosting repo, not orchestrator-navigation cross-references.
- Step 7's missing `_notify.notify`/builder-lock-release (present in `### Blocked` but absent from step 7) is **not** added — #809 only reported the `ValueError` precondition bug, not a missing-notification gap.
- No application/script code changes (`_status.py` etc.) — the bug is in the documented call site, not the helper itself.
- No changes to `_status.py`'s `update_field` behavior (e.g. making it upsert) — the discussion favors fixing the SKILL.md call site to use the already-correct `set_blocked` helper instead.

## Decisions

### scope-boundary

- Decision: Fix exactly the 4 named issues (#810, #809, #792, #806) in `mill-go/SKILL.md` and `mill-plan/SKILL.md` only. Do not touch `mill-start/SKILL.md:276`, even though it shares #806's exact defect pattern.
- Rationale: the task brief explicitly scopes to "mill-go/mill-plan SKILL.md" gaps; `mill-start` is a different file with its own task lineage. Fixing it here would be uncoordinated scope creep into another skill's doc surface, and its fix would need to be independently verified against mill-start's own conventions.
- Rejected: bundling the mill-start:276 fix into this task — rejected to keep this task's diff auditable 1:1 against its 4 source issues; flag it as a follow-up candidate instead.

### 810-mutation-sequence

- Decision: Add explicit state mutation to `mill-go/SKILL.md` before each of steps 3.5's and 3.6's `halt with BLOCKED: ...` sentences, using `_status.set_blocked` (not the two-call `append_phase`+`update_field` pattern), followed by commit, invoking the holistic cleanup block, `_notify.notify("mill-go.blocked", ...)`, and builder-lock release — mirroring the generic `### Blocked` section (lines 853–862) and the sibling holistic escalation branches (lines 1187, 1190, 1195) that already spell this out for their own halts.

  Current text (step 3.5, line 1127): `If sub-step 3.6 does NOT apply, halt with `BLOCKED: holistic code review ERROR-only round {H}` and surface each entry's `error` string from `reviews[]` to the user.` (preceded by line 1126: `On the **second** consecutive run that still has top-level `verdict: "ERROR"`, **first check rate-limit fallback** (see sub-step 3.6 below).`)

  New text to insert immediately before that halt sentence:
  ```
  Before halting: `_status.set_blocked(status_path, f"holistic code review ERROR-only round {H}", timestamp=_timestamp.now_utc_iso())`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review (ERROR-only round {H})"` and push; invoke the holistic cleanup block; `_notify.notify("mill-go.blocked", f"holistic review: ERROR-only round {H}", slug=slug)`; release the builder lock (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release`).
  ```
  Then the existing `halt with BLOCKED: holistic code review ERROR-only round {H} and surface each entry's error string from reviews[] to the user` sentence follows unchanged.

  Current text (step 3.6, line 1146): `If the fallback reviewer ALSO returns `verdict: ERROR` on its first pass: halt with `BLOCKED: holistic code review fallback also failed at round {H}` and surface every `reviews[*].error` from BOTH the original and fallback attempts. Do NOT cascade to a second fallback.`

  New text to insert before that halt: the identical mutation-sequence shape as above, with `blocked_reason` = `f"holistic code review fallback also failed at round {H}"` and the commit message `"mill-go: blocked on holistic review (fallback also failed at round {H})"`.

  Current text (step 3.6, line 1148): `If `fallback_reviewer is None` AND a rate-limit was detected on both 3.5 passes: halt with `BLOCKED: holistic rate-limited, no fallback_reviewer configured`. The operator-visible message is intentional -- silent infinite fallback is wrong.`

  New text to insert before that halt: the identical mutation-sequence shape, with `blocked_reason` = `"holistic rate-limited, no fallback_reviewer configured"` and the commit message `"mill-go: blocked on holistic review (rate-limited, no fallback)"`.

- Rationale: matches how every other holistic escalation branch in the same file (1187/1190/1195) already documents a full mutation sequence before halting; #810 reported exactly this gap, and the issue's own suggested fix names this sequence explicitly ("add the same explicit state-mutation sequence ... to step 3.5's halt branch, and to the corresponding 3.6 rate-limit-fallback-exhausted halts").
- Rejected: leaving the mutation sequence unstated and relying on operator improvisation (status quo — this is literally what #810 reported going wrong).
- Rejected: using the two-call `append_phase`+`update_field` pattern (matching 1187/1190/1195's literal wording) instead of `set_blocked` — rejected because `update_field` provably raises `ValueError` on a first-ever block (#809); specifying it here would import the #809 bug into three new call sites instead of fixing it.

### 809-set_blocked-swap

- Decision: In `mill-go/SKILL.md` holistic step 7 "Rounds exhausted" (lines 1200–1201), replace:
  ```
  `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`;
  `_status.update_field(status_path, "blocked_reason", f"holistic review exhausted {max_holistic_rounds} round(s)")`;
  ```
  with a single call:
  ```
  `_status.set_blocked(status_path, f"holistic review exhausted {max_holistic_rounds} round(s)", timestamp=_timestamp.now_utc_iso())`;
  ```
  The rest of step 7 (commit, push, invoke the holistic cleanup block, halt message) is unchanged — `set_blocked` already performs the `phase: blocked` overwrite and timeline-row append that `append_phase` used to do, so no separate `append_phase` call remains.
- Rationale: `_status.update_field` (`plugins/mill/scripts/_status.py:203-238`) is strict-key — it raises `ValueError: Key 'blocked_reason' not found in yaml block` when the task has never been blocked before, since `blocked_reason:` doesn't exist yet in `status.md`'s yaml block on a task blocked for the first time. `_status.set_blocked` (`_status.py:241`) is the already-correct atomic helper — it upserts `phase:`, upserts `blocked_reason:` (insert-or-update), and appends the timeline row in one call — and is already the established pattern at 5+ other call sites: `mill-merge/SKILL.md:81`, `mill-quick/SKILL.md:143`, `mill-start/SKILL.md:52` and `:315`, `mill-plan/SKILL.md:477` and `:484`.
- Rejected: making `_status.update_field` itself upsert instead (issue #809's alternative suggestion) — rejected because that changes shared script behavior relied on by other call sites (e.g. `mill-plan/SKILL.md:252`'s `plan` pointer update, which intentionally requires the key to pre-exist), which is out of scope for a doc-accuracy fix and risks masking future genuine "field should already exist" bugs at those other call sites.
- Rejected: broadening step 7 to also add `_notify.notify`/lock-release (matching `### Blocked` fully) — rejected per the scope-boundary decision; #809 reported only the `ValueError` precondition bug.

### 792-timeout-note

- Decision: Add a timeout note to `mill-go/SKILL.md`'s "0.5. Baseline pre-flight" section, placed immediately after its final sentence (currently ending "...Skip this step entirely for every batch after the first." at line 483) and before the "### 0.6. Per-batch baseline recapture" heading:
  ```
  Give this Bash-tool call the same extended 600000ms (10-minute) timeout recommended for finalize-stage verify replays above: `--stage baseline`'s `per_batch` substage replays every batch's `verify:` command to seed `verify_baseline_failures`, which is an arbitrary, potentially slow project command with no bound on runtime, sharing the identical default-2-minute-Bash-timeout risk that motivated the original finalize-stage-CLI fix.
  ```
- Rationale: reuses the established lead sentence verbatim (matching line 456 and line 1314's sibling notes word-for-word: "Give this Bash-tool call the same extended 600000ms (10-minute) timeout recommended for finalize-stage verify replays above:"), while adapting only the rationale clause to what 0.5 actually replays (`--stage baseline`'s per-batch verify commands, per its own documented behavior at lines 478–480), rather than the `done_gate`/`gate_cmd` rationale the two other siblings use — 0.5 doesn't invoke `done_gate`, so copying that clause verbatim would misdescribe the risk. #792 was hit live: an explicit 300000ms timeout on this exact call still hit "Exit code 143 / Command timed out after 5m 0s".
- Rejected: copying sibling wording 100% verbatim including the `done_gate`/`gate_cmd`-specific rationale clause — rejected as factually wrong for 0.5, which has no `gate_cmd` involved.
- Rejected: placing the note earlier in the section (e.g. right after the `millpy-implement.py --stage baseline` code block at line 474) — rejected in favor of matching the sibling notes' placement convention, which puts the timeout note as its own paragraph at the end of the relevant step, after the parsing/logging prose.

### 806-portable-cross-refs

- Decision: In `mill-plan/SKILL.md`, replace all 6 non-portable `plugins/mill/...` cross-references with skill-base-relative forms:
  | Line | Current | Replacement |
  |---|---|---|
  | 94 | `plugins/mill/docs/harness-tool-contracts.md` | `../../docs/harness-tool-contracts.md` |
  | 118 | `plugins/mill/skills/mill-go/SKILL.md` | `mill-go/SKILL.md` |
  | 347 | `plugins/mill/skills/mill-go/SKILL.md` | `mill-go/SKILL.md` |
  | 366 | `plugins/mill/skills/mill-go/SKILL.md` | `mill-go/SKILL.md` |
  | 402 | `plugins/mill/skills/mill-receiving-review/SKILL.md` | `mill-receiving-review/SKILL.md` |
  | 432 | `plugins/mill/skills/mill-go/SKILL.md` | `mill-go/SKILL.md` |

  Each replacement is a like-for-like substring swap inside its existing sentence — the surrounding prose (backtick-quoting, section-name suffixes like `'s "## Agent-mode dispatch" section`) is unchanged.

  Do **not** touch the `plugins/mill/templates/...` (lines 166, 171), `plugins/mill/unit_tests/...` (lines 195, 196), or `plugins/mill/.claude-plugin/plugin.json` (line 319) references, or the `plugins/mill/templates/plan-batch.md` mention at line 317 — those are legitimate repo-relative paths used inside `verify:` commands and render/file-creation instructions that execute from `git_root` in this self-hosting millhouse repo, not orchestrator-navigation cross-references into another skill's doc.

- Rationale: `mill-go/SKILL.md` (bare, sibling-relative) is already the established convention for this exact reference — it's used at `mill-plan/SKILL.md:381` (in the very same file, describing the very same "## Agent-mode dispatch" section) and throughout `mill-start/SKILL.md` (e.g. lines 177, 239, 249, 274, 288, 290, 317). The harness injects a "Base directory for this skill" path when a skill loads (observed live at this session's own invocation: `Base directory for this skill: .../plugins/mill/skills/mill-start`), so a sibling-relative reference like `mill-go/SKILL.md` resolves correctly under any skill's base directory (`.../skills/<other-skill>/SKILL.md`) regardless of whether that base directory is a plugin cache path or a dev-tree path — this is exactly what makes the existing line-381 precedent portable already. The docs file isn't under `skills/`, so it needs one more `../` hop: from `plugins/mill/skills/mill-plan/` up two levels reaches `plugins/mill/`, then into `docs/harness-tool-contracts.md`.
- Rejected: leaving `plugins/mill/docs/harness-tool-contracts.md` untouched and fixing only skill-to-skill refs — rejected because #806 explicitly names the docs reference as one of the broken sites ("similar `plugins/mill/...` paths appear ... in the `plugins/mill/docs/harness-tool-contracts.md` reference"), and the same root cause (repo-root-anchored path, valid only in the millhouse dev tree) applies to it.
- Rejected: routing these through `${CLAUDE_PLUGIN_ROOT}`-prefixed paths instead — rejected because these are prose cross-references for the orchestrator to *read* (open a file / jump to a heading while reasoning), not Bash commands to *execute*; `${CLAUDE_PLUGIN_ROOT}` is an environment variable meaningful only inside an actual Bash tool call, not inside prose describing which file/section to consult.

## Technical context

Both files are large (`mill-go/SKILL.md` is 1387 lines; `mill-plan/SKILL.md` is 500+ lines) — mill-plan should use `Grep`/targeted `Read` with `offset`/`limit` rather than reading either file in full, since a single unbounded `Read` truncates at the tool's page cap on `mill-go/SKILL.md`.

- `_status.py` (`plugins/mill/scripts/_status.py`):
  - `update_field(status_path, key, value)` at line 203 — strict-key rewrite; raises `ValueError` if `key` isn't already present in the yaml block. Docstring at lines 204-223 states this explicitly.
  - `set_blocked(status_path, reason, *, timestamp)` at line 241 — atomic: overwrites `phase: blocked`, upserts `blocked_reason:` (insert-or-update), appends a `blocked '<ts>'` timeline row. Docstring at lines 242-268.
  - `append_phase(status_path, phase, timestamp)` at line 425 — appends a phase/timeline row; does not touch `blocked_reason`.
- `mill-go/SKILL.md` section map relevant to this task:
  - `### Blocked` (lines 853-862) — the canonical full mutation-sequence example: `_notify.notify`, builder-lock release, operator message.
  - `## Holistic code review` starts at line 935.
  - Step 3.5 "ERROR-only-aggregate retry" spans lines 1095-1128; its halt is at line 1127.
  - Step 3.6 "Rate-limit fallback" spans lines 1130-1149; halts at lines 1146 and 1148.
  - Sibling holistic escalation branches with full mutation sequences already documented: infrastructure (line 1187), transient (line 1190), verify/logic (line 1195) — all inside step 5's `REQUEST_CHANGES` handling (lines 1173-1196).
  - Step 7 "Rounds exhausted" at lines 1200-1205.
  - "0.5. Baseline pre-flight" spans lines 467-483 (the `--stage baseline` invocation is at line 473; the `per_batch` substage description is at lines 478-480).
  - "0.55. Done-gate baseline pre-flight" (sibling with timeout note) spans lines 427-465; its timeout note is at line 456.
  - "6. Run finalize stage" 's timeout note (another sibling) is at line 323.
  - Handoff's "0. Pre-done gate" (third sibling) spans lines 1284-1319; its timeout note is at line 1314.
- `mill-plan/SKILL.md` section map:
  - Line 94 — inside the entry-gate wait's `<task-notification>` two-notification-shape explanation.
  - Line 118 — the "Fork scope guardrail" paragraph in `### Phase: Plan`.
  - Line 347 and line 432 — both inside "Phase: Plan Review"'s Agent-mode dispatch instructions (`--holistic-only` plan review dispatch); these two lines currently read identically.
  - Line 366 — inside Phase: Plan Review's crash-recovery / resume-flow prose.
  - Line 381 — **already correct**, uses bare `mill-go/SKILL.md` for the same "## Agent-mode dispatch" section; use this line's exact phrasing/backtick style as the template for fixing 118/347/366/432.
  - Line 402 — "Confirm `mill-receiving-review` is loaded" step in Phase: Plan Review, step 3.

## Constraints

No `CONSTRAINTS.md` present at the hub root. No additional constraints beyond the repo's own `CLAUDE.md` conventions (e.g. never use `sed`; ASCII-only in generated markdown where applicable — these SKILL.md files already contain non-ASCII em-dashes/arrows elsewhere, matching existing file style, so new prose should match the surrounding style rather than force ASCII-only, since the `print()`/`_log()` ASCII rule in `CLAUDE.md` applies to stdout output, not to SKILL.md prose).

## Testing

This is a documentation-only change to two `SKILL.md` files — no application/script code changes, so no unit tests apply. Verification is mechanical, via `verify:` grep commands per plan card:

- After the #806 batch: `grep -n "plugins/mill/skills/mill-go\|plugins/mill/skills/mill-receiving-review\|plugins/mill/docs" plugins/mill/skills/mill-plan/SKILL.md` must return **zero** matches (confirms all 6 sites converted, and that the correct subset of `plugins/mill/...` references — i.e. none of the intentionally-untouched template/unit_tests/plugin.json ones, since those don't match `skills/` or `docs/`, only `templates/`/`unit_tests/`/`.claude-plugin/`) is unaffected.
- After the #809 batch: `grep -n 'update_field(status_path, "blocked_reason"' plugins/mill/skills/mill-go/SKILL.md` must return **zero** matches.
- After the #810 batch: confirm (by eye, in review) that steps 3.5's and 3.6's two halts each now contain `_status.set_blocked(`, a commit, `_notify.notify("mill-go.blocked"`, and a builder-lock `release` call before their `halt with BLOCKED:` sentence — no grep substitutes well for this since it's a structural/ordering check, not a presence check.
- After the #792 batch: `grep -n "600000ms" plugins/mill/skills/mill-go/SKILL.md` should show one **new** match near "0.5. Baseline pre-flight" (in addition to the 3 pre-existing sibling matches), for a total of 4.
- These are plain `grep` invocations against markdown files — no `PYTHONPATH=` prefix is needed (the `verify:` prefix rule in `CLAUDE.md` applies to Python-project test subprocesses, not to grep-only verify commands with no Python involved).
- No `_codeguide/` exists in this repo, so no codeguide-update step applies to this task.

## Q&A log

- **Q:** Should the fix cover exactly the 4 issues named in this task's brief, or also opportunistically fix the identical `#806`-pattern bug at `mill-start/SKILL.md:276`? **A:** [auto-pick] Scope strictly to the 4 named issues; note the mill-start occurrence as a follow-up, don't fix it now. **Why:** the task brief explicitly scopes to mill-go/mill-plan SKILL.md; mill-start is a different file with its own task lineage.
- **Q:** For #810's steps 3.5/3.6 halts, what state mutation should be added before halting? **A:** [auto-pick] `_status.set_blocked(...)` (single atomic call) + commit + `_notify.notify("mill-go.blocked", ...)` + builder-lock release, mirroring `### Blocked`. **Why:** consistent with #809's fix using the same correct helper; the two-call `append_phase`+`update_field` pattern used by sibling branches 1187/1190/1195 is provably buggy on a first-ever block per #809.
- **Q:** For #809's step 7, should the fix be minimal (swap the broken call for `set_blocked`) or also add the `_notify.notify`/lock-release step 7 currently lacks? **A:** [auto-pick] Minimal fix only — swap the two calls for one `_status.set_blocked(...)` call; leave the notify/lock-release gap alone. **Why:** #809 reported only the `ValueError` precondition bug, not a missing-notification gap; broadening risks scope creep beyond the named issue.
- **Q:** For #792's timeout note, copy sibling wording verbatim or adapt the rationale clause to name `--stage baseline`/`verify_baseline_failures` specifically? **A:** [auto-pick] Adapt: keep the lead sentence verbatim, write a 0.5-specific rationale clause. **Why:** matches the issue's own suggested-fix language and stays factually accurate — 0.5 doesn't invoke `done_gate`, so the two other siblings' `done_gate`-specific rationale would misdescribe 0.5's actual risk.
- **Q:** For #806, use bare `<skill>/SKILL.md` for skill cross-refs and what for the docs file? **A:** [auto-pick] `mill-go/SKILL.md` / `mill-receiving-review/SKILL.md` for skill refs (matching existing line-381 precedent), `../../docs/harness-tool-contracts.md` for the docs file. **Why:** the bare-skill-relative form is already proven portable at line 381 in the same file and throughout mill-start/SKILL.md; the docs file needs one more `../` hop since it isn't under `skills/`.
