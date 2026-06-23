MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-23
```

## Findings

### [BLOCKING] Card 4 Context omits `_timestamp.py`
**Location:** batch 2 (nit-enforcement) / card 4
**Issue:** Requirements item 3 names `_timestamp.now_utc_iso()` (and the call is added inside `_implementer_common._forward_output`), but `_timestamp.py` is in neither `Context:` nor `Edits:` — the implementer would cold-start on the timestamp helper, violating Context-completeness.
**Fix:** Add `plugins/mill/scripts/_timestamp.py` to card 4's `Context:`.

### [NIT] Card 5 `_status` timeline-read helper unnamed
**Location:** batch 2 / card 5
**Issue:** Requirements says "read status rows via `_status` helpers; do not hand-parse the YAML block" but never names the specific helper. The only timeline accessor is `_status.read_full(status_path)["timeline"]` (there is no row-iterator API); leaving it generic invites the implementer to reach for a nonexistent function.
**Fix:** Name `_status.read_full` (and that timeline rows are `"<phase>  <timestamp>"` strings) so the parse target is explicit.

### [NIT] Card 4 leaves `nits_scope` shape ambiguous
**Location:** batch 2 / card 4
**Issue:** Item 3 offers two alternative shapes ("derive scope from a new `nits_scope` param OR pass the formatted marker label") and item 4 separately states `nits_scope = args.batch_name if args.scope=="batch" else "holistic"`; the marker-label is `nits-fixed-<nits_scope>`. The dual-option phrasing weakens the otherwise-precise contract.
**Fix:** Commit to the single `nits_scope: str | None = None` param shape and drop the "OR" alternative.

### [NIT] Card 9 verify-content-check is "if practical", not a card
**Location:** batch 3 / card 10 + Batch Tests
**Issue:** The fixer-brief unsatisfiable-demand instruction (card 9) is prose-only; the Batch Tests note that card 10 asserts brief content "if practical." Since the briefs are templates with stable text, this is mechanically testable and should not be optional.
**Fix:** Make the brief-content assertion a firm requirement in card 10, or accept it stays plan-reviewer-validated and drop the "if practical" hedge.

## Verdict

REQUEST_CHANGES
One Context-completeness gap (card 4 / `_timestamp.py`) is blocking; remaining items are nits.
MILL_REVIEW_END
