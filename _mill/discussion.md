# Discussion: Agent-tool dispatch discards the effort tier already encoded in mill-agents.yaml (opushigh/opusmedium/opusmax)

```yaml
task: Agent-tool dispatch discards the effort tier already encoded in mill-agents.yaml (opushigh/opusmedium/opusmax)
slug: mill-agent-effort-gap
status: discussing
parent: hanf/linux-port-more
```

## Problem

Under `dispatch: agent`, `mill-go/SKILL.md` step 3 resolves a reviewer or implementer
alias from `mill-agents.yaml` (e.g. `opushigh`, `sonnetmax`) and reads its `effort`
field into the prepare-stage JSON envelope — but the Agent tool call that actually
spawns the subagent only accepts `subagent_type`, `model`, `prompt`, and optionally
`isolation`. There is no `effort` parameter to forward it to, so every Agent-mode
dispatch actually runs at whatever reasoning effort the invoking session (or the
`mill-reviewer.md` / `mill-implementer.md` agent definition) defaults to — regardless
of whether `mill-config.yaml` named `opusmedium`, `opushigh`, or `opusmax` for that
role. This was flagged while investigating why Opus effort felt too high after the
Opus 5 release: the operator could not actually dial reviewer/implementer effort down
via config, because the signal was silently dropped at the one place it needed to
reach the harness.

This is a documented, intentional gap in the SKILL.md text (not a silent bug), but it
means the per-role effort tiers in `mill-config.yaml` (`roles.implementer.model`,
`roles.fixer.model`, `roles.*.reviewer`) have had no actual effect on reasoning effort
since Agent-mode dispatch was introduced. Claude Code's subagent definition frontmatter
supports a real `effort:` key (low/medium/high/xhigh/max) that overrides the session
default per subagent-type at spawn time — confirmed via Claude Code's own sub-agent
documentation — which gives a concrete, already-available mechanism to close the gap.

## Scope

**In:**
- Six new static agent-definition files under `plugins/mill/agents/`:
  `mill-reviewer-medium.md`, `mill-reviewer-high.md`, `mill-reviewer-max.md`,
  `mill-implementer-medium.md`, `mill-implementer-high.md`, `mill-implementer-max.md`.
  Each is identical to its base file (`mill-reviewer.md` / `mill-implementer.md`)
  except for `name:` (matches its own filename stem) and an added
  `effort: medium|high|max` frontmatter key.
- `mill-go/SKILL.md` step 3 (Agent-mode dispatch): select `subagent_type` from the
  resolved envelope's `effort` field instead of always using the base
  `mill:mill-reviewer` / `mill:mill-implementer` literal.
- Extending `plugins/mill/unit_tests/test-agents-defs.py` with parametrized coverage
  for the 6 new files.

**Out:**
- No `mill-agents.yaml` schema change — `effort` is already present and already
  correctly resolved into every review/implement/fix/merge-in envelope. Only the
  Agent-tool-call consumption side was missing.
- No change to gemini-provider dispatch — Agent-mode dispatch is already
  Claude-provider-only (`_agent_dispatch.resolve_dispatch_mode`); gemini reviewers use
  subprocess/psmux dispatch, which reads `effort` differently and is unaffected.
- No new `low` or `xhigh` tier files. No catalog entry in `mill-agents.yaml` currently
  sets those values — `haiku`, `g25flash`, `g25pro`, `g3flash_preview` (and `_bulk`
  variants) carry no `effort` key at all and keep using the base agent file, which
  preserves their exact current behavior (session-default effort) — not a regression.
- No new `agents.yaml` field mapping alias -> agent-def file. The tier name is derived
  directly as a string from the already-resolved `effort` value; a lookup table would
  just duplicate that value.

## Decisions

### tier-file-strategy

- Decision: Ship 6 new static agent-definition files under `plugins/mill/agents/`
  (listed in Scope). Each is a copy of its base file's body and `description`, with
  `name:` updated to the new filename stem and `effort: medium|high|max` added to
  frontmatter.
