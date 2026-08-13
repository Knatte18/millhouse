MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
duration_s: 325.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [BLOCKING:design] #827 escape-hatch rejection rests on a false premise
**Section:** Decisions / "Step 1.5 fix table... verify-full-suite" Rejected paragraph
**Issue:** Claims a `verify-full-suite` skip-check "requires new plumbing... wiring `--skip-check` through both Agent-mode and subprocess/psmux dispatch." Verified: `--skip-check` is a generic, repeatable argparse flag already wired into both `--stage prepare` (millpy-review-plan.py:220) and `--stage full` (line 327); `_check_wiki_config_mutation` itself (`_plan_validate.py:1283`) has no special code-level allowlist either — wiki-config-mutation's "escape hatch" is entirely SKILL.md-prose (the two-condition justification test), not extra script plumbing.
**Fix:** Correct the rationale — the only missing piece for a `verify-full-suite` escape hatch would be an analogous SKILL.md justification paragraph, not new CLI plumbing; re-decide whether to add one or keep the hard "never permitted" stance on accurate grounds.

### [BLOCKING:design] Testing section's "no unit-test surface" claim is false
**Section:** ## Testing
**Issue:** States "there is no unit-test surface in `plugins/mill/unit_tests/` that exercises SKILL.md content directly." `plugins/mill/unit_tests/test-skill-helper-drift.py` scans `SKILLS.rglob("SKILL.md")` (every SKILL.md, including mill-plan's) and asserts every `_<module>.<fn>(` prose reference resolves to a real shipped function — directly relevant since this task's fixes add/touch helper-reference prose (`_paths.resolve_main_worktree_root(...)`, `_status.append_phase(...)`, etc.).
**Fix:** Name this test explicitly in the Testing section as verification the implementer must run against the edited SKILL.md.

### [NIT:consistency] #815 Decision misnames its own target section
**Section:** Decisions / "New authoring guardrail... (#815)"
**Issue:** Says the new principle goes in "Phase: Plan... (~line 551-560)," but lines ~551-560 are inside `## Principles` (starts ~line 544), not `### Phase: Plan` (ends ~line 258) — confirmed by reading the file.
**Fix:** Say "## Principles" instead of "Phase: Plan"; the cited line numbers are already correct.

### [NIT:consistency] `_paths.py`'s own `resolve_hub_path` docstring carries the same mislabel
**Section:** Scope / Out — `_paths.py`'s `resolve_hub_path` docstring/behavior
**Issue:** Excludes fixing `_paths.py` itself, reasoning that only mill-plan's inline comment needs correcting. But `resolve_hub_path`'s own docstring reads "Return the hub directory (the main worktree, where mill-config.yaml lives)" — the same "main worktree" mislabel this task removes from mill-plan's comment, and the discussion's own Technical Context says this is empirically false in flat layouts. A docstring-only edit carries the same zero-ripple property the Rejected paragraph grants mill-plan's comment fix.
**Fix:** Either fold a docstring wording fix into scope, or note explicitly why the docstring is left inconsistent.

### [NIT:design] #832 re-entry doesn't specify how `N` is derived
**Section:** Decisions / "Max-rounds block: add a `blocked` re-entry row (#832)"
**Issue:** `_status.append_phase(status_path, f"plan-review-r{N+1}", ts)` needs `N` from somewhere on cold re-entry; the decision doesn't say whether to regex-parse it out of `blocked_reason` prose (fragile — two numbers appear in that string) or re-derive it via the file's own established `discover_round`-style scan.
**Fix:** State the derivation method explicitly (prefer scanning `reviews_dir`/status Timeline over parsing `blocked_reason` text).

## Verdict

REQUEST_CHANGES
Two BLOCKING findings rest on premises contradicted by the source; NITs are minor mislabels/ambiguity.
MILL_REVIEW_END
