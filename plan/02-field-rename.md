# Batch: field-rename

```yaml
task: 10 (B) — Plan-template format-forbedringer
batch: field-rename
cards: 6
verify: python plugins/mill/unit_tests/test-plan-validate.py && python plugins/mill/unit_tests/test-review-common.py
depends-on: [batch-numbering]
```

## Batch Scope

This batch renames `Reads:` → `Context:` and `Modifies:` → `Edits:` everywhere: regex constants in `_review_common.py` and `_plan_validate.py`, required-field lists, function names, error messages, all six templates, the implementer brief, and mill-plan SKILL.md. `Creates:` and `Deletes:` are unchanged. The code change is purely mechanical — no logic changes. Unit tests for the affected modules are updated to use the new field names. Cards must be done in order: code first (cards 7-8), then templates and SKILL.md (cards 9-10), then tests (card 11), then plan-file relabel (card 12). Card 12 ensures the post-batch code-reviewer's `parse_batch_refs` (which now uses the renamed regex) can still bulk source files from the plan files in `plan/`.

## Cards

### Card 7: Rename in `_review_common.py`, `_review_plan.py`, `_review_code.py`

- **Reads:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_code.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `_review_common.py`:
  - Update `_RE_REFS_HEADER`: change `r"^-\s*\*\*(Reads|Modifies|Creates|Deletes):\*\*(?P<inline>.*)$"` to `r"^-\s*\*\*(Context|Edits|Creates|Deletes):\*\*(?P<inline>.*)$"`.
  - Update `parse_batch_refs` docstring: replace "Reads/Modifies/Creates/Deletes" with "Context/Edits/Creates/Deletes".

  In `_review_plan.py`:
  - Line with `` f"`Reads:` / `Modifies:` / `Creates:` in the batch + cross-batch creates " ``: change to `` f"`Context:` / `Edits:` / `Creates:` in the batch + cross-batch creates " ``.
  - Line with `f"## Plan content (overview + batch + Reads/Modifies/Creates files + cross-batch ancestor creates)\n"`: change to `f"## Plan content (overview + batch + Context/Edits/Creates files + cross-batch ancestor creates)\n"`.
  - Comment `# Union all Reads:/Modifies:/Creates: across all batch files`: change to `# Union all Context:/Edits:/Creates: across all batch files`.

  In `_review_code.py`:
  - Docstring line 14: replace `` "that batch's ``Reads:`` / ``Modifies:`` / ``Creates:`` lines." `` with `` "that batch's ``Context:`` / ``Edits:`` / ``Creates:`` lines." ``.

- **Commit:** `refactor(review): rename Reads/Modifies → Context/Edits in review_common, review_plan, review_code`

### Card 8: Rename in `_plan_validate.py`

- **Reads:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Modifies:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Update module docstring: in check descriptions, replace `Reads:/Modifies:/Creates:` with `Context:/Edits:/Creates:`, "Modifies:" with "Edits:", and update `card-missing-field` description from "(Reads, Modifies, Creates, Requirements, Commit)" to "(Context, Edits, Creates, Requirements, Commit)".

  Update `_RE_REFS_HEADER` constant: change `r"^-\s*\*\*(Reads|Modifies|Creates|Deletes):\*\*(?P<inline>.*)$"` to `r"^-\s*\*\*(Context|Edits|Creates|Deletes):\*\*(?P<inline>.*)$"`.

  Update `_REQUIRED_CARD_FIELDS`: change `["Reads", "Modifies", "Creates", "Deletes", "Requirements", "Commit"]` to `["Context", "Edits", "Creates", "Deletes", "Requirements", "Commit"]`.

  Rename `_parse_modifies_only` to `_parse_edits_only` throughout the file (definition and all three call sites: in `_check_parallel_modifies_overlap`, `_check_wiki_config_mutation`, and `_check_all_files_touched_mismatch`). Update the function's docstring: replace "Modifies:" with "Edits:".

  Rename `_check_reads_not_backtick_path` to `_check_ref_not_backtick_path` throughout the file (definition + the single call site in `run()`). The function validates `Context:`/`Edits:`/`Creates:`/`Deletes:` after the rename, so "reads" in its name is misleading.

  Update the `_check_reads_not_backtick_path` inline error message: change `"Reads/Modifies/Creates inline value contains prose alongside backtick path:"` to `"Context/Edits/Creates inline value contains prose alongside backtick path:"`.

  Update error messages in `_check_parallel_modifies_overlap`:
  - `batch_modifies` variable rename to `batch_edits`.
  - Message: `f"path '{path}' in Modifies: of parallel-eligible batches '{a_name}' and '{b_name}'"` → `f"path '{path}' in Edits: of parallel-eligible batches '{a_name}' and '{b_name}'"`.

  Update error messages in `_check_wiki_config_mutation`: `"batch modifies or creates wiki/config.yaml"` → `"batch edits or creates wiki/config.yaml"`.

  Update error messages in `_check_all_files_touched_mismatch`:
  - `f"path '{p}' listed in overview's All Files Touched but not in any card's Modifies: or Creates:"` → `"...Edits: or Creates:"`.
  - `f"path '{p}' in card Modifies:/Creates: but missing from overview's All Files Touched"` → `"...Edits:/Creates:..."`.