- Rationale: the Agent tool consumes `subagent_type` by name from the harness's static
  registry of `.md` files under `agents/` — there is no way to pass an inline-rendered
  agent definition at call time, and the `effort:` frontmatter key is the only verified
  mechanism to fix reasoning effort per subagent-type. Static per-tier files are the
  only way to attach it.
- Rejected: encoding effort as a prompt instruction (e.g. "operate at high effort") —
  no verified enforcement, unlike the native frontmatter key.

### subagent_type-selection

- Decision: in `mill-go/SKILL.md` step 3, compute `subagent_type` as: the base name
  (`mill:mill-reviewer` / `mill:mill-implementer`) when the envelope's `effort` is
  null/absent; else `mill:mill-{role}-{effort}` when `effort` is exactly `"medium"`,
  `"high"`, or `"max"`; else (an unrecognized future value) fall back to the base name,
  called out as a documented gap for that value — mirroring how today's
  always-drop-effort behavior is itself documented rather than silent.
- Rationale: `role` (`reviewer` vs `implementer`) is already determined at this point in
  step 3 by which CLI is being dispatched (the three review CLIs -> reviewer; implement,
  fix, merge-in CLIs -> implementer, since all implementer-class roles already share
  `mill:mill-implementer` per the existing "Why not fork?" note). The fallback-to-base
  path can never regress below current behavior (which is always base/session-default
  today), so it is strictly safe.
- Rejected: hard-failing the batch on an unrecognized `effort` value — would turn a
  future catalog addition into a dispatch-blocking error instead of a graceful (if
  imperfect) degrade to current behavior.

### test-coverage

- Decision: extend `test-agents-defs.py` with a parametrized check per new tier file,
  reusing its existing `_extract_frontmatter` helper: `name` matches the filename stem,
  `tools` set matches the corresponding base file's tools set exactly, `effort` equals
  the tier encoded in the filename, and `model` is absent (same invariant the base-file
  tests already assert).
- Rationale: the test file already covers exactly this surface for the two base files;
  extending it is near-zero marginal cost and catches copy-paste drift (wrong tools
  set, wrong effort value, mismatched name) across 6 near-duplicate files.
- Rejected: no automated test, relying on manual read-through — rejected given the
  existing pattern already exists and is directly extensible.

## Technical context

- `plugins/mill/skills/mill-go/SKILL.md` (Agent-mode dispatch, step 3) documents the
  exact gap this task closes — search for "has no corresponding Agent-tool call
  parameter to forward it to".
- Envelope construction already resolves `effort` correctly in five places; no
  script-side change is needed there, only the Builder's consumption of the value:
  - `plugins/mill/scripts/_review_discussion.py:123`
  - `plugins/mill/scripts/_review_plan.py:453` (per-batch) and `:545` (holistic)
  - `plugins/mill/scripts/_review_code.py:382`
  - `plugins/mill/scripts/_implementer_common.py:1187`
- `plugins/mill/templates/mill-agents.yaml` — canonical list of `effort:`-bearing
  aliases: `opusmedium`/`opus` (medium), `opushigh` (high), `opusmax` (max),
  `sonnetmedium`/`sonnet` (medium), `sonnethigh` (high), `sonnetmax` (max). `haiku`,
  `g25flash`, `g25pro`, `g3flash_preview` (and `_bulk` variants) carry no `effort` key.
