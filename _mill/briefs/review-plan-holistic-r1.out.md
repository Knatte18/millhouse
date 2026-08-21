MILL_REVIEW_BEGIN
# Review: mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-08-21
```

## Findings

### [BLOCKING:design] Card 4's hub-config insertion anchor doesn't match the real file's key order
**Location:** batch 02-baseline-build-once-step / Card 4, second edit target (`mill-config.yaml`)
**Issue:** Card 4 says to insert the new key "immediately after `done_gate_baseline_preflight: false`, before `max_cards_per_batch: 10`" for BOTH files. That order is true in `plugins/mill/templates/mill-config.yaml` (lines 123-124), but this hub's own `mill-config.yaml` has the reverse order: `max_cards_per_batch: 10` at line 17, `done_gate_baseline_preflight: false` at line 23 — there is no "before `max_cards_per_batch`" position after `done_gate_baseline_preflight` in this file.
**Fix:** For the hub-config edit, drop the false "before `max_cards_per_batch`" anchor and just say "immediately after `done_gate_baseline_preflight: false` " (or "anywhere in the `pipeline:` block" since position has no functional effect).

### [NIT:consistency] Card 6's check_bg_status parse instruction drops the tuple-shape clarification the pattern it mirrors states explicitly
**Location:** batch 03-baseline-dispatch-background-skill / Card 6a and 6d
**Issue:** `_bg.check_bg_status` returns `tuple[str, int | None]`; `mill-start/SKILL.md`'s existing call site (the pattern Card 6 explicitly claims to reuse) spells this out — "Parse the JSON result as `(status, pid_or_code)` and branch: ...". Card 6's new text for both "0.5" and "0.6" instead says "Parse the JSON result and branch: ..." with no shape clarification, dropping precision relative to the source pattern it's copying verbatim (the `python -c` one-liner is byte-identical to mill-start's).
**Fix:** Match mill-start's wording exactly — add "as `(status, pid_or_code)`" to both new parse instructions.

## Verdict

REQUEST_CHANGES
Card 4's hub-config anchor is factually wrong against the actual file; everything else verified accurate against source.
MILL_REVIEW_END
