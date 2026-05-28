<!--
Template: `<WIKI_PATH>/active/<slug>/plan/NN-<batch-slug>.md` — written
by mill-plan once per batch during Phase: Plan.

Tokens: <TASK_TITLE>, <TASK_TITLE_YAML>, <BATCH_NAME>, <BATCH_NAME_YAML>, <BATCH_SLUG>.

Each batch is a Sonnet-sized unit of implementation. A batch groups
cards that logically hang together and that a single Sonnet session
can implement in one go, keeping context well under the 200k window.
There is no hard cap on cards — the planner picks what makes sense.
Fill every section; no heading-only skeletons.

Replace `NN` in `number: NN` with the integer from the batch filename
(e.g., `02-field-rename.md` → `number: 2`).

Non-null verify: commands MUST start with "PYTHONPATH= " (empty value, single space) so the test subprocess does not inherit the cache PYTHONPATH. The validator check verify-not-isolated enforces this.

verify: scope MUST match what the batch touches — usually a single test file or a `--only` list (e.g. `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fold.py test-marker.py`). Unbounded `run-all.py` runs the entire suite (multiple minutes); use it only when the batch genuinely touches a cross-cutting helper and justify the scope choice in the ## Batch Tests section.

Strip this HTML comment before writing.
-->
# Batch: <BATCH_NAME>

```yaml
task: <TASK_TITLE_YAML>
batch: <BATCH_NAME_YAML>
number: NN
cards: 0
verify: null
depends-on: []
```

## Batch Scope

_One paragraph stating what this batch delivers and why it is one
batch. Call out the external interface (if any) the next batch will
consume. List the batch-local decisions that differ from `## Shared
Decisions` in the overview._

## Cards

_One `### Card N` per card. Cards are logical sub-sections, not files.
Number cards globally across all batches (no restart-from-1 inside
each batch) so the reviewer and implementer can cite card numbers
unambiguously. Fields per card:_

- **Context:** every file the implementer reads but does not change. Non-empty. One backtick-wrapped path per indented bullet. Context: is an allowlist — the implementer reads ONLY the files listed here. A file needed but not listed is a plan defect. Files listed in Edits: are implicitly read — do not repeat them in Context:.
- **Edits:** files the implementer changes (implicitly also read — do not repeat in Context:). One backtick-wrapped path per indented bullet.
- **Creates:** files the implementer creates. One backtick-wrapped path per indented bullet. When a field has nothing, write the literal "none" on the same line as the field label.
- **Deletes:** files the implementer deletes. One backtick-wrapped path per indented bullet. Multi-line bullet form supported. When a field has nothing, write the literal "none" on the same line as the field label.
- **Requirements:** what the card must achieve. Use stable identifiers — name the specific function, class, or constant being added, changed, or deleted (e.g., "replace `_load_config` in `mill-claim.py` with `from _config import load_config`"). Never write vague prose ("refactor X") without the specific identifier. Exact assertion shapes live in tests, not here.
- **Commit:** one-line commit message the implementer will use.

Context/Edits/Creates/Deletes fields contain ONLY backtick-wrapped paths in bullet form. No inline parenthetical commentary, no line-range suffixes (e.g. ":55-65"). Inline notes belong in Requirements:. When a field has nothing, write the literal "none" on the same line as the field label.

Note for reviewers: the plan-reviewer bulks `Context: ∪ Edits:` (existing files only; `Creates:` targets do not exist yet). The code-reviewer bulks `Context: ∪ Edits: ∪ Creates:` (all files exist post-implementation).

### Card N: <short title>

- **Context:**
  - `path/a`
  - `path/b`
- **Edits:**
  - `path/c`
- **Creates:**
  - `path/d`
- **Deletes:** none
- **Requirements:** …
- **Commit:** `<type>(<scope>): <summary>`

## Batch Tests

_How the batch as a whole is verified. If `verify:` in the frontmatter
runs a test suite, name the files it covers. If `verify: null`, state
why (e.g. pure docs batch with no runnable surface)._
