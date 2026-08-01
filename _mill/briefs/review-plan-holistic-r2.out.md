MILL_REVIEW_BEGIN
# Review: Non-interactive pipeline: only mill-start's interview may prompt the operator — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (Sonnet 5, per harness metadata)
reviewed_file: plan/
date: 2026-08-01
```

## Findings

### [BLOCKING] Card 7 Context omits `_review_common.py`
**Location:** Batch 4 (mill-go-handoff-gates), Card 7
**Issue:** Requirements names `_review_common.RE_SIMPLE`/`RE_BATCH` as the exact matching constants the new prose must mirror (including the "anchored at the filename start" and unanchored-glob-pitfall claims), but Context lists only `plugins/mill/scripts/_nit_gate.py` — `_review_common.py` is absent from both `Context:` and `Edits:`.
**Fix:** Add `plugins/mill/scripts/_review_common.py` to Card 7's `Context:` list so the implementer can verify the regex anchoring claim against the actual definitions rather than trusting the plan's paraphrase.

### [BLOCKING] Card 11 Context omits `_parent_branch.py`
**Location:** Batch 5 (mill-merge-self-resolve), Card 11
**Issue:** The replacement text introduces a brand-new claim — `_parent_branch.ParentBranchError` fires specifically when "status.md is missing the `parent:` row" — that does not appear anywhere in the current SKILL.md text being edited, yet Card 11's `Context:` is `none` and `_parent_branch.py` is not in `Edits:` either. The Batch Tests section says this was "confirmed during Phase: Plan by reading `_parent_branch.resolve`'s signature and body," but that confirmation doesn't carry over to the implementer's own cold-start read set.
**Fix:** Add `plugins/mill/scripts/_parent_branch.py` to Card 11's `Context:` list.

### [BLOCKING] Cards 8 & 9 self-resolve actions skip the audit-trail decision
**Location:** Batch 4 (mill-go-handoff-gates), Cards 8 and 9
**Issue:** Shared Decision `audit-trail-via-status-timeline` requires "every self-resolve action" to append a `_status.append_phase(...)`-style row to status.md's timeline, and explicitly lists `mill-go-handoff-gates` under "Applies to." Card 8's self-resolve (auto-commit of in-scope dirt) and Card 9's self-resolve (auto-commit/auto-clean of scope-violation paths) each `git commit` directly with no corresponding `_status.append_phase` call — unlike Cards 2/3's self-resolve bullets, which route through the existing implement/fix dispatch machinery that already writes status.md on its own. Card 7 is fine (the dispatched NIT-fix pass already writes a `nits-fixed-<scope>` row per the existing "Manual recovery note" paragraph); Cards 8/9 have no equivalent existing writer.
**Fix:** Add a `_status.append_phase(status_path, "<short-reason>", timestamp)` call (e.g. `"self-resolved-terminal-dirt"` / `"self-resolved-scope-violation"`) to each of Card 8's and Card 9's self-resolve git-commit steps, folded into the same commit that already stages the changes.

### [NIT] Shared Decision text overstates batch 4's mechanism
**Location:** `00-overview.md` Shared Decision `unconditional-default-not-a-flag`
**Issue:** The decision states "Every edit in batches 1-4 removes an `if pipeline.autonomous_mode: true` ... gate ... rather than adding any new gate," but Batch 4's own Batch Scope correctly says its three Handoff gates have "NO existing autonomous-mode branch at all" and get genuinely new self-resolve logic — batch 4 doesn't fit the decision's own summary.
**Fix:** Narrow the decision's wording to "batches 1-3" for the gate-removal claim, or add a caveat noting batch 4 adds new self-resolve logic where no prior gate existed.

## Verdict

REQUEST_CHANGES
Two Context-completeness gaps (Cards 7, 11) and a missing audit-trail append_phase in Cards 8/9 need fixing.
MILL_REVIEW_END
