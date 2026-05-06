# Discussion: 10 (B) — Plan-template format-forbedringer

```yaml
task: 10 (B) — Plan-template format-forbedringer
slug: plan-template-quality
status: discussing
parent: main
```

## Problem

Three usability gaps in the plan template and mill-plan skill have been accumulating since mill-v2 shipped:

1. **Batch numbering** — Batches are numbered by filename prefix (`01-`, `02-`) but that number never appears in the overview's `batches:` YAML block. `depends-on:` lists batch _names_ (e.g. `depends-on: [foundation]`), which are meaningless for navigating a DAG. A reader has to hunt through batch titles to reconstruct the dependency graph.

2. **Reads/Modifies overlap** — The `Reads:` and `Modifies:` card fields are redundant: any file you modify is obviously also read, so planners list the same file in both. This makes `Reads:` ambiguous and forces implementers to infer intent from duplication. The rename (`Context:`/`Edits:`) makes the fields non-overlapping with self-evident semantics.

3. **Vague Requirements** — mill-plan instructions don't require stable identifiers (function names, class names) in `Requirements:` bodies. Planners write "refactor config loading to use shared helper" instead of "replace `_load_config` in `mill-claim.py` with `from _config import load_config`". Implementers then do exploratory reads not listed in `Context:`, increasing token cost and error rate.

## Scope

**In:**
- Add `number:` field to the `batches:` YAML block in the plan overview and to each batch file's frontmatter
- Switch `depends-on:` from batch-name strings to batch-number integers
- Update `_plan_dag.py` to validate integer `depends-on:`, remain backward-compatible with old name-based plans
- Update `_plan_validate.py`'s `depends-on-unknown` check for number-based deps
- Rename `Reads:` → `Context:` and `Modifies:` → `Edits:` throughout: templates, regex constants, field lists, review criteria, SKILL.md instructions
- Strengthen mill-plan SKILL.md: `Requirements:` must use stable identifiers; `Context:` is an allowlist
- Add BLOCKING criteria to plan-review templates for vague Requirements and missing Context entries
- Document the reviewer asymmetry for `Creates:` (plan-reviewer bulks `Context: ∪ Edits:`; code-reviewer bulks `Context: ∪ Edits: ∪ Creates:`)
- Update unit tests for all changed modules

**Out:**
- mill-go SKILL.md — batch execution uses `topo_order()` which still returns names; no change needed
- code-review template "out-of-plan files" criterion — already covers Edits/Creates; no new Reads-enforcement in code review (unobservable at review time)
- mill-merge, mill-merge-in, mill-spawn — no plan-parsing changes
- wiki-config.yaml — no new config keys; the local `.millhouse/config.local.yaml` override (`review.plan.batch: null`) is already set for this worktree, so holistic-only plan review is active without code changes
- Adding a global `review.plan.per_batch` config key — out of scope; `batch: null` already achieves holistic-only for any worktree that wants it

## Decisions

### batch-number-field-location

- **Decision:** Add `number:` to both the overview's `batches:` YAML block (integer, first field in the entry) and to each batch file's frontmatter (same integer). `depends-on:` in the overview becomes a list of integers.
- **Rationale:** Having `number:` in the overview block is required for DAG validation. Having it in the batch frontmatter makes each batch file self-describing (implementer sees their batch number without opening the overview).
- **Rejected:** Number-only in the overview, derived from filename in the batch file — the filename is a path artifact, not a first-class metadata field.

### depends-on-integer-format

- **Decision:** `depends-on:` switches from `[name1, name2]` (strings) to `[1, 2]` (integers). `_plan_dag.py` maps numbers to names internally; `topo_order()` still returns names (mill-go unchanged).
- **Rationale:** Issue #17 explicitly says names are meaningless for DAG navigation; numbers are what the human eye needs.
- **Backward compat:** `_plan_dag.py` detects format by type: if all `depends-on:` entries are integers, validate against `number:` values; if all are strings, fall back to name-based validation (old behavior). This keeps tasks 9 and 11 (which have existing plans with name-based deps) working after this task merges to main.

### field-rename-context-edits

- **Decision:** `Reads:` → `Context:`, `Modifies:` → `Edits:`. `Creates:` and `Deletes:` unchanged. Semantics: `Context:` = files read but not changed; `Edits:` = files changed (implicitly also read — must not appear in `Context:`); `Creates:` = new files; `Deletes:` = deleted files.
- **Rationale:** `Context:` signals "read-only background" without ambiguity. `Edits:` is unambiguous about modification. The old `Reads:`+`Modifies:` overlap was the root of the redundancy bug.
- **Rejected:** Keep names, only add a comment — doesn't fix the confusion at source.

### reviewer-asymmetry-documentation

