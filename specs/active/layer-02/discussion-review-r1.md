# Discussion Review — Layer 02 (r1)

```yaml
reviewer: claude-sonnet-4-6 (via Agent tool)
reviewed_file: specs/active/layer-02/discussion.md
date: 2026-04-20
round: 1
```

## Findings

### [GAP] Bulk-only contract breaks discussion-review's core job
**Section:** "Contracts between layers → Reviewer → LLM-provider" / "Open questions not yet resolved"
**Issue:** The discussion commits to "bulk-only — no tool-use" at the LLM-provider level. The v1 `discussion-review.md` protocol explicitly requires the reviewer to read source files referenced in the discussion's `## Technical Context` section to verify technical claims — that is its defining purpose. The v1 prompt says: "Read source files referenced in the discussion's Technical Context section to verify claims." Bulk mode requires the backend to pre-bulk all relevant files. For a discussion reviewer, the relevant files are discovered by reading the discussion first (they are listed in a section the reviewer encounters mid-read), so the backend cannot know which files to bulk before calling the reviewer. The discussion acknowledges this tension only vaguely in "Open questions" under the error/verdict topic; it does not resolve it. Either: (a) the discussion-review template must instruct the reviewer not to verify technical claims at all (a regression from v1), or (b) the backend must parse the discussion to extract referenced files before bulking (workable but complex and undocumented), or (c) the "bulk-only" constraint must be relaxed for discussion-review. None of these options are chosen.
**Suggested fix:** Add an explicit decision: state which of the three options above applies to discussion-review, and update the architecture section accordingly. If option (b) is chosen, describe the file-extraction step in `_review_discussion.py`'s flow.

---

### [GAP] LOC budget left open while architecture adds 4-layer split
**Section:** "Open questions not yet resolved"
**Issue:** The discussion explicitly defers the LOC budget decision ("Defer the decision until we see implementation reality"), but the 1500 LOC hard cap in `00-overview.md` is a hard project constraint, not negotiable. The 4-layer split introduces at minimum: 3 API scripts (~15 LOC each), 4 backend files (~100–150 LOC each), 1 reviewer file (~20 LOC), 1 LLM-provider file (~80 LOC), plus `_review_common.py`. A rough count suggests 3×15 + 4×125 + 20 + 80 = ~645 LOC for Layer 02 alone, before templates (not counted in Python LOC) and integration tests. Layer 01 already delivered scripts that consume some of the 1500-LOC budget. Without a stated budget claim for Layer 02, a plan writer cannot know what trade-offs to make. The original `layer-02-review.md` set a 750 LOC limit; the discussion explicitly abandons that without setting a replacement.
**Suggested fix:** State an explicit LOC budget for Layer 02 (e.g., "Layer 02 target: ≤700 LOC Python") and note which Layer 01 files count against the shared 1500-LOC cap. This lets the plan writer flag over-runs before writing code.

---

### [GAP] `_review_common.py` scope left undecided
**Section:** "Scope for v2 Layer 02 → Unknown / still to decide during implementation"
**Issue:** Whether `_review_common.py` exists as a shared module or is inlined into the three `_review_*.py` files is listed as an open decision. This is not a minor implementation detail — it determines the file count, the import graph, and whether there is a shared round-discovery / bulking / verdict-parsing API. A plan writer choosing to skip `_review_common.py` will write three sets of duplicated logic; a plan writer choosing to create it will produce a different architecture. These are not equivalent choices and should not be deferred to implementation.
**Suggested fix:** Make the decision now. Given the YAGNI principle in 00-overview.md and the small number of call sites (3), the recommendation would be to skip `_review_common.py` initially and split only if the duplication becomes painful. But the decision must be stated so the plan writer doesn't have to invent it.

---

### [GAP] Failure mode for partial batch failure is "current thinking," not decided
**Section:** "Open questions not yet resolved"
**Issue:** What happens when one sub-review in a parallel batch fails (LLM timeout, transient error) is explicitly marked "to confirm during implementation." The proposed behavior (`verdict: ERROR` for that sub-review, aggregate becomes `REQUEST_CHANGES`) is described as "current thinking." The plan writer needs to know this to implement the ThreadPoolExecutor fan-out, the result aggregation, and the `ReviewResult` assembly. If this is changed during implementation it will affect the CLI contract (orchestrator behavior) and the integration tests.
**Suggested fix:** Confirm the behavior now. The proposed scheme is reasonable; promote it from "current thinking" to a numbered decision in the decisions log.

