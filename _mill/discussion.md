# Discussion: Monitor tool: persistent:true doesn''t exist, entry-gate waits break

```yaml
task: Monitor tool: persistent:true doesn''t exist, entry-gate waits break
slug: mill-monitor-persistent-true-unsupported
status: discussing
parent: main
```

## Problem

`mill-plan/SKILL.md`'s "Entry-gate wait for upstream mill-start" section and `mill-go-base/SKILL.md`'s
"Entry-gate wait for upstream mill-plan" section both instruct the orchestrator to call the `Monitor`
tool with `persistent: true`, and add: "Do not set a `timeout_ms` value distinct from the default —
`persistent: true` makes it irrelevant." Ten independent field reports (GitHub issues #1058, #1062,
#1066, #1067, #1078, #1085, #1088, #1096, #1100, #1108), filed from several different repos on
2026-09-21, all say the `Monitor` tool schema they hit had **no `persistent` parameter at all** —
only `command`/`ws`, `description`, and `timeout_ms` (capped, per those reports, at 1,800,000 ms /
30 minutes). Following the SKILL text literally against that tool build gives a wait that expires
every 5–30 minutes against a `pipeline.entry_wait_timeout_minutes` budget that defaults to 240
minutes, with no documented recovery branch for the expiry notice — the SKILL's three documented
outcomes are `READY`, `TIMEOUT after <N>s`, and harness-level cancellation, none of which describe an
early, unrequested expiry. Reporters worked around this by hand: arming at the `timeout_ms` cap,
re-arming on every expiry, and manually decrementing their own remaining-budget bookkeeping across
re-arms — exactly the loop the SKILL text should have told them to run, if the parameter really
doesn't exist.

**Verification finding that changes the fix.** Before writing this task's plan, the current, live
`Monitor` tool schema available to this very session was inspected directly (not assumed from the
bug reports, and not read from any cached/stale source). It exposes:

```
persistent: boolean, default false — "Run for the lifetime of the session (no timeout).
  Use for session-length watches like PR monitoring or log tails. Stop with TaskStop."
timeout_ms: number, default 300000, max 3600000 — "Kill the monitor after this deadline.
  Ignored when persistent is true."
```

This directly contradicts the specific technical claim common to all ten source issues (no
`persistent` parameter; 30-minute cap). The SKILL text's existing `persistent: true` call already
matches this confirmed-current schema exactly, including the "no timeout, stop via TaskStop" semantics
the entry-gate wait actually wants. Per this repo's own CLAUDE.md ("reading the real code takes
priority over trusting the task body" — stated there for source-code verification, and the same
principle applies to a live tool schema, which is exactly as authoritative), the fix in this task is
**not** "drop `persistent: true` and rewrite the wait around a bounded-timeout re-arm loop", as the
ten source issues suggest — doing so would regress a call pattern that is demonstrably correct against
the tool as it exists now, purely to satisfy reports against an evidently older or different `Monitor`
build.

What **is** still a real, current defect, independent of which `Monitor` build is in play: the
entry-gate wait's documented outcome list has no branch for an unexpected/early expiry notification.
That gap is real on any build — a future regression, an older cached harness, or a host that behaves
differently from this session's — and it's the concrete failure every one of the ten reports actually
hit (an expiry with no documented next step). This task closes that gap defensively, on top of keeping
the verified-correct `persistent: true` call, rather than replacing it.

## Scope

**In:**
- `plugins/mill/skills/mill-plan/SKILL.md`, "Entry-gate wait for upstream mill-start" section: add a
  fourth, explicit outcome branch — an unexpected/early expiry notification — alongside the existing
  `READY` / `TIMEOUT after <N>s` / harness-stop branches, with a re-arm action.
