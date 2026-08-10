# Batch: finalize-verdict-rewrite

```yaml
task: '_review_common/_review_plan: verdict/count consistency and path-suppression gaps'
batch: finalize-verdict-rewrite
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-class-taxonomy.py test-review-finalize.py
depends-on: []
```

## Batch Scope

`finalize_scope` (`_review_common.py`) already rewrites demoted findings' headings/YAML via `rewrite_demoted_findings`, but never touches the persisted file's own top-level verdict — so a file can persist a fenced `verdict: REQUEST_CHANGES` (and `## Verdict` prose asserting blocking gaps) while the finalize envelope and orchestrator correctly report `APPROVE` after the `blocking_classes` ceiling demotes the surviving BLOCKING count to zero. This is a reporting defect in the persisted artifact only — the adjudication logic itself (verdict derives from surviving post-ceiling blocking count) is correct and unchanged (`#799`/`#797`). Card 6 adds a new rewrite helper reusing `apply_actual_model_override`'s existing fence-scanning logic; Card 7 wires it into `finalize_scope`, gated strictly to the case the ceiling actually changed the verdict (never firing when `blocking_classes is None`, preserving every historical/test call site's byte-identical guarantee); Card 8 adds coverage in `test-review-class-taxonomy.py`, the file that already owns `finalize_scope`'s demotion/verdict-derivation tests and their `_finalize` fixture helper — not `test-review-finalize.py`, which tests CLI-level pass-through/byte-identical-echo behavior and has no demotion fixtures at all (zero `demoted`/`blocking_classes` references in that file today).

## Cards

### Card 6: Add `rewrite_verdict_token` helper