- **Commit:** `refactor(plan-validate): rename Reads/Modifies → Context/Edits in plan_validate`

### Card 9: Rename in all six templates

- **Reads:**
  - `plugins/mill/templates/plan-batch.md`
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/implementer-brief.md`
- **Modifies:**
  - `plugins/mill/templates/plan-batch.md`
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `plan-overview.md`:
  - HTML comment line referencing "resolving card-level `Reads:`/`Modifies:` paths" → replace `Reads:`/`Modifies:` with `Context:`/`Edits:`.
  - `## All Files Touched` description: `Full union of every \`Creates:\` / \`Modifies:\` across every batch` → `Full union of every \`Creates:\` / \`Edits:\` across every batch`.

  In `plan-batch.md`:
  - Card field header label `**Reads:**` → `**Context:**` in the template body (the `### Card N:` example).
  - Card field header label `**Modifies:**` → `**Edits:**`.
  - Update the field description bullet list (the lines starting with `- **Reads:** every file...` and `- **Modifies:** files the implementer edits...`): rename and update description: `- **Context:** every file the implementer reads but does not change. Non-empty. One backtick-wrapped path per indented bullet.` and `- **Edits:** files the implementer changes (implicitly also read — do not repeat in Context:). One backtick-wrapped path per indented bullet.`
  - Update the combined constraint sentence at the bottom of the Cards section: replace `Reads/Modifies/Creates/Deletes fields` with `Context/Edits/Creates/Deletes fields`.
  - Add a reviewer-asymmetry note after the field descriptions: "Note for reviewers: the plan-reviewer bulks `Context: ∪ Edits:` (existing files only; `Creates:` targets do not exist yet). The code-reviewer bulks `Context: ∪ Edits: ∪ Creates:` (all files exist post-implementation)."

  In `review-plan-batch.md`:
  - Criteria section: replace `Reads:` with `Context:`, `Modifies:` with `Edits:` in all criteria bullet text.
  - Specifically: `**Reads field** — non-empty; lists every file the implementer reads.` → `**Context field** — non-empty; lists every file the implementer reads but does not edit. Edits: files are implicitly read — do not repeat them in Context:.`
  - Replace `Creates`/`Modifies`/`Reads` references in completeness criterion: `every card has \`Creates\`/\`Modifies\`, \`Reads\`, \`Requirements\`, \`Commit\`.` → `every card has \`Creates\`/\`Edits\`, \`Context\`, \`Requirements\`, \`Commit\`.`
  - **Explore targets** bullet: `**Explore targets** — purpose-driven; subset of \`Reads:\`.` → `**Explore targets** — purpose-driven; subset of \`Context:\`.`
  - Add after the criteria list a note about reviewer asymmetry: "**Reviewer note:** plan-reviewer sees only `Context: ∪ Edits:` (existing files). `Creates:` targets are absent — do not flag missing `Creates:` files as NEED_CONTEXT."

  In `review-plan-holistic.md`:
  - Same field-name replacements as above in criteria text.
  - `**Reads field** — non-empty per card.` → `**Context field** — non-empty per card; Edits: files are implicitly read.`
  - `Creates`/`Modifies`/`Reads` → `Creates`/`Edits`/`Context` in completeness criterion.
  - **Explore targets** bullet: `**Explore targets** — purpose-driven; subset of \`Reads:\`.` → `**Explore targets** — purpose-driven; subset of \`Context:\`.`

  In `review-code-batch.md`:
  - Criteria text: `**Plan alignment** — every card's \`Requirements:\` is realised in the source files; every file listed in \`Reads:\` / \`Modifies:\` / \`Creates:\` is present and matches its stated role.` → use `Context:` / `Edits:` / `Creates:`.
  - `**Out-of-plan files** — BLOCKING if the batch touches a file not listed in any card's \`Reads:\`/\`Modifies:\`/\`Creates:\`.` → use `Context:`/`Edits:`/`Creates:`.

  In `implementer-brief.md`:
  - `Read every file in \`Reads:\` before editing.` → `Read every file in \`Context:\` and \`Edits:\` before editing.`
  - `Edit / create the files in \`Modifies:\` / \`Creates:\`.` → `Edit / create the files in \`Edits:\` / \`Creates:\`.`
  - `\`Reads:\`/\`Modifies:\`/\`Creates:\` lists` → `\`Context:\`/\`Edits:\`/\`Creates:\` lists`.