- `plugins/mill/skills/mill-go-base/SKILL.md`, "Entry-gate wait for upstream mill-plan" section: the
  identical fourth branch (this section already mirrors mill-plan's wait pattern almost verbatim).
- `plugins/mill/docs/harness-tool-contracts.md`, "## Monitor tool" section: refresh the recorded
  contract with the schema actually confirmed this session (parameter list, `timeout_ms`
  default/max, and the "ignored when persistent is true" note), record that it was reconfirmed via a
  live schema read on 2026-09-21, and document the new expiry/re-arm branch as part of the shared
  contract, since both SKILL.md sections above cite this doc as their source of truth.
- Budget bookkeeping across a re-arm: the orchestrator must recompute the wait's remaining
  `giveup_s` from wall-clock elapsed time since the wait was first armed, not restart it from zero,
  so a re-arm cannot silently turn `pipeline.entry_wait_timeout_minutes` into an unbounded wait.

**Out:**
- No change to `_phase_wait.build_wait_command`'s poll-script logic itself. The script's own internal
  `elapsed`/`giveup_s` loop already runs correctly stand-alone (see Technical context) — the defect is
  entirely in what the orchestrator does when the *harness* kills the `Monitor` watch early, not in
  the polled bash script.
- No change to `pipeline.entry_wait` / `pipeline.entry_wait_timeout_minutes` semantics or defaults —
  both already do what's needed.
- `orch-wait/SKILL.md` and `orch-review/SKILL.md`: both use the word "persistent" only as a
  description of the general wait idiom ("persistent background bash poll, not a fixed sleep") and
  cross-reference mill-go-base's canonical section rather than repeating the literal `Monitor(...,
  persistent: true, ...)` call. They inherit this task's fix through that cross-reference with no
  text change of their own required.
- No change to `Monitor`'s tool implementation itself (out of this repo's control — it's a harness
  tool, not mill code).
- Not reopening or commenting further on the ten already-closed/consolidated source issues; they were
  already folded into this one wiki task.

## Decisions

### Keep `persistent: true`, do not revert to a bounded re-arm loop as the primary mechanism

- Decision: The entry-gate wait keeps its existing single `Monitor(command=cmd, persistent: true,
  description=...)` call as the primary mechanism. Do not restructure it around `timeout_ms` set to
  the tool's cap plus an orchestrator-driven re-arm loop as the normal path.
- Rationale: Live verification this session (see Problem) confirms `persistent` is a real, current
  `Monitor` parameter with exactly the semantics this wait needs — unbounded runtime bounded only by
  the poll script's own internal `giveup_s` (already up to `pipeline.entry_wait_timeout_minutes`,
  default 240 minutes) and by `TaskStop`/session end. Rewriting around a ≤60-minute bounded call plus
  a mandatory re-arm loop would add real complexity (wall-clock budget tracking across re-arms) to
  work around a limitation that does not reproduce against the current tool.
- Rejected: Dropping `persistent: true` and always using the capped-`timeout_ms` re-arm loop (the
  literal ask in all ten source issues) — rejected because it contradicts directly-verified current
  tool behavior; applying it anyway would be "fixing" working code to match stale field reports,
  exactly the kind of stale-context mistake this repo's CLAUDE.md calls out as having previously
  caused mid-plan rework.

### Add a fourth documented outcome: unexpected/early expiry, with re-arm

- Decision: Both entry-gate wait sections gain a fourth branch in their "Branch on the `<event>`
  content" step, alongside `READY` and `TIMEOUT after <N>s`: **any notification that is not one of
  those two recognized event shapes, and is not the separately-handled harness-stop case** (an
  event-less "Monitor expired..." notice, or any other unrecognized event text) is treated as an
  unexpected early expiry. On this branch: recompute the wait's remaining budget as
  `remaining_s = giveup_s - elapsed_wallclock_s` (wall-clock seconds since this Entry-gate wait was
  first armed for the current phase-table evaluation, tracked by the orchestrator, not by the poll
  script); if `remaining_s <= 0`, treat it exactly like the `TIMEOUT after <N>s` branch (halt with the
  existing give-up message); otherwise rebuild `cmd` via `_phase_wait.build_wait_command` with
  `giveup_s = remaining_s` (same `ready_phase`, `poll_interval_s`, `clean_tree_root`/
  `clean_tree_paths` as the original call), re-issue the same `Monitor(..., persistent: true, ...)`
  call, and resume waiting — this is a re-arm, not a restart of Entry step 4's phase-table
  re-evaluation (that only happens on `READY`).
- Rationale: This is the one concrete, build-independent defect every source issue actually
  demonstrates: an expiry with no documented next step. Documenting it costs nothing on a harness
  build where `persistent: true` never actually expires early (the branch simply never fires there),
  and it is exactly correct insurance against an older/different harness build, a future regression,
  or a session restart scenario. Tracking wall-clock elapsed at the orchestrator level (rather than
  trusting the poll script's own internal counter) is required because a re-arm starts a brand-new
  bash process whose own `elapsed` variable restarts at 0 — issue #1066 explicitly flags this as the
  failure mode when re-arming by hand without separate bookkeeping.
- Rejected: Silently re-arming with the *original* `giveup_s` on every expiry (what several reporters
  did without adjusting for elapsed time) — rejected because it can turn a configured 4-hour give-up
  into an effectively unbounded wait across enough re-arms, defeating the point of
  `pipeline.entry_wait_timeout_minutes`.
  Also rejected: folding the expiry case into the existing harness-stop branch ("no automatic
  retry, halt") — rejected because unlike an operator-issued `TaskStop`, an early expiry is not an
  operator decision to stop waiting; halting there would force a manual `/mill-plan` or `/mill-go`
  re-invocation for a condition the orchestrator can safely recover from on its own.

### Refresh `harness-tool-contracts.md`'s Monitor section rather than leaving it silently stale

- Decision: Update the "## Monitor tool" section to record the schema as directly reconfirmed on
  2026-09-21 (parameter list including `persistent`; `timeout_ms` default 300000 / max 3600000,
  ignored when `persistent` is true), and add one paragraph documenting the expiry/re-arm contract
  from the decision above, since this file is the single cross-referenced source of truth both
  SKILL.md sections point readers to.
- Rationale: The file's own header states its shapes "were confirmed via live spikes" — leaving it
  asserting a schema that ten independent field reports contradict, with no note of the
  re-verification that resolved the discrepancy, would misinform the next reader who trusts this file
  over re-checking the live tool themselves.
- Rejected: Leaving `harness-tool-contracts.md` untouched and only patching the two SKILL.md files —
  rejected because the two SKILL.md sections explicitly say "See
  `plugins/mill/docs/harness-tool-contracts.md` for this contract's canonical write-up," so an
  un-refreshed canonical doc would immediately fall out of sync with its own declared consumers.

## Technical context

- `plugins/mill/skills/mill-plan/SKILL.md` lines 82–118: "Entry-gate wait for upstream mill-start".
  The `Monitor` call and its "do not set timeout_ms" note are at lines 100–101. The three-outcome
  branch list is at lines 109–114 (`READY`, `TIMEOUT after <N>s`, harness-stop at line 114).
- `plugins/mill/skills/mill-go-base/SKILL.md` lines 174–225: "Entry-gate wait for upstream mill-plan",
  structurally identical to mill-plan's copy but additionally carries the speculative baseline-launch
  logic (lines 197–206) — that block is unrelated to this task and must not be touched. The `Monitor`
  call is at lines 207–208; the branch list is at lines 214–219 (`READY`, `TIMEOUT after <N>s`,
  harness-stop at line 220).
- `plugins/mill/docs/harness-tool-contracts.md` lines 24–34: the current "## Monitor tool" section,
  itself already written assuming `persistent: true` is valid — it needs its parameter list and
  numeric bounds refreshed, not its core claim reversed.
- `plugins/mill/scripts/_phase_wait.py`: `build_wait_command(status_path, ready_phase, poll_interval_s,
  giveup_s, *, clean_tree_root=None, clean_tree_paths=None) -> str` renders the polled bash script.
  Its docstring is explicit that it "never reads or knows about
  `pipeline.entry_wait_timeout_minutes`" — the minutes-to-seconds conversion and the choice of
  `poll_interval_s` are the caller's job, which is exactly why the re-arm branch above must recompute
  `giveup_s` itself before calling this function again; there is no existing helper for the
  wall-clock-elapsed-since-armed bookkeeping, so the plan should add small orchestrator-level (SKILL
  text) bookkeeping, not a new script function, unless the plan author judges the arithmetic too
  fiddly to spell out safely in prose — that call is left to mill-plan.
- Both entry-gate wait sections already record the poll script's two-notification shape (one
  `<event>`-carrying notification per stdout line, then a separate event-less
  `<status>completed</status>` notification) and cite `harness-tool-contracts.md` for it — the new
  branch does not change that shape, it only adds a case for an event whose content matches neither
  `READY` nor `TIMEOUT after ...`.
- `matches_wait_trigger` and the phase-table gating around these sections are unrelated to this task
  and must not change.
- Neither SKILL.md file states a concrete `timeout_ms` cap number anywhere in its own text today —
  the 1,800,000 ms figure only ever appeared in the (now superseded) source-issue reports, not in this
  repo's own docs, so there's no incorrect number embedded in-repo to also correct beyond
  `harness-tool-contracts.md`'s own description.
- `orch-wait/SKILL.md` (lines ~17–21) and `orch-review/SKILL.md` (lines ~32–34) describe their waits
  as "same idiom as mill-go-base's entry-gate wait" / "same idiom as orch-wait's own wait" without
  repeating the literal `Monitor(..., persistent: true, ...)` call — confirmed by grep across the
  plugin tree; no edit needed there.

## Testing

This is a documentation-only change (two `SKILL.md` files plus one `docs/*.md` file) — no Python
source changes, so `plugins/mill/unit_tests/` needs no new test file. Verification is a careful
read-through, not an automated run:

- Confirm the added fourth branch in each SKILL.md is reachable only when the notification's `<event>`
  content matches neither `READY` nor `^TIMEOUT after \d+s waiting for phase: `, and is distinct from
  the existing harness-stop bullet (which fires on a `TaskStop`/cancellation of the recorded
  `task_id`, not on any notification content at all) — the three conditions must remain mutually
  exclusive so an implementer can't accidentally make the new branch swallow the other two.
- Diff the two SKILL.md sections' final wording side by side: mill-go-base's copy already carries
  extra material (the speculative baseline launch) interleaved with the shared wait pattern, so the
  new branch's wording should only differ where the two files already differ today (target phase
  name, upstream skill name) and otherwise match, preserving the existing near-duplication.
- Confirm `harness-tool-contracts.md`'s refreshed numbers (`timeout_ms` default 300000 / max 3600000)
  match this discussion's own Problem section exactly (both were read from the same live schema
  fetch in the same session) — no separate re-verification needed by mill-plan, but the plan should
  not silently change these numbers again without a fresh check.
- No regression risk to `_phase_wait.py` or its existing test coverage (if any) since this task does
  not touch that module.

## Q&A log

- **Q:** Given the live `Monitor` tool schema (verified this session) contradicts all ten source
  issues' central claim, should the fix (1) drop `persistent: true` and rewrite around a
  bounded-`timeout_ms` re-arm loop as originally asked, (2) keep `persistent: true` unchanged and
  make no functional edit at all, or (3) keep `persistent: true` and add a defensive re-arm branch for
  the one concrete gap every report actually hit (missing outcome for an unexpected expiry)?
  **A:** [auto-pick] Option 3. **Why:** matches directly-verified current tool behavior (ruling out
  option 1, which would regress working behavior to satisfy stale reports) while still fixing the one
  defect that's real regardless of which `Monitor` build is in play, and every one of the ten reports
  independently hit exactly that defect (an expiry with no documented next step) — leaving it
  undocumented (option 2) would mean the task closes with nothing to show for ten consolidated
  reports, and reopens the same "no branch for this notification" trap on the very host or version
  drift that produced them in the first place.
- **Q:** Should the re-arm branch's remaining-budget recomputation live as a new `_phase_wait.py`
  helper function, or be spelled out as orchestrator-level bookkeeping directly in the two SKILL.md
  sections' prose? **A:** [auto-pick] Spell it out in the SKILL.md prose (option 1, recommended over
  adding a new script function). **Why:** the arithmetic is a single subtraction plus a re-call to the
  existing `build_wait_command` with an adjusted `giveup_s` — `_phase_wait.py`'s own docstring already
  establishes the convention that budget/minutes-to-seconds bookkeeping is the caller's job, not this
  module's; introducing a new helper for one subtraction would be scope beyond what a docs-only fix
  needs. mill-plan may still choose to extract a helper if it finds the prose ambiguous to implement
  safely — left as an implementation-level judgment call, not a discussion-level one.
- **Q:** Does `orch-wait/SKILL.md` / `orch-review/SKILL.md` need the same literal edit since they
  reference "the same idiom"? **A:** [auto-pick] No (option 1: rely on the existing cross-reference).
  **Why:** grep confirms neither file contains a literal `Monitor(..., persistent: true, ...)` call to
  edit — both already describe their wait as following mill-go-base's canonical section, so they
  inherit the fix through that reference with zero text change.
- **Q:** Should `harness-tool-contracts.md` be refreshed as part of this task, or left to a future,
  separate task? **A:** [auto-pick] Refresh it now (option 1). **Why:** both edited SKILL.md sections
  cite it by name as "this contract's canonical write-up" — shipping a fix that makes the two call
  sites correct while leaving their own cited source of truth silently stale would be an inconsistency
  introduced by this very task, not a pre-existing one it's reasonable to defer.
