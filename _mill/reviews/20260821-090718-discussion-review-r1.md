MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs

```yaml
duration_s: 315.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; harness-reported model id "claude-sonnet-5")
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [NIT:consistency] #895 default grace window contradicts its own stated purpose
**Demoted-from:** BLOCKING
**Section:** Decision #895, config-default parenthetical. **Issue:** The decided default `pipeline.entry_wait_blocked_grace_s ~20s` is explicitly documented as "far short of the ~3-minute transient window in the reported repro" — the exact real-world scenario the fix was added to solve. The Rejected alternative ("fixed re-check-once") is dismissed specifically because "the actual reported repro's ~3-minute window would still false-halt under this option," but with the chosen 20s default the decided design ALSO still false-halts on that identical repro — no functional improvement over the rejected alternative for the motivating case, out of the box. **Fix:** Either raise the default to comfortably exceed the reported ~3-minute window, or explicitly state the default is intentionally conservative and that repos with a known longer transient window must set `entry_wait_blocked_grace_s` in `config.local.yaml`/hub config — the discussion currently asserts neither, leaving the default's adequacy internally contradictory.

### [NIT:consistency] Technical Context misattributes `_compute_transitive_ancestors`
**Section:** Technical context, `_plan_dag.py` bullet. **Issue:** Lists `_compute_transitive_ancestors` as belonging to `_plan_dag.py`; verified it is defined only in `_plan_validate.py` (line 985, used by `_check_parallel_modifies_overlap`) — `_plan_dag.py` has no such function or import. The #887 Decision text itself correctly attributes it (implicitly, via "already defined and used by the existing `_check_parallel_modifies_overlap` check"), so only the Technical Context bullet is wrong. **Fix:** Move `_compute_transitive_ancestors` to the `_plan_validate.py` parenthetical list.

### [NIT:consistency] #877 rationale's grep claim is inaccurate
**Section:** Decision #877, rationale. **Issue:** States "grepped for 'same commit'/'amend'/'atomic': zero hits" — verified there is one incidental hit for "same commit" in the file (Entry-gate wait section, referring to phase-transition commit coupling, unrelated to cross-card commits); "amend"/"atomic" do have zero hits. The substantive conclusion (no existing cross-card same-commit rule) still holds, but the stated grep result is not literally accurate. **Fix:** Reword to "no existing rule governing cross-card commit merging" rather than asserting a literal zero-hit grep across all three terms.

### [NIT:design] #877 rationale rests on an unverified "no-amend policy"
**Section:** Decision #877, rationale. **Issue:** Cites "the harness's no-amend policy" as an established fact justifying the new Principles rule; grepped the repo and found no documented policy by that name anywhere. The underlying one-commit-per-card convention is independently confirmed (`mill-go-base/SKILL.md` line 871, "every per-card commit invokes the `git-commit` skill"), which alone is sufficient to justify the rule. **Fix:** Either cite the actual source establishing the no-amend constraint, or drop the "no-amend policy" framing and rely solely on the confirmed per-card-commit structure.

### [NIT:design] #887's "general_refs" description over-includes Creates:
**Section:** Decision #887. **Issue:** Says the check should scan "B's Context:/Edits: refs (the same general_refs set `_check_non_existent_path` already computes)" — but the actual `general_refs` in `_check_non_existent_path` is `Context+Edits+Creates` (via `parse_batch_refs`'s default fields) minus Deletes, not Context+Edits only. A literal reuse of that variable would also scan batch B's own Creates: tokens against other batches' Creates: sets, which is outside the described intent. **Fix:** Clarify the implementer should compute `_parse_context_only(path) | _parse_edits_only(path)` directly rather than reusing `general_refs` verbatim.

## Verdict

APPROVE
One BLOCKING: #895's default grace window doesn't cover the repro it was designed to fix.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