- **Decision:** Document in `review-plan-batch.md` that the plan-reviewer bulks `Context: ∪ Edits:` (existing files only; `Creates:` targets don't exist yet) and the code-reviewer bulks `Context: ∪ Edits: ∪ Creates:`. The code that handles this (`creates_union` suppression in `_review_plan.py`) already works; this is a documentation gap only.
- **Rationale:** The asymmetry is non-obvious; documenting it in the template prevents future confusion when maintaining the review backend.
- **Rejected:** Remove `Creates:` from `parse_batch_refs()` in plan-review context — unnecessary; suppression is already correct.

### requirements-stable-identifiers

- **Decision:** mill-plan SKILL.md mandates stable identifiers (function names, class names, constant names) in `Requirements:` bodies. `Context:` is declared an allowlist: the implementer reads ONLY listed files; a missing file = plan defect. Both rules added to plan-batch template comment and plan-review BLOCKING criteria.
- **Rationale:** Vague Requirements force cold-start implementers to explore, which is the main driver of undeclared reads and "plan is unclear" stuck reports.
- **Rejected:** Stable-identifiers only without allowlist framing — the allowlist is what makes `Context:` useful for cold-start; without it planners still treat it as a hint.

## Technical context

### Repo layout

```
plugins/mill/
  scripts/
    _plan_dag.py         — DAG extraction, validation, topo_order
    _plan_validate.py    — Pre-review validator; check 4 = depends-on-unknown
    _review_common.py    — parse_batch_refs(), _RE_REFS_HEADER regex
    _review_plan.py      — Plan review backend; references Reads/Modifies in docstrings
    _review_code.py      — Code review backend; references Reads/Modifies in docstring line 14
  templates/
    plan-overview.md     — Overview template; batches: YAML block
    plan-batch.md        — Batch template; frontmatter + card field descriptions
    review-plan-batch.md — Per-batch plan review prompt
    review-plan-holistic.md — Holistic plan review prompt
    review-code-batch.md — Per-batch code review prompt
    implementer-brief.md — Implementer session prompt
  skills/
    mill-plan/SKILL.md   — Planner instructions (Phase: Plan + Principles)
  unit_tests/
    test-plan-dag.py     — DAG unit tests; all use name-based depends-on
    test-plan-validate.py — Validator unit tests; use Reads/Modifies/Creates field names
    test-review-common.py — parse_batch_refs tests; use Reads/Modifies/Creates
```

### `_plan_dag.py` key functions

- `extract_batch_index(overview_text)` — parses the `batches:` YAML block, returns `list[dict]`
- `_check_shapes(batches)` — validates each entry has `name:` and `file:`. Currently requires `depends-on:` to be a list of strings.
- `_check_deps(batches)` — validates each `depends-on:` entry against `{entry["name"] for entry in batches}`
- `_check_acyclic(batches)` — Kahn's algorithm using `entry["name"]` as graph keys
- `topo_order(batches)` — returns `list[str]` of names in topological order (mill-go unchanged)
- `iter_batch_verifies(plan_dir)` — uses `entry["name"]` for batch identity

### `_plan_dag.py` required changes (Change A)

`_check_shapes` must:
1. Accept `number:` field when present (optional — old plans won't have it)
2. Validate uniqueness of all `number:` values across entries (when present)
3. Accept `depends-on:` as a list of integers OR strings (not mixed)

`_check_deps` must:
- If `depends-on:` contains integers: validate against `{entry["number"] for entry in batches}`
- If `depends-on:` contains strings: validate against `{entry["name"] for entry in batches}` (old path)
- If mixed types → raise `PlanDAGError`

`_check_acyclic` and `topo_order`:
- When `depends-on:` is integer-based, build adjacency map by translating numbers to names first (using `{entry["number"]: entry["name"] for entry in batches}`). Both functions work on names throughout; the translation is purely internal to `_check_deps` / `_check_acyclic`.

### `_plan_validate.py` key constants and functions

```python
_RE_FIELD_HEADER = re.compile(
    r"^-\s*\*\*(Reads|Modifies|Creates|Deletes):\*\*(?P<inline>.*)$"
)
_REQUIRED_CARD_FIELDS = ["Reads", "Modifies", "Creates", "Deletes", "Requirements", "Commit"]
```

After rename (Change B): `Reads` → `Context`, `Modifies` → `Edits` in both.

`_parse_modifies_only(batch_path)` — extracts `Modifies:` paths for the `parallel-modifies-overlap` check. Rename to `_parse_edits_only`. The caller `_check_parallel_modifies_overlap` (or its equivalent) must call the renamed function.

`_check_depends_on_unknown` (Change A): uses `known_names = {entry["name"] for entry in batches}`. After Change A, also compute `known_numbers = {entry["number"] for entry in batches if "number" in entry}`. Check each `dep` in `entry.get("depends-on", [])` against numbers if integer, names if string.

### `_review_common.py` key regex

```python
_RE_REFS_HEADER = re.compile(
    r"^-\s*\*\*(Reads|Modifies|Creates|Deletes):\*\*(?P<inline>.*)$"
)
```

After Change B: `Reads|Modifies` → `Context|Edits`.

`parse_batch_refs()` docstring mentions "Reads/Modifies/Creates/Deletes" — update to "Context/Edits/Creates/Deletes".

### Template rendering note

`plan-overview.md` and `plan-batch.md` are filled in by mill-plan using `_render.render`. The rendered file content is what gets committed. The template itself (under `plugins/mill/templates/`) is what gets changed in this task. mill-plan's SKILL.md instructions for filling in the templates must also be updated to reflect the new fields.

### Backward compatibility with tasks 9 and 11

Tasks `wiki-enhance` (task 9) and `review-code-enhancements` (task 11) have existing plans at `c:/Code/millhouse/wts/wiki-enhance/plan/` and `c:/Code/millhouse/wts/review-code-enhancements/plan/`. Their plans use:
- Name-based `depends-on:` (strings)
- `Reads:`/`Modifies:` field names

After this task merges to main, those plans will still be valid because:
- `_plan_dag.py` falls back to name-based validation when `depends-on:` entries are strings
- `_plan_validate.py` and `_review_common.py` with the new `Context|Edits` regex will NOT parse their plans' `Reads:`/`Modifies:` fields — those cards will appear to have empty Context/Edits lists

The second point is a silent failure: old plans' `Reads:`/`Modifies:` entries won't be bulked by reviewers after the rename. However, tasks 9 and 11 are already approved and their code review has already run. mill-merge-in replays `iter_batch_verifies()` which reads the batch frontmatter `verify:` field — unaffected by the rename. So merging is safe.

If tasks 9/11 need a new round of code review after this task merges, they would need to update their batch files to use `Context:`/`Edits:`. The plan does not need to address this — it's a known, acceptable limitation for in-flight plans.

### mill-plan SKILL.md relevant sections

Phase: Plan — Principles (end of file):
```
- **Card `Reads:` must be comprehensive** — every file the implementer needs to read, listed. An empty or terse `Reads:` is a review-blocker in the batch-review template. and contain ONLY backtick-wrapped paths in bullet form — no inline prose, no line-range suffixes. Inline notes belong in Requirements: bodies.
```

This must be updated to use `Context:` and strengthened with the allowlist framing.

The mechanical-fix table has:
```
| depends-on-unknown | Compare the unknown name against the Batch Index...
```
Must be updated for integer-based deps.

## Testing

### test-plan-dag.py

All existing tests use string `depends-on`. Add new tests:
- `test_good_plan_with_numbers_accepted` — batches with `number:` field and integer `depends-on: [1]`
- `test_number_dep_unknown_rejected` — `depends-on: [99]` where no batch has `number: 99` → `PlanDAGError`
- `test_number_dep_duplicate_rejected` — two entries with same `number:` value
- `test_mixed_dep_type_rejected` — `depends-on: [1, "other"]` (mixed int/str) → `PlanDAGError`
- `test_old_name_deps_still_valid` — plan without `number:` field and string `depends-on:` still passes (backward compat)
- Update `test_good_plan_accepted` to include `number:` fields (it's the canonical good-plan fixture)

### test-plan-validate.py

- Update all `_make_batch_file` fixtures to use `Context:`/`Edits:` instead of `Reads:`/`Modifies:`
- Update assertions that check for "Modifies" in error messages to check "Edits"
- `test_check_depends_on_unknown`: add a sub-case for integer deps (unknown number → error)

### test-review-common.py

Search for test functions that use `_RE_REFS_HEADER` or test `parse_batch_refs` with `Reads:`/`Modifies:` — update field names to `Context:`/`Edits:`. If existing tests only call `parse_batch_refs` on fixture strings, the fixture strings need updating.

## Q&A log

- **Q:** Should `depends-on` switch from batch names to numbers? **A:** Yes — numbers only. `_plan_dag.py` validates integers against `number:` values, falls back to names for plans without `number:` fields (backward compat).
- **Q:** Should `number:` appear in both the overview block and the batch frontmatter? **A:** Both — batch file must be self-describing.
- **Q:** Rename `Reads:`→`Context:` and `Modifies:`→`Edits:`, or just clarify semantics keeping old names? **A:** Rename.
- **Q:** Reviewer asymmetry for `Creates:` — fix in code or docs only? **A:** Docs only; the code already handles it via `creates_union` suppression in `resolve_ref_paths`.
- **Q:** Stable identifiers in Requirements + Reads-as-allowlist — both? **A:** Both. `Context:` is an allowlist; `Requirements:` must use function/class names.
- **Q:** Run batch plan reviews later (mill-plan)? **A:** No. Local config already overrides `review.plan.batch: null`, which triggers holistic-only mode in `_review_plan.py`. No code change needed for this.
