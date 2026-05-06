# Review: 8 (A) — Disable per-batch reviews (config-driven) — 02-config-docs

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 02-config-docs
date: 2026-05-06
```

## Findings

### [NIT] Card 4 Edit A: template's batch line lacks comment — "identical edits" claim is wrong
**Step:** Card 4 — Edit A
**Issue:** Plan states both files currently have `batch: sonnetmax            # per-batch reviewer; MODE must be "bulk"`, but `wiki-config.yaml` actually has `batch: sonnetmax` with no comment. The "apply identical edits to both files" framing is false — the edit on the template is a fresh comment addition, not an append.
**Fix:** Describe the two edits separately: for `wiki-config.yaml`, the old line is `batch: sonnetmax` and the new line is `batch: sonnetmax            # per-batch reviewer; MODE must be "bulk". null = skip per-batch (holistic must be set)`.

### [NIT] Card 4 Edit B: "current lines" description mismatches both files
**Step:** Card 4 — Edit B
**Issue:** Plan's "current lines" show `self_fix_rounds: 2` (no comment), but `wiki/config.yaml` has `self_fix_rounds: 2          # how many times the implementer self-fixes...`. Symmetrically, the plan includes a comment on `holistic: true` that is absent in `wiki-config.yaml`. An exact-string match would fail on at least one file per edit.
**Fix:** Show the actual lines from each file separately; the intent (insert `per_batch: true` between `holistic` and `self_fix_rounds`) is unambiguous once described per-file.

## Verdict

APPROVE  
Two doc-precision NITs only; functional requirements, decisions, and back-compat are correct.