- **Commit:** `refactor(templates): rename Reads/Modifies → Context/Edits in all plan and review templates`

### Card 10: Rename in `mill-plan/SKILL.md`

- **Reads:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Replace every occurrence of `Reads:` with `Context:` and `Modifies:` with `Edits:` in the entire file. Specifically:

  In Phase: Plan (batch sizing paragraph): `If a proposed batch would force Sonnet to load the entire codebase to understand its own \`Reads:\` list` → `\`Context:\` list`.

  In validator mechanical-fix table:
  - `non-existent-path` row: `move it from Reads:/Modifies: to Creates:` → `move it from Context:/Edits: to Creates:`.
  - `card-missing-field` row: `Reads: → list the file(s)...` → `Context: → list the file(s)...`; `Modifies: → none if the card creates a new file only` → `Edits: → none if the card creates a new file only`.
  - `all-files-touched-mismatch` row: `union of every card's Modifies: + Creates:` → `union of every card's Edits: + Creates:`.

  In Principles section: `**Card \`Reads:\` must be comprehensive**` → `**Card \`Context:\` must be comprehensive**`; update the full sentence to say "every file the implementer needs to read WITHOUT editing, listed" and "An empty or terse \`Context:\` is a review-blocker".

- **Commit:** `refactor(mill-plan): rename Reads/Modifies → Context/Edits in SKILL.md`

### Card 11: Update unit tests for renamed fields