---

### [GAP] Config schema in discussion conflicts with config schema in ref-formats.md
**Section:** "Config contract"
**Issue:** The discussion proposes a `review:` section in `wiki/config.yaml` with keys like `review.discussion.rounds`, `review.plan.batch`, `review.plan.holistic`, `review.code.mode`. The `ref-formats.md` canonical `config.yaml` schema uses `pipeline:` with keys like `plan-review-model`, `code-review-model`, `discussion-review-model` (a flat model-per-type structure). These two schemas are incompatible. The discussion's schema adds new keys not in `ref-formats.md` and restructures the review section entirely. The `ref-formats.md` rule says "No additions without a spec update." The discussion does not reference updating `ref-formats.md`.
**Suggested fix:** Either update `ref-formats.md` to adopt the discussion's schema (and flag the supersession explicitly), or explicitly state that the discussion's config schema supersedes the relevant section of `ref-formats.md` and list what changes.

---

### [GAP] Active slug discovery: "multiple `.slug.md` files" edge case is stated but not handled
**Section:** "Path resolution"
**Issue:** The discussion says "if zero or multiple are found → error," which is correct, but does not specify the error behavior precisely enough for a plan writer: is it a non-zero exit with JSON on stdout (matching the normal output contract), a plain stderr message with exit 1, or something else? For an orchestrator that always parses stdout as JSON, a non-JSON error message would cause a second failure in the caller. This matters because "multiple `.slug.md` files" can happen legitimately during worktree operations and the orchestrator needs to handle it gracefully.
**Suggested fix:** Specify the error output contract: "On slug-discovery failure, write a human-readable message to stderr and exit 1. Stdout is empty (no JSON)." If the orchestrator needs structured error output, say so.

---

### [GAP] Review output filename pattern in discussion differs from ref-formats.md
**Section:** "Round discovery" / "Path resolution"
**Issue:** The discussion shows review filenames as `<timestamp>-<type>-review-r<N>.md` (e.g., `20260418-001200-discussion-review-r1.md`). The `ref-formats.md` format inventory shows `<ts>-<type>-r<N>.md` for the file pattern. The v1 prompts write to `<timestamp>-plan-review-r<N>.md`. Three sources, three slightly different patterns. A plan writer will produce one of these and it will not match what the round-discovery scanner expects.
**Suggested fix:** Pick one canonical pattern and cite it consistently in both the discussion and `ref-formats.md`. The discussion should define the exact regex the round-discovery scan uses.

---

### [NOTE] 00-overview.md "Provider plugin pattern" API conflicts with discussion's reviewer/LLM-provider split
**Section:** "Architecture — 4 layers"
**Issue:** `00-overview.md` defines a "Provider plugin pattern" where each provider exposes `def review(prompt, model, effort) -> ReviewResult`. The discussion's architecture replaces this with a 4-layer split where the LLM-provider only exposes `def run(text, *, model, effort) -> str` (raw text, no ReviewResult). The ReviewResult is assembled by the backend, not the provider. This is a deliberate design change from `00-overview.md` and is a good one, but the discussion does not explicitly acknowledge that it supersedes the `00-overview.md` provider contract. This could confuse a plan writer who reads both documents.
**Suggested fix:** Add a sentence in the discussion (e.g., in "Decisions log") stating that the LLM-provider contract defined here supersedes the "Provider plugin pattern" in `00-overview.md`.

---

### [NOTE] Template placeholder list is incomplete relative to v1 prompts
**Section:** "Templates"
**Issue:** The discussion lists placeholder tokens: `<TASK_TITLE>`, `<ARTEFACT_PATH>`, `<ARTEFACT_CONTENT>`, `<CONSTRAINTS>`, `<RELEVANT_FILES>`, `<REVIEW_OUTPUT_PATH>`, `<ROUND>`. The v1 `discussion-review.md` prompt uses `<DISCUSSION_FILE_PATH>`, `<TASK_TITLE>`, `<CONSTRAINTS_CONTENT>` — and crucially the reviewer is told to read the file itself (tool-use). In a bulk model where the backend pre-bulks all relevant files, `<ARTEFACT_PATH>` plus `<ARTEFACT_CONTENT>` replaces the file-path-only token. That is fine, but `<REVIEWER_MODEL>` (needed for the review-output YAML frontmatter `reviewer_model:` field per `ref-formats.md`) is not listed among the tokens. It is likely needed.
**Suggested fix:** Add `<REVIEWER_MODEL>` to the token list, or explain how the review-output file gets its `reviewer_model:` field populated without a template token.

