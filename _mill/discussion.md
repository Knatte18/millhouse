# Discussion: Monitor tool: persistent:true still referenced in mill-go-base and mill-plan despite no such param

```yaml
task: Monitor tool: persistent:true still referenced in mill-go-base and mill-plan despite no such param
slug: monitor-persistent-true-still-referenced
status: discussing
parent: main
```

## Problem

`mill-go-base/SKILL.md` (Entry-gate wait for upstream mill-plan) and `mill-plan/SKILL.md` (Entry-gate wait for upstream mill-start) both instruct the orchestrator to call the `Monitor` tool with `persistent: true`.
A live read of the real `Monitor` tool schema in this session (2026-09-23) confirms that parameter does not exist: the schema has `command`/`ws`, `description`, and `timeout_ms` (default `300000`, and per the tool's own description "deadlines above 1800000ms are capped to 1800000ms" — i.e. an effective 30-minute cap regardless of the declared JSON `maximum: 3600000`). There is no `persistent` field at all.

A prior task already swept nine other GitHub issues reporting the same "`persistent` doesn't exist" problem (#1110, #1117, #1125, #1126, #1128, #1132, #1135, plus the two earlier ones referenced from `harness-tool-contracts.md`) and fixed other call sites, but missed these two. Issue #1139 is this task's source and gives the concrete fix: pass `timeout_ms: 1800000` (the effective max) instead of `persistent: true`, and treat re-arming the wait on every expiry as the normal path rather than an edge case.

`plugins/mill/docs/harness-tool-contracts.md`'s "## Monitor tool" section — which both SKILL.md sections cite as "the canonical write-up" for this contract — currently asserts the opposite: that a "live tool-schema read on 2026-09-21" reconfirmed a `persistent` boolean parameter, and that the ten field reports claiming otherwise are simply hitting a different, non-conforming build. That claim does not hold against this session's own live schema read. Fixing only the two SKILL.md call sites while leaving their cited canonical doc asserting `persistent` exists would leave the fix self-contradictory, so this doc is in scope too.

## Scope

**In:**
- `mill-go-base/SKILL.md`'s "Entry-gate wait for upstream mill-plan" section: replace `persistent: true` with `timeout_ms: 1800000` on both the initial `Monitor` call and the re-arm call, and reframe the "any other notification content" branch from an "unexpected early expiry" to the expected, normal outcome for any wait whose configured `giveup_s` exceeds 1800s.
- `mill-plan/SKILL.md`'s "Entry-gate wait for upstream mill-start" section: the same two edits, mirrored.
- `plugins/mill/docs/harness-tool-contracts.md`'s "## Monitor tool" section: correct the schema description (drop the `persistent` claim, state the real params and the 1800000ms effective cap), and correct the framing of the "early, unrequested expiry" bullet to match the reframing above (it is not build-specific — no `Monitor` build holds a wait open indefinitely).

**Out:**
- `orch-wait/SKILL.md` and `orch-review/SKILL.md`: both use the English phrase "persistent background bash poll" descriptively (the poll script runs continuously in the background), never the literal `Monitor(persistent: true)` tool argument. Confirmed via grep — no change needed.
- `mill-setup/SKILL.md`'s one `persistent` hit refers to a persistent shell env var, unrelated to the `Monitor` tool. No change needed.
- The `TIMEOUT after <N>s` branch's own halt behavior, `wait_started_epoch`/`remaining_s` bookkeeping, and the `clean_tree_root`/`clean_tree_paths` gating in `mill-plan`'s wait: none of this depends on `persistent` and none of it changes.
- `_phase_wait.py` itself: it only builds the poll script string; it has no knowledge of the `Monitor` tool's parameters and needs no change.

## Decisions

### Replace `persistent: true` with a fixed `timeout_ms: 1800000`

- Decision: Every `Monitor(...)` call in both entry-gate wait sections (initial call and every re-arm) passes `timeout_ms: 1800000` explicitly instead of `persistent: true`. Always the same constant, on every call, regardless of how much of the configured `giveup_s` budget remains.
- Rationale: `1800000` is the tool's effective cap (per the tool's own description), so it minimizes re-arm frequency. Using a constant instead of `min(remaining_s * 1000, 1800000)` is simpler and just as correct: the poll script's own internal timeout (`remaining_s`, baked into the rebuilt `cmd`) governs the real give-up point and will make the script print its own `TIMEOUT after ...` line and exit before `Monitor`'s 1800000ms cap fires whenever `remaining_s` is the smaller of the two — no separate arithmetic needed on the `Monitor` side.
- Rejected: Passing no `timeout_ms` (defaults to 300000ms, forcing needless re-arms every 5 minutes instead of every 30). Computing a dynamic `timeout_ms` per re-arm (correct but adds arithmetic that buys nothing over the constant, since the script's own internal timeout already handles the tail case).

### Reframe the third branch as the normal path, not an edge case

- Decision: The "any other notification content" branch (a `Monitor` expiry with no `READY`/`TIMEOUT` event) is documented as the expected, normal outcome for any wait whose `giveup_s` exceeds 1800s — not as an "unexpected early expiry" specific to some non-conforming `Monitor` build. Since `Monitor` has no mode that holds a wait open indefinitely, this branch fires at least once for every wait exceeding 30 minutes (the default `entry_wait_timeout_minutes` is 240, so this is the common case, not the rare one). The branch's mechanics (recompute `remaining_s`, halt if exhausted, otherwise rebuild `cmd` and re-issue `Monitor`) are unchanged — only the framing/prose changes, plus dropping any language that ties the branch to a specific "build" of the tool.
- Rationale: The old framing was written under the (now-disproven) belief that `persistent: true` normally holds the wait open, making any early expiry a build-specific anomaly. That belief is gone, so the anomaly framing is gone with it — otherwise a future reader re-derives the same wrong mental model this task exists to fix.
- Rejected: Leaving the "unexpected early expiry" language in place and only swapping the tool parameter. This would technically work (the mechanics are unchanged) but perpetuates the false premise in prose, which is exactly the kind of doc/reality drift this task (and the eight before it) is cleaning up.

### Also correct `harness-tool-contracts.md`'s Monitor tool section

- Decision: Rewrite the "## Monitor tool" section's opening paragraph and the "early, unrequested expiry" bullet to state the real schema (no `persistent` field; `timeout_ms` defaults to 300000, effectively capped at 1800000) and to match the reframing above. Keep the rest of the section (the two-notification shape: one per-line event notification, then a separate terminal `<status>completed</status>` notification) — that part is unaffected by the `persistent` question and was not disputed by any of the field reports.
- Rationale: Both SKILL.md sections point at this file as their contract's "canonical write-up." Fixing the call sites while leaving the doc they cite asserting the opposite creates a standing self-contradiction in the repo — the next reader (human or plan-writing session) who follows either section's link lands on a doc telling them `persistent` is real and their two just-read SKILL.md sections are stale.
- Rejected: Leaving `harness-tool-contracts.md` untouched as out-of-scope, on the theory that the brief only names the two SKILL.md files. Rejected because the doc is not an independent third fact source — it is the explicitly cross-referenced justification for the exact two sections in scope, so leaving it wrong defeats the point of fixing the sections at all.

## Technical context

- `Monitor` tool schema (confirmed live, this session, 2026-09-23): `command` or `ws` (mutually exclusive), `description` (required), `timeout_ms` (number, default `300000`, JSON `maximum: 3600000`, but the tool's own description states "Deadlines above 1800000ms are capped to 1800000ms" — treat 1800000 as the real ceiling). No `persistent` parameter exists.
- `_phase_wait.build_wait_command(status_path, ready_phase, poll_interval_s, giveup_s, *, clean_tree_root=None, clean_tree_paths=None) -> str` (`plugins/mill/scripts/_phase_wait.py:28`) renders the bash poll script passed as `Monitor`'s `command`. It has its own internal `giveup_s`-based timeout independent of `Monitor`'s `timeout_ms` — printing `TIMEOUT after <N>s waiting for phase: <ready_phase>` and exiting 2 once its own internal elapsed time reaches `giveup_s`. This is why the fix can pass a constant `timeout_ms: 1800000` on every `Monitor` call: the script's own internal timeout (rebuilt with `remaining_s` on every re-arm) is what actually enforces the operator-configured `entry_wait_timeout_minutes` budget; `Monitor`'s `timeout_ms` only bounds how long any single `Monitor` call can run before it must be re-armed.
- Call sites to edit:
  - `plugins/mill/skills/mill-go-base/SKILL.md:208-209` (initial `Monitor` call + its "do not set timeout_ms" sentence) and `:221` (the re-arm branch).
  - `plugins/mill/skills/mill-plan/SKILL.md:102-103` (initial call) and `:116` (re-arm branch).
  - `plugins/mill/docs/harness-tool-contracts.md:26` (opening paragraph) and `:28`, `:35` (the `persistent: true` example call and the "early, unrequested expiry" bullet).
- Both SKILL.md sections are otherwise structurally identical (mill-go-base waits on mill-plan reaching `planned`; mill-plan waits on mill-start reaching `discussed`), so the same edit shape applies to both — mill-plan's version additionally threads `clean_tree_root`/`clean_tree_paths` into `build_wait_command`, which is untouched by this fix.
- Confirmed via `grep -rn "persistent" plugins/`: the only literal `Monitor(..., persistent: true, ...)` call-site text is in the four line ranges above (two per file, initial + re-arm). `orch-wait/SKILL.md:19`, `orch-review/SKILL.md:34`, and `mill-setup/SKILL.md:357` all use "persistent" in unrelated English prose, not as a tool argument.

## Testing

No unit or integration test exercises the literal `Monitor` tool call (it's an orchestrator-only, harness-level interaction with no Python entry point) — `_phase_wait.py`'s existing test coverage (`build_wait_command`/`matches_wait_trigger` string-building and predicate logic) is unaffected by this fix and needs no new cases, since neither function's signature or behavior changes.

Verification for this task is inspection-based:
- `grep -rn "persistent: true" plugins/mill/` returns no results after the fix (currently returns the four call sites plus the one doc example).
- `grep -rn "persistent" plugins/mill/docs/harness-tool-contracts.md` no longer asserts the parameter exists.
- Read through both edited entry-gate wait sections end-to-end and confirm the re-arm branch's mechanics (recompute `remaining_s`, halt-or-rebuild) still read correctly with the new framing — this is a prose/doc-accuracy fix, not a behavior change to any runnable code, so there is no test suite to run beyond the existing `run-all.py` regression pass (unaffected files, expected to stay green).

## Q&A log

- **Q:** What should replace `persistent: true` in the `Monitor` call? 1) Pass a fixed `timeout_ms: 1800000` (the tool's effective cap) on every call, and treat every expiry-without-event as the normal re-arm path, per #1139. 2) Pass `timeout_ms: 1800000` but keep the old "unexpected early expiry" framing unchanged. 3) Leave `timeout_ms` unset (defaults to 300000ms) and just re-arm more often. **A:** [auto-pick] Fixed `timeout_ms: 1800000` on every call, reframed as the normal re-arm path. **Why:** matches #1139's concrete fix exactly, minimizes re-arm frequency, and closes the doc/reality gap that caused this bug class (nine prior issues) instead of just patching the symptom.
- **Q:** Should `harness-tool-contracts.md`'s Monitor tool section — which both SKILL.md sections cite as the canonical write-up for this contract — be corrected too, even though the task brief only names the two SKILL.md files? 1) Yes, correct it as part of this fix. 2) No, leave it for a separate task. **A:** [auto-pick] Yes. **Why:** it is the explicit cross-referenced justification for exactly the two sections in scope; leaving it asserting `persistent` exists while the sections it justifies no longer use it is a self-contradiction that defeats the fix.
- **Q:** Do `orch-wait/SKILL.md` and `orch-review/SKILL.md` (which contain the substring "persistent") need any edits? 1) No — confirmed by reading both lines that the word is used descriptively ("persistent background bash poll"), never as the literal tool argument. 2) Audit them anyway for safety. **A:** [auto-pick] No edits needed. **Why:** grep plus direct reading of both lines confirms neither passes `persistent: true` to any tool call; re-auditing would be redundant work with no behavior at stake.