- `plugins/mill/agents/mill-reviewer.md` and `mill-implementer.md` — base files.
  Existing invariant enforced by `test-agents-defs.py`: no `model:` key (model comes
  from the Agent tool call's `model` parameter, not agent-def frontmatter). The new
  tier files preserve this and additionally add `effort:`.
- Agent-mode dispatch is gated to the Claude provider only by
  `_agent_dispatch.resolve_dispatch_mode`; gemini-provider catalog entries always use
  subprocess/psmux dispatch and are untouched by this change.
- Only two `subagent_type` literals exist today (`mill:mill-implementer`,
  `mill:mill-reviewer`) per `mill-go/SKILL.md`'s "Why not fork?" note, which also
  confirms fixer and merge-in dispatches reuse `mill:mill-implementer` as an
  implementer-class role.

## Testing

- TDD candidate: `test-agents-defs.py`. Write the parametrized assertions for the 6
  new files first (they fail on missing files), then create the files to make them
  pass.
- No integration test: exercising an actual Agent-tool call with a materialized effort
  override and inspecting the resulting reasoning effort is outside what
  `integration_tests/` can observe (it drives real git/CLI, not the harness's internal
  Agent dispatch). Verification of the wiring itself happens via code read-through
  during code review of the `mill-go/SKILL.md` diff.

## Q&A log

- **Q:** Which fix direction should this task take — (1) per-effort-tier agent
  definition files with `mill-go` step 3 picking `subagent_type` by resolved effort, or
  (2) some other mechanism to thread `mill-agents.yaml`'s effort tier through? **A:**
  [auto-pick] Direction 1 (per-effort-tier agent files). **Why:** the brief already
  confirms the `effort:` frontmatter key is a real, harness-honored mechanism; no
  alternative mechanism was identified that doesn't require this same static-file
  approach, since the Agent tool has no `effort` parameter and no runtime-templated
  agent-definition path.
- **Q:** Does this task's scope cover implementer/fixer roles too, or reviewer only?
  **A:** [auto-pick] Both reviewer and implementer/fixer/merge-in roles. **Why:** the
  brief explicitly states "Same gap applies to mill-implementer.md for
  roles.implementer.model / roles.fixer.model tiers" — scoping to reviewer-only would
  leave half the documented gap unresolved.
- **Q:** Which effort tiers need dedicated agent-definition files — only the tiers
  actually present in `mill-agents.yaml` (medium/high/max), or all five Claude Code
  effort levels (low/medium/high/xhigh/max)? **A:** [auto-pick] Only medium/high/max.
  **Why:** no catalog entry in `mill-agents.yaml` sets `effort: low` or `effort: xhigh`
  explicitly; building unused tiers now is speculative (YAGNI). Aliases without an
  effort key keep the base file unchanged, which is not a regression.
- **Q:** What naming convention should the new agent-definition files use? **A:**
  [auto-pick] `mill-reviewer-<tier>.md` / `mill-implementer-<tier>.md`, flat under the
  existing `plugins/mill/agents/` directory. **Why:** mirrors the existing flat
  directory and `mill:mill-<role>` naming convention with a tier suffix; no subfolders
  exist today and introducing one would be an unrelated structural change.
- **Q:** In `mill-go` step 3, how should the subagent_type-selection logic handle an
  effort value that isn't medium/high/max (e.g. a future catalog addition)? **A:**
  [auto-pick] Fall back to the base agent file (session-default effort) and document it
  as a known gap for that value, rather than hard-failing the dispatch. **Why:** the
  fallback path can never regress below today's always-session-default behavior, so
  it's strictly safe; hard-failing would turn a future config edit into a
  dispatch-blocking error.
- **Q:** Should the new tier files' `description` field be updated to mention the tier
  (for operator legibility), or left identical to the base file? **A:** [auto-pick]
  Left identical — only `name` and `effort` differ from the base file. **Why:** minimal
  diff; no evidence agent descriptions are surfaced anywhere that would benefit from
  tier-specific text, and the filename itself already encodes the tier.
- **Q:** Should test coverage for the 6 new files be automated, or verified by manual
  read-through during review? **A:** [auto-pick] Automated — extend
  `test-agents-defs.py` with a parametrized check per new file. **Why:**
  `test-agents-defs.py` already covers exactly this surface (frontmatter invariants)
  for the two base files; extending it is near-zero marginal cost and catches
  copy-paste drift across 6 near-duplicate files that manual read-through could miss.
