# Discussion: (A) — Benchmark Gemini single-reviewers vs sonnetmax baseline

```yaml
task: (A) -- Benchmark Gemini single-reviewers vs sonnetmax baseline
slug: bench-gemini-single-reviewers
status: discussing
parent: main
```

## Problem

Issue #278 surfaced a failure mode in the current review setup: on a 169 KTok bulk prompt (43 files, mill-paths-cleanup task), both Sonnet medium and Sonnet max drifted into implementer voice on holistic code review. The default sonnetmax reviewer is calibrated for normal-size tasks (5-10 files); large refactors break the role boundary.

The natural fallback would be Gemini cluster, but the NORCE laptop cannot use it -- cache servers are behind a firewall. That leaves Gemini single-reviewers as the candidate fallback. The existing `g25flash` reviewer is already in the registry but is documented as "proven uforutsigbar" (unpredictable). We need empirical data: are Gemini GA single-reviewers actually usable, and if so, which one?

This task builds a benchmark harness, adds `g3flash_preview` and `g25pro` to the registry, and runs both against the existing `g25flash` to determine whether either is a viable fallback for large-prompt reviews. `gemini-3-flash-preview` ("3 Flash Preview") is the primary Flash-tier candidate; `gemini-2.5-pro` is the Pro-tier candidate.

## Scope

**In:**
- Add `g3flash_preview`, `g3flash_preview_tool`, `g25pro`, and `g25pro_tool` reviewer entries to `wiki/reviewers.yaml`
- Build `plugins/mill/integration_tests/bench-reviewers.py` -- a benchmark runner script
- Create a small code-review fixture at `plugins/mill/integration_tests/fixtures/sample-code.py`
- Run the full benchmark (g25flash + g3flash_preview + g25pro across discussion/plan/code review types)
- Write results to `.scratch/bench-<timestamp>.md`

**Out:**
- Gemini 3.1-pro-preview, gemini-3.1-flash-lite-preview, gemini-2.5-flash-lite -- all accessible but not mentioned in the task; keeping scope tight to the two named candidates
- Gemini cluster reviewer -- blocked on NORCE by firewall; orthogonal to this task
- Claude / sonnetmax runs in the benchmark script -- baseline is already known from daily use; running it adds cost with no benefit
- Automated LLM-as-judge scoring -- too expensive and adds a confounding variable
- Statistical variance / multiple runs per configuration -- this is a qualitative benchmark; 1 run per config is sufficient
- Changes to the review pipeline itself -- observation only

## Decisions

### model-scope

- Decision: Benchmark g25flash (gemini-2.5-flash), g3flash_preview (gemini-3-flash-preview), and g25pro (gemini-2.5-pro).
- Rationale: `gemini-3-flash-preview` is the "3 Flash Preview" model from the task description; it is accessible through the current gemini CLI (model ID confirmed by testing). `gemini-2.5-pro` is the Pro-tier candidate. `gemini-2.5-flash` (g25flash) serves as the existing Flash-tier baseline that is known to be unstable, giving a comparison point for g3flash_preview. Note: initial exploration guessed wrong model IDs (gemini-3-flash, gemini-3.0-flash) which failed; the correct ID gemini-3-flash-preview was found from the CLI interactive model menu.
- Additional models discovered but excluded to keep scope tight: gemini-3.1-pro-preview, gemini-3.1-flash-lite-preview, gemini-2.5-flash-lite. Accessible but not in the task description.
- Rejected: Including all 6 available models -- too expensive; benchmark would lose focus.

### script-location

- Decision: `plugins/mill/integration_tests/bench-reviewers.py`
- Rationale: Sits alongside other integration tests; shares the `fixtures/` directory; runs from the hub root with the same `uv run` invocation pattern.
- Rejected: A separate `bench/` directory -- no benefit, unnecessary new top-level directory.

### test-corpus

- Decision: Use `integration_tests/fixtures/sample-discussion.md` for discussion reviews, `integration_tests/fixtures/sample-plan/` for plan reviews, and a new `fixtures/sample-code.py` for code reviews.
- Rationale: Zero setup cost; reproducible; already in the repo. The existing fixtures were written for the review integration tests so they are a realistic but controlled input.
- Rejected: Materialising the 169 KTok prompt from issue #278 -- requires a full pipeline run; would make the bench script expensive to run and slow to iterate on.

### quality-metric

- Decision: Format compliance + finding count. No automated quality scoring.
- Format compliance = response starts with `# Review:`, contains a fenced yaml block with a `verdict:` field, and ends with a `## Verdict` section.
- Finding count = number of `### [GAP]`, `### [BLOCKING]`, or `### [NIT]` headings in the response.
- Rationale: Both metrics are objective and require no additional LLM calls. Format compliance catches role drift (an implementer response would not match). Finding count gives a proxy for reviewer depth.
- Rejected: LLM-as-judge -- adds another model's cost and introduces a new variable into what should be a simple measurement.

