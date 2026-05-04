# Batch: content-helpers

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
batch: content-helpers
cards: 7
verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Foundation batch. Adds the `Deletes:` schema to the refs parser, three new helpers in `_review_common.py` (`compute_deletes_union`, `build_deletes_section`, `detect_resume_round`), extends `resolve_ref_paths` with a `deletes_union` keyword, documents the `Deletes:` field in `plan-batch.md`, and adds a `timeout` kwarg to every reviewer module's `run()` so timeout config can propagate. No backend integration in this batch — `_review_plan.py`, `_review_code.py`, `_plan_validate.py`, and the CLIs continue to work unchanged. The four downstream batches (`review-plan-integration`, `review-code-integration`, `cli-error-prefix`, `plan-validate-deletes`) consume what this batch produces.

External interface for downstream batches:
- `compute_deletes_union(plan_dir: Path) -> set[str]`
- `resolve_ref_paths(..., *, deletes_union: set[str] | None = None, ...)` (extended kwarg)
- `build_deletes_section(deletes_tokens: list[str]) -> str`
- `detect_resume_round(reviews_dir: Path, review_type: str) -> int | None`
- Reviewer `run(prompt_text, *, session_id=None, resume=False, timeout=None) -> tuple[str, str]`

## Cards

### Card 1: Add `Deletes` to refs-header regex in `_review_common.py`

- **Reads:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update the `_RE_REFS_HEADER` constant to alternate over `Reads|Modifies|Creates|Deletes` instead of the current three-way alternation. Confirm `parse_batch_refs` continues to extract tokens for all four field types via the existing single-line and multi-line bullet logic — no signature change. Add a unit test in `test-review-common.py` proving `parse_batch_refs` returns `Deletes:` tokens alongside the existing fields when the input batch has all four. Existing tests for `Reads`/`Modifies`/`Creates` must still pass. The new test fixture is built in-memory via `tempfile`.
- **Commit:** `feat(review-common): include Deletes in refs header regex`

### Card 2: Add `compute_deletes_union(plan_dir)` helper

- **Reads:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** TDD-first. Add `compute_deletes_union(plan_dir: Path) -> set[str]` mirroring `compute_creates_union` exactly: iterate every `??-*.md` file under `plan_dir` except `00-overview.md`; for each file, scan `Deletes:` headers in single-line and multi-line bullet form; extract backtick-wrapped tokens (or comma-separated tokens when no backticks); filter `none` (case-insensitive); return a flat `set[str]` of raw tokens. Empty set when `plan_dir` doesn't exist or contains no batch files. Unit-test cases (write tests first, then implementation): empty plan_dir → empty set; single batch single-line `- **Deletes:** \`a\`, \`b\`` → `{"a", "b"}`; single batch multi-line bullet form → `{"a", "b"}`; "none" sentinel filter (case variants `None`/`NONE`/`none`); two batches with overlapping deletes → de-duplicated; `Deletes:` field absent on a card → that card contributes nothing while other cards in the same batch do; `00-overview.md` is skipped. Insert the helper next to `compute_creates_union`; update the module-docstring's public-API list.
- **Commit:** `feat(review-common): add compute_deletes_union helper`

### Card 3: Extend `resolve_ref_paths` with `deletes_union` keyword

- **Reads:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** TDD-first. Add a new keyword-only parameter `deletes_union: set[str] | None = None` to `resolve_ref_paths`. Inside the loop: when a candidate path is missing on disk, suppress (silent skip, no error) if `raw in (creates_union or set())` OR `raw in (deletes_union or set())`. The existing `creates_union` behaviour is unchanged; the new `deletes_union` adds a second silent-suppress source. The hard-fail path stays identical (raise `ReviewError` only when missing AND not in either union). Tests-first: missing-on-disk + in `deletes_union` → silent suppress (return list excludes that token); missing + in both unions → silent suppress; missing + in neither → `ReviewError` (existing); on-disk + in `deletes_union` → resolve normally and include in returned list; caller-label propagation — when the error is raised, the message contains the supplied `caller_label` prefix. Update the docstring to describe both unions.
- **Commit:** `feat(review-common): add deletes_union suppression to resolve_ref_paths`

### Card 4: Add `build_deletes_section(deletes_tokens)` helper