- **Reads:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `test-plan-validate.py`:
  - In `_make_batch_file`: rename parameter `reads` → `context`, `modifies` → `edits`. Update generated field headers: `f"- **Reads:** {fmt(reads)}\n"` → `f"- **Context:** {fmt(context)}\n"`, `f"- **Modifies:** {fmt(modifies)}\n"` → `f"- **Edits:** {fmt(edits)}\n"`.
  - In `_make_batch_file_cards`: update hardcoded `"- **Reads:** none\n"` and `"- **Modifies:** none\n"` to `"- **Context:** none\n"` and `"- **Edits:** none\n"`.
  - Update all call sites that pass `reads=...` → `context=...`, `modifies=...` → `edits=...`.
  - Update `test_check_card_missing_field_dirty`: use `missing_fields={"Edits"}` instead of `{"Modifies"}`; update assertion to `"Edits" in check2[0]["message"]`.
  - Update any error-message assertions that reference "Modifies:" to "Edits:".
  - Update hardcoded raw-string fixtures in two tests that build batch text directly (without `_make_batch_file`):
    - `test_check_reads_not_backtick_path_clean`: `"- **Reads:** \`src/a.py\`\n"` → `"- **Context:** \`src/a.py\`\n"`; `"- **Modifies:** none\n"` → `"- **Edits:** none\n"`.
    - `test_check_reads_not_backtick_path_dirty`: `"- **Reads:** \`src/foo.py\` (used by foo)\n"` → `"- **Context:** \`src/foo.py\` (used by foo)\n"`; `"- **Modifies:** none\n"` → `"- **Edits:** none\n"`.
    - `test_check_reads_not_backtick_path_none_exempt` uses `_make_batch_file("alpha")` (no raw string) — its docstring `"Clean: \`- **Reads:** none\` returns [] for check 6."` should be updated to `"Clean: \`- **Context:** none\` returns [] for check 6."` for consistency, but the test body needs no changes (relies on the `_make_batch_file` parameter rename).
    Without these updates, the renamed `_RE_REFS_HEADER` regex (Card 8) stops matching the raw-string fixtures and those two tests pass vacuously or fail outright — breaking batch 02's `verify:` command.

  In `test-review-common.py`:
  - Update all `parse_batch_refs` fixture strings: `"- **Reads:** ..."` → `"- **Context:** ..."`, `"- **Modifies:** ..."` → `"- **Edits:** ..."`. Specifically:
    - Multi-line bullet form test: `"- **Reads:**\n  - \`path/a\`\n..."` → `"- **Context:**\n  - \`path/a\`\n..."`.
    - Mixed single-line/multi-line test: `"- **Reads:** \`a\`\n- **Modifies:**\n..."` → `"- **Context:** \`a\`\n- **Edits:**\n..."`.
    - NONE filter test: `"- **Modifies:** NONE\n"` → `"- **Edits:** NONE\n"`.
    - Deletes test: `"- **Reads:** \`src/a.py\`\n- **Modifies:** \`src/b.py\`\n..."` → `"- **Context:** ...\n- **Edits:** ...\n..."`.
    - Mixed token + lowercase none test: `"- **Reads:** \`a\`, none\n"` → `"- **Context:** \`a\`, none\n"`.
    - Assert comment strings: replace `"Reads token missing"`, `"Modifies token missing"` with `"Context token missing"`, `"Edits token missing"`.
    - Any other fixture string containing `Reads` or `Modifies` field headers.

- **Commit:** `test(plan-validate,review-common): update field names Reads/Modifies → Context/Edits`

### Card 12: Relabel plan files so post-batch and holistic code review can bulk source files

- **Reads:**
  - `plan/01-batch-numbering.md`
  - `plan/02-field-rename.md`
  - `plan/03-guidance.md`
- **Modifies:**
  - `plan/01-batch-numbering.md`
  - `plan/02-field-rename.md`
  - `plan/03-guidance.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Replace every occurrence of `- **Reads:**` with `- **Context:**` and every occurrence of `- **Modifies:**` with `- **Edits:**` in all three plan-batch files: `plan/01-batch-numbering.md`, `plan/02-field-rename.md`, and `plan/03-guidance.md`. Both single-line form (`- **Reads:** \`path\``) and multi-line form (`- **Reads:**\n  - \`path\``) must be replaced. `- **Creates:**` and `- **Deletes:**` headers are unchanged. Do NOT edit `plan/00-overview.md` — it contains no card field labels (only its `## All Files Touched` description, which Card 9 already updates as a template change does not apply here because `00-overview.md` is a rendered instance, not the template).

  Why all three plan files: this worktree's `.millhouse/config.local.yaml` sets `review.code.per_batch: false`, so only the holistic code reviewer runs after all batches complete. The holistic reviewer reads every batch file and bulks the union of source files via `parse_batch_refs`. After card 7 commits the regex rename, `parse_batch_refs` only matches `Context|Edits|Creates|Deletes` headers; any plan file still using `**Reads:**`/`**Modifies:**` returns an empty ref set and its source files are not bulked. Relabeling all three plan files (01, 02, 03) ensures the holistic reviewer sees every source file from every batch.

  This card runs LAST in batch 02 so that the renamed regex (committed in card 7) matches the now-renamed plan-file headers when the holistic code reviewer fires after batch 03.

- **Commit:** `refactor(plan-files): relabel plan-file card fields Reads/Modifies → Context/Edits`

## Batch Tests

Cards 7-10 are mechanical renames with no logic change; correctness is verified by the unit tests in card 11. Card 12 has no runnable test surface (it only relabels plan-text headers); its correctness is observed indirectly by mill-go's post-batch code-reviewer successfully bulking the source files. The `verify:` command runs `test-plan-validate.py` and `test-review-common.py`. All tests that previously relied on `Reads:`/`Modifies:` field names must pass after the rename.
