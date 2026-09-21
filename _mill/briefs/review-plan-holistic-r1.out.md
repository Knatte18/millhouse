MILL_REVIEW_BEGIN
# Review: Monitor tool: persistent:true doesn''t exist, entry-gate waits break — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-21
```

## Findings

None. Verified against source:

- Both entry-gate wait sections' quoted anchor text (the "Call the `Monitor` tool..." bullet, the
  `TIMEOUT after <N>s...` sub-bullet, and the shallower-indented harness-stop bullet) matches
  `mill-plan/SKILL.md` lines 100/112/114 and `mill-go-base/SKILL.md` lines 207/218/220 verbatim,
  including the indentation delta (4-space `READY`/`TIMEOUT` sub-bullets vs. 2-space harness-stop
  bullet) the cards rely on for correct insertion nesting.
- `_phase_wait.build_wait_command`'s signature/docstring (`plugins/mill/scripts/_phase_wait.py`)
  confirms: no `pipeline.entry_wait_timeout_minutes` awareness (caller's job, matching the plan's
  choice to spell out re-arm bookkeeping in SKILL.md prose rather than a new helper), and that
  mill-plan's call carries `clean_tree_root`/`clean_tree_paths` while mill-go-base's does not — the
  re-arm calls in cards 1/2 correctly preserve that asymmetry.
- `plugins/mill/unit_tests/test-phase-wait.py` calls `build_wait_command`/`matches_wait_trigger`
  directly and never touches SKILL.md prose, confirming the "single batch, no verify:" Shared
  Decision's rationale.
- `harness-tool-contracts.md`'s current text and the discussion's ten issue numbers /
  `timeout_ms` 300000/3600000 figures match card 3's Requirements verbatim.
- Decision alignment: all three Shared Decisions (keep `persistent: true`; add the fourth
  outcome/re-arm branch; refresh the contracts doc) are implemented, none reverted or partially
  applied. Scope matches discussion's "In"/"Out" lists exactly — no drift.
- Batch Index DAG, `All Files Touched`, Moves (`none` everywhere, no Rename mechanic needed),
  and per-card Creates/Edits/Context/Requirements/Commit completeness all check out.

## Verdict

APPROVE
Plan is source-verified accurate, fully implements all three Shared Decisions, no BLOCKING gaps found.
MILL_REVIEW_END