### timeout

- Decision: 300s per reviewer call.
- Rationale: Trial run showed g25flash timed out at 120s on a ~1900-token prompt (run 1 TIMEOUT; run 2 returned in 61s). 300s gives headroom for slow responses without blocking the loop for too long on hangs.
- Rejected: 120s -- known to be too short for g25flash. 600s -- over-generous, delays results if a model hangs.

### sonnetmax-baseline

- Decision: Do NOT run sonnetmax in the benchmark script. Reference existing review quality from daily use as the baseline. The relevant baseline is `sonnetmax` (bulk mode), not `sonnetmax_tool`.
- Rationale: User explicitly flagged Gemini per-token cost; Claude API is also billed. The sonnetmax baseline quality is already well-understood. Critically, the comparison must be apples-to-apples: Gemini reviewers run in bulk mode, so the comparison baseline is `sonnetmax` (bulk), not `sonnetmax_tool` (which has tool-reading capability and would be an unfair advantage). `sonnetmax_tool` is used for discussion-review role in daily config but is not representative for this benchmark's purpose.
- Rejected: Running sonnetmax_tool in the script -- unfair comparison (extra capability); running sonnetmax in bulk -- doubles billing with limited benefit since the baseline quality is already known.

### registry-additions

- Decision: Add `g3flash_preview` (bulk), `g3flash_preview_tool` (tool-use), `g25pro` (bulk), and `g25pro_tool` (tool-use) to `wiki/reviewers.yaml`. No effort field -- gemini CLI ignores it.
- Rationale: Mirrors the existing `g25flash` / `g25flash_tool` pair. Bulk variants are the benchmark targets; tool-use variants are added for completeness so operators can assign them to review roles.
- Rejected: Only bulk variants without `_tool` -- asymmetric with the existing Flash pair; reviewers.yaml already has the pattern.

## Technical context

### Reviewer dispatch stack

The 4-layer architecture:
```
bench-reviewers.py
  -> _reviewers.load(wiki_path) + resolve(registry, name)   # get spec
  -> _reviewer_single.run(spec, prompt_text)                 # dispatch
  -> _llm_gemini.run_bulk(prompt_text, model=..., timeout=...) # invoke CLI
```

`_reviewers.resolve()` returns a flat spec dict: `{type, provider, model, tooluse, ...}`. The bench script passes this to `_reviewer_single.run()`, which picks `run_bulk` or `run_tool_use` based on `spec["tooluse"]`.

### Prompt rendering

Templates live in `plugins/mill/templates/`. `_render.render(template_path, values)` substitutes `<TOKEN>` placeholders. The bench script renders:
- `review-discussion.md` with TASK_TITLE, ROUND, REVIEWER_MODEL, TOOL_RULE, ARTEFACT_SECTION, CONSTRAINTS
- `review-plan-holistic.md` with the plan overview content
- `review-code-holistic.md` with bulked file content

`TOOL_RULE` is either a bulk-mode disclaimer or a tool-use instruction -- see `_review_common.build_tool_rule()`.

### Verdict and finding parsing

`_review_common.parse_verdict(text)` extracts APPROVE / GAPS_FOUND / REQUEST_CHANGES from a fenced yaml block.
`_review_common.parse_blocking_count(raw_output, *, severity)` counts `### [<severity>]` headings for a single severity per call. The bench script calls it once per applicable severity (GAP/BLOCKING/NIT depending on review type) and sums the results to produce a total finding count.

Both are already tested in the review integration tests. The bench script reuses them directly.

### Existing fixtures

- `plugins/mill/integration_tests/fixtures/sample-discussion.md` -- ~7600 chars, ~1900 tokens. Used as the discussion artefact. This is the document both trial runs reviewed.
- `plugins/mill/integration_tests/fixtures/sample-plan/` -- `00-overview.md` + `01-core.md`. Used as the plan artefact for plan-holistic review.
- `plugins/mill/integration_tests/fixtures/sample-code.py` (NEW) -- a small Python snippet (~50 lines) used as the code artefact. Needs to be created. Content: a realistic but simple helper function with a mild bug or style issue that a reviewer should catch.

### Preliminary trial results

Trial runs conducted during mill-start (sample-discussion.md, ~1910 tokens, bulk mode):

