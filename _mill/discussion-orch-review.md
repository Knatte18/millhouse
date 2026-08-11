# Orchestrator review: discussion.md (mill-go2-fork-implementer)

```yaml
reviewer: orchestrator (manual, ad-hoc)
reviewed_file: discussion.md
verdict: GAPS_FOUND
```

## Verification performed

Cross-checked every cited file:line reference and factual claim against actual source
in this worktree (task-worktree path, not `${CLAUDE_PLUGIN_ROOT}` cache):

- `mill-go-base/SKILL.md` lines 1-16 (Lean Builder role text), 1443-1449 (Lean Builder
  principle, including the exact "lets Opus be a legitimate Builder choice" quote),
  421-433 (`**Why not fork?**` paragraph, all three disqualifiers word-for-word), 572
  (`### 1. Implement` dispatch), 803-807 (`f"approved-{batch_name}"` precedent),
  217/389-393 (Agent-mode dispatch section bounds) — all confirmed accurate.
- `templates/implementer-brief.md:102` — Test Integrity Guardrail heading, confirmed.
- `_agent_dispatch.language_skills_directive` — confirmed exists at `:245`.
- `test-mill-go-variants.py` — confirmed exactly 7 `_check_*` functions (matches "seven
  variant-contract checks"), and `_check_variants_carry_no_machinery` /
  `_check_parameterization_lock` both exist as named.
- `mill-start/SKILL.md:179` and `mill-plan/SKILL.md:119` — both confirmed to cite the
  base's `Why not fork?` paragraph exactly as characterized (mill-start cites all three
  disqualifiers as inapplicable to its own Explore-phase fork use; mill-plan cites the
  tool-inheritance claim specifically).
- Disqualifier #3's factual-wrongness claim — independently confirmed:
  `--resume-incomplete` does re-run the prepare stage (re-writing the brief) per the
  base's own step 6.5.2 text, so "no on-disk brief... cannot be resumed" is indeed
  inaccurate for this design.
- Hub `mill-config.yaml`: `roles.implementer.model: sonnetmedium`,
  `roles.fixer.model: sonnetmedium` — differs from the base paragraph's cited
  `sonnethigh`/`haiku`, but the base text explicitly scopes those values to
  `plugins/mill/templates/mill-config.yaml` (the seed template, not this hub's live
  config), and this discussion's own Decision `model-and-effort-loss-is-documentation-only`
  correctly cites the hub's actual `sonnetmedium` value separately. No inconsistency.

Another unusually well-grounded document — no inaccurate citation or unsupported
factual claim found.

## Findings

### [GAP:consistency] Fork-fallback audit marker omits the sibling task's `_notify` call, unexplained

Decision `fork-fallback-status-marker` records a cold-fallback event with only a
committed `status.md` phase row (`_status.append_phase(..., f"fork-fallback-{batch_name}", ...)`)
— no `_notify.notify(...)` call.

The sibling task `mill-go2-fork-fixer`'s equivalent decision (`record-the-fallback`)
solves the identical problem — auditing the same experiment's most important
measurement, a dead fork — and explicitly does **both**: `_notify.notify(...)` for
live visibility plus a committed status row for durability. That discussion's own
rationale rejects `_notify`-only specifically because "lost once the session ends" —
but never argues the reverse (row-only, no `_notify`) is sufficient, which is exactly
what this discussion's decision does, with no stated rationale for dropping the
`_notify` half.

Since both tasks describe themselves as producing the experiment's key comparable
measurement (fork failure rate), an unexplained divergence in how that measurement is
surfaced makes the two roles harder to compare and monitor uniformly — a live-notify
signal exists for a dying forked fixer but not for a dying forked implementer, for no
stated reason.

**Suggested fix:** either add the `_notify.notify("<VARIANT_LABEL>.fork-fallback", ...)`
call for parity with the fixer task, or add one sentence to the decision's rationale
explaining why real-time notification is unnecessary specifically for the implementer
fallback case (e.g., if there's a structural reason — none is apparent from the
document as written).

## Non-blocking notes

- **Cross-task staleness (informational, not a defect in this file):** this task's
  Decision `correct-why-not-fork-in-base` edits the base's `Why not fork?` paragraph,
  including correcting disqualifier #3. The sibling `mill-go2-fork-fixer` discussion's
  Decision `no-base-edits` asserts "`Why not fork?`'s three disqualifiers remain
  accurate as written for the base" — that claim will become stale once this task
  lands, since disqualifier #3 will no longer read as originally quoted there. Not a
  problem mechanically (fixer never touches `mill-go-base/SKILL.md`, so no merge
  conflict is possible regardless of landing order), but worth knowing when the fixer
  task is eventually planned/implemented.
- The `f"fork-fallback-{batch_name}"` marker (no round number) is fine as-is: per
  Decision `cold-fallback-on-dead-fork`, at most one cold fallback can occur per batch
  for the implementer role, unlike the fixer's per-round fix dispatch — so the shapes'
  divergence on round-number inclusion is structurally justified, even though neither
  discussion states this explicitly. Flagging only the `_notify` omission above as an
  actual finding.
