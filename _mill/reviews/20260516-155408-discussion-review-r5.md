I have all the evidence needed. Writing the review now.

# Review: 57 (A) — Move config.yaml and agents.yaml from wiki to hub worktree

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-16
```

## Findings

### [GAP] mill-setup Phase 4.95 unaddressed in machine-layer removal
**Section:** Decision: Overlay precedence — Scope effects of the removal
**Issue:** The scope effects list removing `_machine.load_layer()` from `_config.py` and `_review_common.py` and conditionally deleting `_machine.py`, but `mill-setup/SKILL.md` Phase 4.95 imports `_machine` and calls `_machine.probe()` and `_machine.machine_config_path()` — two callers that survive the listed removals. Phase 4.95 also references the to-be-deleted `plugins/mill/templates/config.machine.yaml` in its output message. After this task: `_machine.py` cannot be deleted (remaining callers), the machine template deletion breaks Phase 4.95's message, and Phase 4.95 would keep telling operators to configure a layer that no longer works. The discussion gives no instruction on whether Phase 4.95 should be removed, updated to say the machine config is deprecated, or left as-is.
**Fix:** Add a scope effect decision for Phase 4.95: state whether it is removed (enabling `_machine.py` deletion) or updated to say the machine config layer is no longer operative, and whether `test-machine.py` is also removed if `_machine.py` goes.

### [NOTE] "Out" section has inaccurate reasoning on autonomous_mode callsites
**Section:** Scope — Out
**Issue:** "no production code currently reads cfg['pipeline']['autonomous_mode']" — verified false; `mill-autofix/SKILL.md:124`, `mill-go/SKILL.md:232`, and `mill-plan/SKILL.md:153,155` are all live callers. The correct reasoning (these callers keep working through the intermediate state because mill-autofix still writes the key and validation is warn-only) is given in Technical Context, but the Out section's misstated rationale could mislead a plan writer who reads it in isolation.
**Fix:** Update the Out section to say the key has callsites in SKILL.md files that remain functional through the intermediate state, with the follow-up migration scope noted.

## Verdict

GAPS_FOUND
mill-setup Phase 4.95 and its `_machine` dependency are outside the stated removal scope, leaving `_machine.py` undeletable and the machine template deletion broken.