| Reviewer | Model | Run | Wall-clock | Verdict | Findings | Format OK |
|----------|-------|-----|-----------|---------|----------|-----------|
| g25flash | gemini-2.5-flash | 1 | TIMEOUT >120s | - | - | - |
| g25flash | gemini-2.5-flash | 2 | 61s | GAPS_FOUND | 1 | Yes |
| g25pro | gemini-2.5-pro | 1 | 37s | GAPS_FOUND | 1 | Yes |
| g3flash_preview | gemini-3-flash-preview | 1 | 17s | GAPS_FOUND | 1 | Yes |

Observations:
- g25flash is unstable: timed out on the first call to a 1900-token prompt, then succeeded in 61s on retry. This confirms the "proven uforutsigbar" characterisation.
- g25pro is stable: returned correctly in 37s. Format compliant, sensible finding.
- g3flash_preview is the fastest: returned in 17s. Format compliant, GAPS_FOUND with a specific finding. More stable than g25flash in this trial.
- All produce format-compliant output when they return.
- The 120s default timeout in `_llm_gemini.run_bulk` is insufficient for g25flash; the bench script uses 300s.

### New `reviewers.yaml` entries

```yaml
g3flash_preview:
  type: single
  provider: gemini
  model: gemini-3-flash-preview

g3flash_preview_tool:
  type: single
  provider: gemini
  model: gemini-3-flash-preview
  tooluse: true

g25pro:
  type: single
  provider: gemini
  model: gemini-2.5-pro

g25pro_tool:
  type: single
  provider: gemini
  model: gemini-2.5-pro
  tooluse: true
```

## Constraints

- **Gemini is per-token billed** -- keep the test corpus small; avoid running multiple rounds. 1 run per reviewer per prompt type.
- **Correct model IDs matter** -- gemini-3-flash-preview is the correct ID for "Flash Preview". Earlier guesses (gemini-3-flash, gemini-3.0-flash) were wrong and failed. Always verify model IDs from the CLI interactive menu before concluding a model is unavailable.
- **Windows paths** -- the bench script runs on Windows; use `Path` throughout; no POSIX path assumptions.
- **No registry write** -- `wiki/reviewers.yaml` is a wiki file. Additions go through `_wiki.write_commit_push` or `git -C <wiki_path>`. The bench script reads the registry but does not modify it.

## Testing

### bench-reviewers.py

No unit test needed (it is an integration runner, not a library). Validation approach:
- Smoke test: `python plugins/mill/integration_tests/bench-reviewers.py --reviewers test_stub --types discussion` -- uses `_reviewer_test_stub` (zero cost) to verify the harness end-to-end. Must produce a results table with at least one row and no Python exceptions.
- The test_stub reviewer returns a fixed APPROVE response, so format-compliance and finding-count columns should both be 0 and "Yes" respectively.

### Fixtures

- `sample-code.py`: no test needed; it is a static fixture. Visual review suffices.

### Registry entries

The existing `_reviewers.load()` validator catches schema errors. After adding `g3flash_preview` / `g3flash_preview_tool` / `g25pro` / `g25pro_tool`, run:
```
python -c "from _reviewers import load; from pathlib import Path; load(Path('c:/Code/millhouse/wiki'))"
```
from the hub root to confirm the new entries pass validation.

## Q&A log

- **Q:** Which models are in scope? **A:** g25flash (existing, unstable baseline), g3flash_preview (gemini-3-flash-preview, the "3 Flash Preview" target), g25pro (gemini-2.5-pro). **Why:** These are the two models named in the task description. Earlier scope was wrong -- gemini-3-flash-preview IS accessible; wrong model IDs were guessed. Correct ID confirmed from gemini CLI interactive menu.
- **Q:** Where should the benchmark script live? **A:** [auto-pick] `plugins/mill/integration_tests/bench-reviewers.py`. **Why:** Alongside existing integration tests, shares fixtures directory.
- **Q:** What test corpus to use? **A:** [auto-pick] Existing fixtures + small new code fixture. **Why:** Zero setup cost, reproducible, realistic inputs.
- **Q:** How to measure quality? **A:** [auto-pick] Format compliance + finding count. **Why:** Objective, no LLM cost, sufficient to detect role drift.
- **Q:** What timeout per call? **A:** [auto-pick] 300s. **Why:** Trial showed 120s is too short for g25flash; 300s covers observed worst-case.
- **Q:** Run sonnetmax in the bench script? **A:** [auto-pick] No -- reference existing data. **Why:** Billing cost, baseline already known. Baseline must be sonnetmax (bulk), not sonnetmax_tool -- the benchmark compares bulk-mode Gemini against bulk-mode Claude; tool-use capability is an unfair advantage.
- **Q:** Add both bulk and tool-use registry entries? **A:** [auto-pick] Yes, both for each new model (g3flash_preview + g3flash_preview_tool, g25pro + g25pro_tool). **Why:** Mirrors the g25flash/g25flash_tool pair; gives operators both modes.