- **Context:**
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new function `rewrite_verdict_token(raw_text: str, new_verdict: str) -> str` in `_review_common.py`, placed adjacent to `rewrite_demoted_findings` (lines 2155-2183) — both are `raw_text`-rewrite helpers `finalize_scope` composes together. It performs two independent in-place rewrites and returns the modified text:
  1. **Fenced-yaml `verdict:` field.** Reuse `apply_actual_model_override`'s existing header-fence-finding scan verbatim as the location strategy (lines 2256-2278: iterate ` ```yaml ` fence-delimited blocks, and for the block whose body contains a line matching `^verdict:\s*\S`, that is the header block) — but instead of injecting a new `reviewer_model:` line, locate that exact `verdict:` line's index inside the block body and replace its value in place with `f"verdict: {new_verdict}"`, preserving the original line's trailing newline character(s) (do not assume `\n` — some source lines may already end differently, mirror how `apply_actual_model_override` line 2284-2285 defensively appends `"\n"` only `if not lines[fence_index].endswith("\n")`). If no yaml-fenced block contains a `verdict:` line (defensive only — `finalize_scope` only reaches this helper after `parse_verdict` already succeeded on the same `raw_text`, so this should not occur in practice), leave this half of the text unmodified.
  2. **`## Verdict` section token.** Per `review-output.schema.md`'s `### \`## Verdict\`` contract (a required section with exactly two lines: the verdict token, then a one-sentence summary), scan for a line whose stripped content is exactly `## Verdict`, then find the first subsequent non-blank line — that line is the verdict token. Replace only that line's content with `new_verdict`, preserving its trailing newline; do NOT touch the following one-sentence-summary line. If no `## Verdict` heading is found (defensive only — every template emits one), leave this half of the text unmodified.

  Add a short docstring stating both rewrite targets and citing `finalize_scope` as the sole caller, and that it is a no-op-preserving companion to `rewrite_demoted_findings` (same "byte-identical when nothing needs to change" spirit, enforced by the caller's own gating in Card 7 rather than inside this function).
- **Commit:** `feat(_review_common): add rewrite_verdict_token helper (#799 #797)`

### Card 7: Wire `rewrite_verdict_token` into `finalize_scope`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `finalize_scope` (def at line 2290), restructure the body currently at lines 2339-2352:
  ```
    raw_text = apply_actual_model_override(raw_text, actual_model)
    verdict = parse_verdict(raw_text)
    findings = extract_findings(raw_text)
    if blocking_classes is not None:
        findings = apply_blocking_ceiling(findings, blocking_classes)
        raw_text = rewrite_demoted_findings(raw_text, findings)
    review_path = write_review_file(
        reviews_dir, review_type, round_n, raw_text, scope=scope
    )
    blocking_count = sum(1 for f in findings if f.severity == BLOCKING_SEVERITY)
    nit_count = sum(1 for f in findings if f.severity == NIT_SEVERITY)

    if verdict != "NEED_CONTEXT":
        verdict = "REQUEST_CHANGES" if blocking_count > 0 else "APPROVE"
  ```
  so that `blocking_count`/`nit_count` are computed and the verdict is recomputed BEFORE `write_review_file` runs (moved up, values unchanged), a local `original_verdict` retains `parse_verdict`'s pre-recompute result, and — only when `blocking_classes is not None` AND the recomputed `verdict` differs from `original_verdict` — call `rewrite_verdict_token(raw_text, verdict)` and assign its result back to `raw_text` before `write_review_file` runs. Equivalent target shape:
  ```
      raw_text = apply_actual_model_override(raw_text, actual_model)
      original_verdict = parse_verdict(raw_text)
      findings = extract_findings(raw_text)
      if blocking_classes is not None:
          findings = apply_blocking_ceiling(findings, blocking_classes)
          raw_text = rewrite_demoted_findings(raw_text, findings)
      blocking_count = sum(1 for f in findings if f.severity == BLOCKING_SEVERITY)
      nit_count = sum(1 for f in findings if f.severity == NIT_SEVERITY)
      verdict = original_verdict
      if verdict != "NEED_CONTEXT":
          verdict = "REQUEST_CHANGES" if blocking_count > 0 else "APPROVE"
      if blocking_classes is not None and verdict != original_verdict:
          raw_text = rewrite_verdict_token(raw_text, verdict)
      review_path = write_review_file(
          reviews_dir, review_type, round_n, raw_text, scope=scope
      )
  ```
  The `blocking_classes is not None` guard on the rewrite call is required — it is what keeps every historical/test call site that omits `blocking_classes` (per this function's own docstring: "every historical/test call site that does not pass it keeps today's counting behaviour untouched") byte-identical, since without a ceiling there is no demotion and `verdict` can still legitimately diverge from `original_verdict` for an unrelated reason (a reviewer stating the wrong verdict token for its own finding count) that this batch is not scoped to touch. Do not change any other line in the function (the final `return` dict, the `effective_scope` computation, and the docstring's Args/Returns sections stay as-is except adding one sentence to the docstring noting the new verdict-token rewrite, mirroring how the existing docstring already documents the demoted-findings rewrite).
- **Commit:** `fix(_review_common): rewrite persisted verdict token when ceiling changes it (#799 #797)`

### Card 8: Test coverage for the verdict-token rewrite

- **Context:**
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extend `test-review-class-taxonomy.py`, using the existing `_finalize` helper (line 36) and `_verdict_yaml` helper (line 81) already in the file. Add a new fixture helper `_verdict_section(verdict: str = "REQUEST_CHANGES") -> str` returning a 2-line `## Verdict` body matching `review-output.schema.md`'s `### \`## Verdict\`` contract (heading, blank line, verdict token line, one-sentence summary line) — e.g. `f"## Verdict\n\n{verdict}\n<summary>\n"` — placed near the other `_verdict_yaml`/`_heading`/`_yaml_block` fixture helpers. Add new test functions (following this file's existing `def test_*() -> bool:` + `TESTS` list + docstring-comment-banner convention, not `test-review-plan-flow.py`'s inline style):
  - `test_verdict_token_rewritten_on_ceiling_flip` — build raw text combining `_verdict_yaml("REQUEST_CHANGES")` + `_verdict_section("REQUEST_CHANGES")` + `_heading("BLOCKING", "scope", "missed call sites")` for the `discussion` review type (mirrors `test_verdict_derivation_discussion_scope_only_approves`'s exact fixture, which already demotes this finding to NIT and flips the recomputed verdict to `APPROVE`, since `scope` is not in discussion's `blocking_classes=[design]`); call `_finalize` with `blocking_classes=resolve_blocking_classes({}, "discussion", None)`; assert the written file's fenced yaml block now reads `verdict: APPROVE` (not `REQUEST_CHANGES`) AND its `## Verdict` section's first non-blank line now reads `APPROVE`, AND the `## Verdict` section's summary line (second line) is byte-unchanged from the fixture's `<summary>` text.
  - `test_verdict_token_unchanged_when_no_demotion` — build raw text via `_verdict_yaml("APPROVE")` + `_verdict_section("APPROVE")` + `_heading("NIT", "design", "cosmetic")` (no BLOCKING finding at all, so nothing is demoted and the recomputed verdict already equals `APPROVE`); call `_finalize`; assert the written file's verdict lines (both the yaml field and the `## Verdict` token) are byte-identical to the fixture's original text — mirrors `rewrite_demoted_findings`'s own no-op-when-nothing-changes guarantee, now asserted for the verdict-token rewrite specifically.
  - `test_verdict_token_rewritten_for_plan_and_code_types` — repeat the ceiling-flip case (same shape as the first new test) once for `review_type="plan"` and once for `review_type="code"` (using `resolve_blocking_classes({}, "plan", "holistic")` / `resolve_blocking_classes({}, "code", "holistic")` and a finding class excluded from each stage's ceiling per the existing `test_ceiling_table_plan`/`test_ceiling_table_code` tables), asserting the same yaml-field + `## Verdict`-token rewrite in both, since `finalize_scope` is shared across all three review types and the token-rewrite logic must be type-agnostic (per discussion.md's Testing section).
  Add all new test functions to the `TESTS` list with a short label, following the existing list's format exactly.
- **Commit:** `test(_review_common): cover verdict-token rewrite on ceiling-driven demotion (#799 #797)`

## Batch Tests

`verify:` runs `test-review-class-taxonomy.py` (new coverage, Card 8) and `test-review-finalize.py` (existing `finalize_scope` byte-identical/CLI pass-through regression guard — `finalize_scope`'s signature and return-dict shape are unchanged by Card 7, only its internal statement order and one new conditional branch, so this file's existing assertions must still pass unmodified).
