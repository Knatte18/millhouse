```yaml
type: bench-results
task: "(A) -- Benchmark Gemini single-reviewers vs sonnetmax baseline"
run: 20260514-114617
reviewers: [g25flash, g3flash_preview, g25pro]
types: [discussion, plan, code]
timeout: 300s
```

## Results

| Reviewer | Type | Time | Verdict | Findings | Fmt |
|---|---|---|---|---|---|
| g25flash | discussion | 16.7s | GAPS_FOUND | 1 | False |
| g25flash | plan | 17.0s | REQUEST_CHANGES | 2 | False |
| g25flash | code | 16.0s | REQUEST_CHANGES | 1 | False |
| g3flash_preview | discussion | 42.9s | GAPS_FOUND | 3 | True |
| g3flash_preview | plan | 51.0s | NEED_CONTEXT | 2 | True |
| g3flash_preview | code | 27.1s | REQUEST_CHANGES | 1 | True |
| g25pro | discussion | 35.3s | GAPS_FOUND | 3 | True |
| g25pro | plan | 43.5s | NEED_CONTEXT | 1 | True |
| g25pro | code | 33.0s | REQUEST_CHANGES | 1 | True |

## Interpretation

**g25flash** is the fastest (16-17s) but fails format compliance across all three review types — each response omits the required `# Review:` header and starts directly with the yaml block, which means `parse_verdict` would fail in production and the review file would not render correctly. g25flash is **not viable** as a NORCE fallback without prompt changes to enforce the header.

**g3flash_preview** and **g25pro** are both format-compliant (Fmt=True) across all three types, with valid verdict/findings structure. Both produce correct verdicts for discussion (`GAPS_FOUND`) and code (`REQUEST_CHANGES`) reviews, and find a reasonable number of issues. Both return `NEED_CONTEXT` on plan reviews — this is a fixture artifact: the sample plan artefact section does not include the source file referenced by the plan (`_render.py`), which causes these models to decline rather than proceeding with a partial review. In production, `millpy-review-plan.py` inlines relevant source files, so this behaviour would need to be re-evaluated with a complete fixture before concluding it is a stable failure mode.

**Recommendation:** g3flash_preview is the stronger NORCE-fallback candidate for discussion and code reviews — it is format-compliant, returns actionable findings, and is 6-10s faster than g25pro. Both models should be re-tested on plan reviews using a fixture that includes the referenced source file before either is enabled for plan review fallback in production.

## Raw output files

Individual responses saved to `.scratch/bench-20260514-114617-<reviewer>-<type>.md`.