---

### [NOTE] Decisions log item #7 ("bulk-only") does not state the rationale for discussion-review specifically
**Section:** "Decisions log"
**Issue:** Decision #7 says "LLM-providers are bulk-only. No tool-use in the provider contract." The rationale given in the architecture section is "keeps the LLM-provider interface uniform across providers that don't support tool-use well (e.g., Gemini)." This rationale is sound for plan and code review but is in direct tension with the nature of discussion review (see GAP above). The decision entry does not address this tension.
**Suggested fix:** Either extend decision #7 with a note on how discussion-review achieves adequate coverage without tool-use, or split it: "bulk-only applies to plan and code review; discussion-review pre-bulks referenced files via backend parsing (decision #X)."

---

### [NOTE] `specs/active/layer-02/` convention is unexplained
**Section:** (general / context)
**Issue:** The discussion file lives at `specs/active/layer-02/discussion.md`. This is a new directory convention (`specs/active/<layer>/`) not documented anywhere in `00-overview.md`, `ref-formats.md`, or the original `layer-02-review.md`. A future reader or plan writer finding this file will not know whether `specs/active/` is where all in-progress layer discussions live, or whether this is a one-off location. The original layer specs live at `specs/layer-02-review.md` (flat), so the convention has changed.
**Suggested fix:** Add a one-sentence process note to this file (or the directory) explaining the convention: "Active layer design discussions live under `specs/active/<layer>/` while the layer is in design. Once implementation begins, the discussion is frozen in place and the canonical spec files at `specs/layer-NN-*.md` are updated to match."

---

### [NOTE] Integration test scope is underspecified
**Section:** "Scope for v2 Layer 02"
**Issue:** The discussion says "Integration tests (at least one per review type)" — three tests minimum. The original `layer-02-review.md` listed specific test scripts (`test-review-plan-claude.ps1`, etc.) and acceptance criteria (7 numbered items). The discussion's "at least one per review type" gives a plan writer no guidance on: what fixtures/sample artefacts are needed, what a passing test asserts (verdict? exit code? file written?), or whether the integration tests run against a real Claude CLI invocation or a stub. Given the 00-overview.md rule "total test LOC < 30% of source LOC," knowing the source LOC estimate also matters.
**Suggested fix:** Specify the minimum assertion for each integration test (e.g., "exits 0, stdout is valid JSON ReviewResult with verdict field, review file written to expected path"). Note whether a real LLM call is required or if a stub/fixture is acceptable.

---

### [NOTE] `_render.py` token grammar (`<[A-Z][A-Z0-9_]*>`) is already implemented; discussion token list is compatible
**Section:** "Templates"
**Issue:** (Positive finding, recorded for completeness.) The existing `_render.py` uses `<[A-Z][A-Z0-9_]*>` — uppercase identifiers only. All tokens listed in the discussion (`<TASK_TITLE>`, `<ARTEFACT_PATH>`, etc.) comply with this grammar. No incompatibility.
**Suggested fix:** No action needed.

---

### [NOTE] Parallelism choice (ThreadPoolExecutor) is well-reasoned but the worker cap is unstated
**Section:** "Parallelism"
**Issue:** The discussion justifies ThreadPoolExecutor well. However, it does not state the default or maximum number of concurrent workers. The text says "2–5 parallel workers per round is the realistic scale" but leaves it implicit. A plan writer will need to either hard-code a number or make it configurable.
**Suggested fix:** Add a note: "Default worker count = number of plan batches (unbounded); or cap at N (TBD). Configurable in config if needed." Or make a concrete decision.

---

## Verdict

GAPS_FOUND

Six GAPs must be resolved before implementation planning can proceed. The most critical are: (1) the bulk-only vs. tool-use tension for discussion-review is unresolved and will cause the reviewer to produce a weaker review than v1 delivered; (2) the LOC budget for Layer 02 is explicitly deferred despite being a hard project constraint; (3) the config schema introduced here conflicts with the canonical schema in `ref-formats.md` without acknowledging the conflict.
