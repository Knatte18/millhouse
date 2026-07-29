MILL_REVIEW_BEGIN
# Review: mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] context-completeness will flag literal "do-not-touch" filename mentions
**Location:** Batch 01 Card 1 (`_check_context_completeness` design) / Batch 02 Card 3 (concrete trigger)
**Issue:** Card 3's Requirements prose reads "forbid touching `plan_dir`, `status_path`, or any `` `mill-config.yaml` ``/`` `config.local.yaml` ``". `mill-config.yaml` is path-shaped (`.yaml` ext) and independently resolvable (a top-level `mill-config.yaml` exists in this repo), so Batch 01's new check will flag Card 3 for referencing a file absent from its own `Context:`/`Edits:` — even though the reference is a prohibition ("never touch this"), not a read dependency. Card 6's mechanical fix ("add to Context:") would then be actively wrong. This is exactly the false-positive class the Shared Decision claims resolvability eliminates ("eliminates the false-positive class... at the source"), yet resolvability alone can't distinguish "reference to read" from "reference to avoid mutating" — this plan's own Card 3 is a live counter-example.
**Fix:** Either exempt tokens inside a documented "forbid/never touch/must not edit" prose pattern, or narrow the heuristic further (e.g. only fire when the token appears in a sentence naming an action the implementer performs on it, not a prohibition list), and add a regression test for this exact "prohibited filename, not a read dependency" case.

### [NIT] Card 1's insertion-point line number is off by one
**Location:** Batch 01 Card 1
**Issue:** Card 1 says to place the new function "before the `# Check 8 — all-files-touched-mismatch` section comment at line 1360" — line 1360 in `_plan_validate.py` is the `# ---` separator; the actual `# Check 8 — ...` comment text is at line 1361. The "after `_check_plugin_manifest_context_missing`'s `return errors` at line 1357" anchor is still correct and unambiguous.
**Fix:** Correct the cited line to 1361 (or drop the number and rely on the section-comment text, which is unambiguous either way).

### [NIT] Line-range-suffixed backtick tokens silently evade context-completeness
**Location:** Batch 01 Card 1
**Issue:** The check tests resolvability on the raw backtick token without stripping a `:NN-NN` line-range suffix (the module already defines `_RE_LINE_RANGE` for exactly this pattern, used elsewhere). A genuinely-missing-context reference written in this codebase's own common style — e.g. Card 2's own `` `plugins/mill/unit_tests/test-plan-validate.py:93-155` `` — fails to resolve as a file and is silently skipped, producing a false negative for a citation style this very plan uses.
**Fix:** Strip `_RE_LINE_RANGE` from the token before calling `resolve_existing_paths`/matching against the combined set, mirroring how the module already treats line-range suffixes elsewhere.

## Verdict

REQUEST_CHANGES
The new check's resolvability heuristic false-positives on Batch 02's own "forbid touching mill-config.yaml" prose.
MILL_REVIEW_END
