I have verified all load-bearing claims. Line references (`_run_verify_gates:642`, `nits_only` guard docstring `894-899`, `millpy-implement.py:81-84/266/295/515`, `millpy-fix.py:319/384` + `args.nits_only`, `_render.render:56` flat substitution, template sentences at the cited lines, mill-go SKILL `:125/129/156/158/161`, mill-receiving-review/mill-start/mill-plan wording, `strip_all_in_worktree` vestigial `junctions_cfg`) are all accurate. I found one genuine tension worth flagging around the #587/#595 test surface.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [GAP] Probe test plan targets a nonexistent Python surface
**Section:** Testing (§ line 95) vs Constraints (§ line 89)
**Issue:** Line 95 prescribes concrete `test-agent-mode-dispatch.py` cases that "stub `TaskOutput` ... assert no re-dispatch / assert transient path fires," but that suite only tests the prepare→finalize CLI round-trip (verified: `test-agent-mode-dispatch.py:1-11`, no harness/Agent/TaskOutput mocking); step-4's stopped/interrupted classification lives entirely in `mill-go/SKILL.md` prose with no Python function to stub against, and Scope In authorizes no new classification helper — yet Constraints line 89 also assumes a testable "surrounding classification logic ... with a mocked/stubbed probe result."
**Fix:** State explicitly whether the probe path is prose-only (no unit tests, manual-reasoning validation per line 89) or whether a new Python classification surface is in scope to make line 95's stub cases implementable — the two sections currently prescribe an untestable-as-written thing.

## Verdict

GAPS_FOUND
One self-contradictory testing prescription for the #587/#595 probe; everything else verified sound.
MILL_REVIEW_END