- **Reads:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `build_deletes_section(deletes_tokens: list[str]) -> str` returning `## Intentionally deleted (N=<count>)\n\n- <token-1>\n- <token-2>\n...` with no trailing newline. Empty list returns the empty string so callers can splice unconditionally. Mirror the shape and docstring of `build_manifest_section`. Tests: empty list → empty string; single token; multiple tokens preserve input order; bullets are exactly `- <token>` (no backticks added by the helper — the caller decides). Insert the helper right after `build_manifest_section` in `_review_common.py` and add it to the module-docstring public-API list.
- **Commit:** `feat(review-common): add build_deletes_section helper`

### Card 5: Add `detect_resume_round(reviews_dir, review_type)` helper

- **Reads:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** TDD-first. Add `detect_resume_round(reviews_dir: Path, review_type: str) -> int | None`. Returns the highest round number `N` such that at least one per-batch review file exists for round `N` AND no holistic review file exists for round `N`; otherwise `None`. Use the existing `RE_SIMPLE` and `RE_BATCH` constants (RE_SIMPLE first per the convention used by `discover_round`). Returns `None` when `reviews_dir` does not exist. Tests-first: no files → `None`; per-batch round-1 files + holistic round-1 file → `None`; per-batch round-1 files + no holistic round-1 → `1`; per-batch rounds 1 and 2 + holistic round-1 + no holistic round-2 → `2`; per-batch round 2 partial (some batches at round 2, some only at round 1) + no holistic round-2 → `2` (highest round seen for any per-batch file regardless of which batch). The helper is consumed only by `_review_plan.run` (B04); add it to the module-docstring public-API list.
- **Commit:** `feat(review-common): add detect_resume_round helper`

### Card 6: Document `Deletes:` field in `plan-batch.md` template

- **Reads:**
  - `plugins/mill/templates/plan-batch.md`
- **Modifies:**
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a `- **Deletes:**` field documentation bullet immediately after the existing `- **Creates:**` bullet in the Cards section of the template. Mirror the prose: backtick-wrapped paths only, multi-line bullet form supported, "none" sentinel for the empty case. Update the example card block (lines starting `### Card N: <short title>`) to include a `- **Deletes:** none` line between `- **Creates:**` and `- **Requirements:**`. Update the prose paragraph that lists which fields contain ONLY backtick-wrapped paths to include `Deletes` in the list ("Reads/Modifies/Creates/Deletes fields contain ONLY backtick-wrapped paths..."). The HTML comment at the top stays — it's stripped per template convention.
- **Commit:** `feat(plan-batch): document Deletes: field in card template`

### Card 7: Add `timeout` kwarg to reviewer modules and stub

- **Reads:**
  - `plugins/mill/scripts/_reviewer_sonnetmax.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/unit_tests/test-reviewer-modules.py`
- **Modifies:**
  - `plugins/mill/scripts/_reviewer_sonnetmax.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/unit_tests/test-reviewer-modules.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a keyword-only parameter `timeout: int | None = None` to every reviewer module's `run()` function. In `_reviewer_sonnetmax.py` and `_reviewer_sonnetmax_tool.py`: when `timeout` is `None`, omit it on the inner `run_bulk` / `run_tool_use` call (the LLM provider's default applies); when set, forward it as `timeout=timeout`. In `_reviewer_test_stub.py`: extend the `kwargs` dict captured in `_prompts` to include `"timeout": timeout` so backend tests can assert it. Update `test-reviewer-modules.py` to assert: every reviewer's `run()` signature exposes `timeout` as a keyword-only parameter with default `None`; calling the stub with `timeout=900` makes `captured_prompts()[0][1]["timeout"] == 900`. The stub still defaults the queue-empty error message; signature changes do not break existing seeded-queue behaviour.
- **Commit:** `feat(reviewers): add timeout kwarg propagating to LLM provider`

## Batch Tests

Run-all unit tests must pass after every card. Specifically:

- `test-review-common.py` covers Cards 1–5 (parse_batch_refs/Deletes, compute_deletes_union, resolve_ref_paths/deletes_union, build_deletes_section, detect_resume_round).
- `test-reviewer-modules.py` covers Card 7 (signature + stub-capture).
- Card 6 has no runtime test surface — the template change is verified implicitly when downstream batches generate test fixtures using the updated shape.

The batch's `verify:` re-runs the entire suite to catch regressions in any other module.
