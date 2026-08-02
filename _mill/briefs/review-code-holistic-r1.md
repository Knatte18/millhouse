**If you find issues, REPORT them — do NOT fix them.**

You are an independent code reviewer for **Improve diagnosability of plan-validate errors and finalize verify-replay failures**. You evaluate the complete implementation (every batch) against the approved plan and produce a structured review.

Reviewer model: **sonnethigh**. Round **1**.

**You MAY use Read, Grep, and Glob to verify claims against source files.**
**CRITICAL: The one exception beyond that is Write -- use it exactly once, to write your full report to the file named in this brief's output-contract footer.**
**CRITICAL: Do NOT use Edit, or run git/bash.**
**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**
**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**

## Prior non-blocking items

The following items were judged non-blocking in a prior round. Do NOT escalate any of them to BLOCKING unless NEW information justifies it -- a new diff, a real reproducible failure, or a concrete in-repo convention. If you escalate, you MUST state the new information explicitly.

Prefer the convention already used by analogous code in the provided source files over a stricter alternative.

(none)

## Constraints


## Files included (N=26)

- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/00-overview.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/01-plan-validate-line-field.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/02-plan-validate-line-field-tests.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/03-status-batch-baseline-field.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/04-implementer-common-signature-diff.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/05-verify-baseline-refactor.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/06-baseline-stage-wiring.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/07-baseline-waiver-integration-test.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_plan_validate.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/skills/mill-plan/SKILL.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-plan-validate.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_status.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-status.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_implementer_common.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-implementer-common.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_verify_baseline.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-verify-baseline.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/millpy-implement.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/skills/mill-go/SKILL.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-millpy-implement.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/integration_tests/test-baseline-waiver.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/discussion.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_plan_dag.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/integration_tests/test-verify-baseline.py
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/status.md
- /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/00-overview.md

## Plan + source files to review
- Overview: `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/00-overview.md`
- Batch file(s):
  - `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/01-plan-validate-line-field.md`
  - `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/02-plan-validate-line-field-tests.md`
  - `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/03-status-batch-baseline-field.md`
  - `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/04-implementer-common-signature-diff.md`
  - `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/05-verify-baseline-refactor.md`
  - `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/06-baseline-stage-wiring.md`
  - `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/07-baseline-waiver-integration-test.md`

Read the overview and every batch file above. Then read every source file listed below for full context (includes cross-batch ancestor creates already on disk):
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_plan_validate.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/skills/mill-plan/SKILL.md`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-plan-validate.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_status.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-status.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_implementer_common.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-implementer-common.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_verify_baseline.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-verify-baseline.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/millpy-implement.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/skills/mill-go/SKILL.md`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/unit_tests/test-millpy-implement.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/integration_tests/test-baseline-waiver.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/discussion.md`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/scripts/_plan_dag.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/plugins/mill/integration_tests/test-verify-baseline.py`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/status.md`
- `/home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/plan/00-overview.md`

## Source-grounding rule

**Never guess.** A `## Files included` manifest at the top of the artefact section above lists every file delivered to you in this prompt. Before emitting `verdict: NEED_CONTEXT`, scan the manifest and confirm the file you claim is missing is genuinely absent from the list. If a file IS in the manifest but you cannot find its content via the `--- FILE: <path> ---` delimiter, that is a long-context recall failure on your side — re-scan; do not emit NEED_CONTEXT for files in the manifest. Only emit `verdict: NEED_CONTEXT` for paths that are NOT in the manifest, and explain under `## Missing context` why each path is needed (one line per path). The orchestrator will re-fire the review with those files added. Fabricating file contents — or inferring them from filename / position alone — is a worse failure than halting honestly.

## Criteria (apply to the implementation as a whole)

- **End-to-end plan alignment** — every batch's cards are realised; every file listed across all batches' `Context:`/`Edits:`/`Creates:` is present in the source files provided.
- **Shared-decisions alignment** — the `## Shared Decisions` subsections are applied consistently across all batches; deviation is BLOCKING.
- **Out-of-plan files** — BLOCKING if any source file is present that is not accounted for in any batch's reference lists. If the implementer added it, the batch file must have been updated first; a review with surprise files means that discipline was skipped somewhere.
- **Cross-batch contracts** — interfaces produced by one batch and consumed by another are compatible. Dependency order implied by `depends-on:` is reflected in the code (consumers don't assume behaviour the producer doesn't guarantee).
- **Integration correctness** — the pieces work together, not just per-batch. Call sites match signatures; shared state is consistently managed; error surfaces compose.
- **Global utility duplication** — BLOCKING if two batches independently reimplement the same helper. Consolidate into a shared module.
- **Test coverage across the whole surface** — happy paths + errors for every batch's entry point. Integration tests reach across batch boundaries where appropriate.
- **Constraint violations** — BLOCKING.
- **Codebase consistency** — naming, error handling, imports, and style match the conventions visible in the source files provided.
- **Language pitfalls** — BLOCKING if high-risk (Python: mutable defaults, import side-effects, Windows path sep, CRLF/LF).

## Output format — STRICT

Wrap your entire output in `MILL_REVIEW_BEGIN` / `MILL_REVIEW_END` markers, each on its own line. Everything outside these markers is ignored by the backend. **No preamble inside the markers.** Per finding: 3–5 lines, short and factual. Cite file and line, state the issue, propose the fix.

Target length: ~400 tokens for APPROVE, ~800–1500 tokens for REQUEST_CHANGES across multiple batches. If you produce more than ~1800 tokens, compress.

~~~markdown
MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures — holistic

```yaml
verdict: APPROVE | REQUEST_CHANGES | NEED_CONTEXT
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: <UTC YYYY-MM-DD>
```

## Findings

### [BLOCKING] <short title, <60 chars>
**Location:** `path/to/file.py:42` (or `:42-58`)
**Issue:** <one sentence>
**Fix:** <one sentence>

### [NIT] <short title>
**Location:** `path/to/file.py:N`
**Issue:** <one sentence>
**Fix:** <one sentence>

## Missing context
(include ONLY when verdict is NEED_CONTEXT — omit the section otherwise)

- `path/to/file.py` — <one-line reason the reviewer needs this file>

## Verdict

<APPROVE | REQUEST_CHANGES | NEED_CONTEXT>
<one sentence — max 20 words>
MILL_REVIEW_END
~~~

Severity / verdict rules match review-code-batch.md.

**Severity vocabulary is closed.** Use ONLY `BLOCKING` or `NIT` as the bracketed label in a finding heading -- never invent another word (e.g. `MAJOR`, `MINOR`, `CRITICAL`, `MEDIUM`, `HIGH`). If a finding's severity feels ambiguous, default to `BLOCKING`, never `NIT` -- an over-cautious BLOCKING can be pushed back on by the orchestrator; a mislabeled NIT (or an unrecognized label) can silently skip review entirely.

Omit `## Findings` if zero findings. Never invent findings to pad.


---

## Output contract

Write your full report to this file: /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/briefs/review-code-holistic-r1.out.md

Any format the prompt above asks for (including a `MILL_REVIEW_BEGIN` / `MILL_REVIEW_END` wrapped report) is the content of /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/briefs/review-code-holistic-r1.out.md -- write it there, not into chat.

Your final chat message must be exactly one line and nothing else: `WROTE /home/knatte/Code/millhouse/wts/mill-validate-verify-diagnostics-gaps/_mill/briefs/review-code-holistic-r1.out.md`
