# Batch: review-backends

```yaml
task: "Add first-class Moves/Renames field to plan cards for rename-heavy batches"
batch: "review-backends"
number: 4
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-plan-flow.py test-language-skills-directive.py test-moves-check.py
depends-on: [1, 3]
```

## Batch Scope

This batch wires Move endpoints into the review subsystem: plan review bulks
Move sources, code review bulks Move targets and gains the mechanical
rename-detection check, and language detection considers Move endpoints. The
pure rename-finding logic lives in a new dependency-free module
`_moves_check.py` (fully unit-testable without git), and `_review_code.finalize`
performs the git invocation and splices advisory NIT findings into the review.
Depends on batch 1 (`parse_moves` / `compute_moves_union`) and batch 3 (the
`pipeline.rename_detect_pct` knob registration). Per `## Shared Decisions`
(mechanical-rename-check-advisory), the mechanical check is per-batch-only and
NIT-only.

## Cards

### Card 18: Bulk Move sources in plan review

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_plan.py`, at the points where the source-file bulk is assembled from `parse_batch_refs` + `compute_creates_union`/`compute_deletes_union` (lines ~309 and ~583), also add the Move **sources** from `compute_moves_union(plan_dir)[0]` to the set of referenced paths resolved into the reviewer bulk, so the plan reviewer sees the file being relocated (sources exist pre-implementation). Do not add Move targets here (they do not exist yet). Add a `test-review-plan-flow.py` case asserting a batch with a `Moves:` source has that source file included in the resolved plan-review bulk.
- **Commit:** `feat(review-plan): bulk move sources for plan review`

### Card 19: Bulk Move targets and reword docstring in code review

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_code.py`, where the bulk is assembled from `parse_batch_refs` + `compute_creates_union`/`compute_deletes_union` (lines ~254-257), also add Move **targets** from `compute_moves_union(plan_dir)[1]` to the referenced paths (post-implementation the target exists; the source is gone). Reword the module docstring (lines ~4-8): scope the "v2 code review does NOT look at git diff / never scrapes git" statement to the LLM reviewer specifically, and document that the backend itself uses git deterministically — both the existing `bulk_files_with_diff` (line ~165) diff-scoping and the new rename-detection check (card 21). Add a `test-review-code-flow.py` case asserting a `Moves:` target is included in the resolved code-review bulk.
- **Commit:** `feat(review-code): bulk move targets and scope docstring git rule`

### Card 20: Pure rename-check module and tests

- **Context:**
  - `plugins/mill/templates/review-code-batch.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_moves_check.py`
  - `plugins/mill/unit_tests/test-moves-check.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `_moves_check.py` exposing `planned_rename_findings(name_status_text: str, moves: list[tuple[str, str]]) -> list[str]`: parse `git diff --name-status` output (already produced with `--find-renames`), build the set of `(old, new)` pairs reported as renames (status lines beginning with `R`, whose two path columns are old and new), and for each planned `(src, dst)` in `moves` NOT present in that rename set, return one advisory **NIT** finding block (formatted per the review schema in `review-code-batch.md`: a `### [NIT] <title>` heading plus `**Location:**`/`**Issue:**`/`**Fix:**` lines) advising confirmation that `git mv` + surgical edits were used. Returns `[]` when every planned move is a detected rename or `moves` is empty. Include a module comment explaining that git does not record renames (similarity-detected at diff time), so this is a surgical-edit-vs-rewrite proxy, not proof. Create `test-moves-check.py` covering: a planned pair shown as `R100`/`R030` yields no finding; a planned pair shown as separate `A`/`D` lines yields one NIT; multiple planned moves with mixed outcomes; empty `moves`; malformed/blank diff text yields no crash. No real git — feed crafted `name_status_text` strings.
- **Commit:** `feat(moves-check): add pure planned-rename finding helper`

### Card 21: Integrate mechanical rename check into code-review finalize

- **Context:**
  - `plugins/mill/scripts/_moves_check.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_code.finalize` (line ~347), when `scope` is not None (per-batch) and a batch `start_sha` is resolvable for `scope` (resolve it the same way `prepare` does around lines ~232-240, via the batch entry's `start_sha`), and the batch declares non-empty `Moves:` (via `compute_moves_union` / `parse_moves` for that batch file): run `git -C <project_root> diff --name-status --find-renames=<thr>% <start_sha>..HEAD` where `<thr>` is `cfg["pipeline"].get("rename_detect_pct", 30)`, call `_moves_check.planned_rename_findings`, and splice the returned NIT finding blocks into `raw_text`'s `## Findings` section BEFORE `finalize_scope` parses it, so the NITs land in the written review file and flow through the normal receive-review loop. NITs MUST NOT change the verdict or `blocking_count`. Skip entirely for holistic scope, when no `start_sha`, or when git fails (swallow git errors — the mechanical check is advisory). Add a `test-review-code-flow.py` case (mocking the git diff call or providing fixture diff text) asserting a planned move that landed as add+delete produces a NIT in the finalized review without changing the verdict.
- **Commit:** `feat(review-code): splice advisory rename NIT into per-batch finalize`

### Card 22: Move endpoints in language detection

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-language-skills-directive.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_agent_dispatch.language_skills_directive` (line ~123), extend the touched-path collection (currently `parse_batch_refs(batch_file, fields=("Edits","Creates"))` at line ~138) to also include Move endpoints from `parse_moves(batch_file)` — flatten each `(src, dst)` pair so suffix-based language detection sees them (use the destination path at minimum; including both is acceptable). Add a `test-language-skills-directive.py` case asserting a card whose only file activity is a `.go -> .go` Move still pulls the Go skills.
- **Commit:** `feat(agent-dispatch): detect language from move endpoints`

## Batch Tests

`verify:` runs `test-review-code-flow.py`, `test-review-plan-flow.py`,
`test-language-skills-directive.py`, and the new `test-moves-check.py` — the
suites covering the four files this batch changes plus the new pure module. The
pure rename logic is exhaustively tested in `test-moves-check.py` with crafted
diff strings; the finalize integration is covered in `test-review-code-flow.py`
with mocked/fixture diff text (no real git, per the unit-test constraint).
