# Orchestrator review: discussion.md (mill-go2-fork-fixer)

```yaml
reviewer: orchestrator (manual, ad-hoc)
reviewed_file: discussion.md
verdict: GAPS_FOUND
```

## Verification performed

Cross-checked every cited file:line reference and factual claim in `discussion.md`
against the actual source in this worktree (task-worktree path, not
`${CLAUDE_PLUGIN_ROOT}` cache), not just read for internal coherence:

- `mill-go2/SKILL.md`, `mill-go/SKILL.md` — 28 lines / 804 bytes each, both variant
  binding + `(none)`/`(none)` sections, confirmed exact.
- `mill-go-base/SKILL.md` — 1481 lines total; Override point A (~239-242), Override
  point B (~28-33), all four fixer dispatch sites (:791, :813, :1239, :1261) with their
  `--args` shapes, `scope_violations` note (:1375), implementer-only `incomplete`
  recovery (:353), `Why not fork?` (:423) — all confirmed accurate, line numbers within
  1-2 lines of cited values.
- `test-mill-go-variants.py` — 4096-byte cap, `MACHINERY_LITERALS`/`MILL_GO_LITERALS`
  banned-string lists, "seven variant-contract checks" docstring — all confirmed
  verbatim.
- `_implementer_common.py` `emit_prepare` — `SUBAGENT_IMPLEMENTER` hardcode and `role`
  field, confirmed at cited lines.
- `millpy-fix.py` — literal `"fix"` role passed to `emit_prepare`, confirmed at :653.
- `mill-implementer.md` / `mill-reviewer.md` agent frontmatter — tool grants
  (`Read,Edit,Write,Bash,Grep,Glob,Skill` vs `Read,Grep,Glob,Write`) confirmed exactly
  as characterized.
- Byte-budget arithmetic (804 + ~1300 fixer + ~1900-2100 sibling ≈ 4096 cap) is
  internally consistent, not just asserted.
- `harness-tool-contracts.md` — confirms the generic Agent-tool notification/`agentId`
  contract this task's fallback logic depends on; it does not single out `fork`
  specifically as one of the live-spiked cases, so "a fork delivers identically to a
  cold `Agent()` call" is a reasonable mechanical inference (same tool, same notify
  pipe), not an independently spike-confirmed fact. Not blocking — noted for the record.

No inaccurate citation or unsupported factual claim found anywhere in the document.
This is an unusually well-grounded discussion.md.

## Findings

### [GAP:scope] Parent task's context-growth open question is dropped silently

The wiki proposal this task was spawned from listed three open questions. Two get an
explicit `Decision` here (`driver-model-guardrail-is-documentation-only` answers the
config-key question; "What is unchanged by forking" answers the fallback-contract
question). The third — *"does the driver session need to periodically re-fork/reset
itself to avoid unbounded context growth across many batches, since the driver is
long-lived across the whole task while Webster's forks are per-batch?"* — is never
mentioned anywhere in this file: not decided, not scoped out, not deferred.

Given every other inherited open question got a formal resolution, the silence here
reads as an oversight rather than a considered "out of scope." A discussion.md must be
consumable by `mill-plan` with zero conversation history — right now a cold reader has
no way to tell whether this was considered and intentionally dropped, or simply missed.

**Suggested fix:** add one line — either a `Decision` entry ("no mitigation in this
task; context growth is an observational question for the running experiment, not a
mechanical one this task's scope addresses") or a bullet under `Scope`'s `Out` list —
so the omission is legible as a choice.

## Non-blocking notes

- The fork/cold-fallback equivalence claim (see Verification above) rests on a
  reasonable inference rather than a spike-confirmed fact for `subagent_type: "fork"`
  specifically. Fine to proceed; flag if `/mill-go2` runs ever show fork notifications
  behaving differently than a cold dispatch.
