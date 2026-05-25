# Batch: verify-isolation

```yaml
task: Isolate verify PYTHONPATH so tests validate worktree code
batch: verify-isolation
number: 1
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

The entire task lands in one batch because the change is small and tightly coupled: a new `_plan_validate.py` check plus the documentation, templates, and SKILL.md guidance that explain why the check exists. Sonnet can hold the whole change-set in context without paging. TDD ordering: card 1 writes the failing unit tests, card 2 adds the function that makes them pass, cards 3-6 propagate the rule into the planner's authoring surface (SKILL.md, templates, and CLAUDE.md). No external interface is exposed for downstream batches; this batch is the entire task.

## Cards

### Card 1: Add unit tests for `_check_verify_not_isolated`

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add the following test functions to `test-plan-validate.py`, registered in `main()`'s `tests` list (see line 1333-1374 for the existing list shape). Use `tempfile.TemporaryDirectory` + the existing `_make_overview` / `_make_batch_file` / `_write_plan` helpers wherever they fit; for cases that need a specific `verify:` value, hand-roll the batch-file text in the test (mirror the pattern in `test_depends_on_batch_mismatch_no_finding_on_match` at lines 1230-1273 — that test already hand-rolls a batch file with a custom yaml block).
  - `test_check_verify_not_isolated_null` — per-batch frontmatter `verify: null` -> no `verify-not-isolated` error.
  - `test_check_verify_not_isolated_missing_key` — per-batch frontmatter that omits `verify:` entirely -> no `verify-not-isolated` error.
  - `test_check_verify_not_isolated_dirty_no_prefix` — per-batch frontmatter `verify: uv run --project plugins/mill python ...` (no prefix) -> exactly one error from `_plan_validate.run(plan_dir, project_root)` with `e["check"] == "verify-not-isolated"`. Assert the 5-key envelope: `e["batch"]` equals the batch file's stem (e.g. `01-alpha`), `e["card"] is None`, `e["path"]` equals the full offending verify string, `e["message"] == "verify command missing PYTHONPATH= prefix"`.
  - `test_check_verify_not_isolated_clean_with_prefix` — per-batch frontmatter `verify: PYTHONPATH= uv run ...` -> no `verify-not-isolated` error.
  - `test_check_verify_not_isolated_two_batches_dirty` — two batch files both unprefixed -> exactly two `verify-not-isolated` errors, one per batch, each with the right `batch:` stem.
  - `test_check_verify_not_isolated_leading_whitespace` — per-batch frontmatter `verify:   PYTHONPATH= uv run ...` (extra leading whitespace before `PYTHONPATH=`, valid yaml because the value side is what matters) -> no error (the check uses `.strip()` before `.startswith()`).
  - `test_check_verify_not_isolated_non_empty_pythonpath_value` — per-batch frontmatter `verify: PYTHONPATH=/some/path uv run ...` -> no error (the check requires the `PYTHONPATH=` token at start, not a specific value).
  - `test_check_verify_not_isolated_run_integration` — invoke `_plan_validate.run(plan_dir, project_root)` (not the check function directly) with one unprefixed batch; assert the final sorted error list contains the `verify-not-isolated` error with all 5 keys present and no `KeyError` was raised. This guards against future code that drops a key on the envelope.
- **Commit:** `test(test-plan-validate): add verify-not-isolated check coverage`

### Card 2: Add `_check_verify_not_isolated` to `_plan_validate.py`

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new check function `_check_verify_not_isolated(batch_files: list[Path]) -> list[dict]` to `_plan_validate.py`. Place it alongside the other `_check_*` functions, before `run()`. Body:
  - Iterate `batch_files`. For each `batch_path`, read text with `batch_path.read_text(encoding="utf-8")`. Extract the leading fenced ` ```yaml ` block using the same inline pattern in `_check_depends_on_batch_mismatch` at `_plan_validate.py:534-549`: scan lines, find ```` ```yaml ```` then the next ```` ``` ```` , `yaml.safe_load("\n".join(lines[start+1:end]))` -> `parsed: dict`. Pass through (treat as missing key) on parse error or missing block.
  - Read `verify = parsed.get("verify")`. If `verify` is `None`, missing, or not a non-empty string after `.strip()` -> continue. Otherwise check `verify.strip().startswith("PYTHONPATH=")`. On `False`, append:
    ```python
    {
        "check": "verify-not-isolated",
        "batch": batch_path.stem,
        "card": None,
        "path": verify,
        "message": "verify command missing PYTHONPATH= prefix",
    }
    ```
  - Return the accumulated list.
  - Register the new check in `run()` (`_plan_validate.py:842-853`) by adding `errors.extend(_check_verify_not_isolated(batch_files))` after the existing `_check_depends_on_batch_mismatch` extend call. Position is not load-bearing — `run()` sorts at the end — but grouping batch-scoped checks together keeps the file readable.
  - Add the new check name to the module-level docstring's "Checks performed" list (`_plan_validate.py:13-30`) with a one-line description: `verify-not-isolated         -- per-batch frontmatter verify: command does not start with PYTHONPATH= reset prefix`.
- **Commit:** `feat(_plan_validate): add verify-not-isolated check`

### Card 3: Document the prefix rule in mill-plan SKILL.md

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Two changes in `plugins/mill/skills/mill-plan/SKILL.md`:
  1. In Phase: Plan, after the "Card numbering is global across batches" paragraph (around the place that explains how to write `Requirements:` content) and before the "Self-validate the DAG" paragraph, add a new paragraph titled **Verify command shape**: "Every non-null `verify:` in a per-batch file's frontmatter MUST start with the literal token `PYTHONPATH=` followed by a single space and then the command — e.g. `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. The empty value on the same line scopes the `PYTHONPATH` reset to that one command, so the test subprocess does not inherit the mill cache scripts dir from the parent shell and tests load worktree modules instead of stale cache modules. The validator check `verify-not-isolated` enforces this; see the Step 1.5 fix table." The exact location (anchor on the line that begins "Card numbering is global across batches") is non-negotiable so the reviewer reads the rule before reading the validation step.
  2. In Phase: Plan Review -> Step 1.5 fix table (the multi-row table starting around `_plan_validate.py:102`), add a new row between `all-files-touched-mismatch` and `wiki-config-mutation`:

     | check                          | mechanical fix                                                                                                  |
     | ------------------------------ | ----------------------------------------------------------------------------------------------------------- |
     | verify-not-isolated            | Open the per-batch file named by the error payload's `batch:` field (resolve `_mill/plan/<batch>.md`). Read the offending command from the payload's `path:` field. Replace the frontmatter line `verify: <original>` with `verify: PYTHONPATH= <original>` (literal `PYTHONPATH=`, single space, original command). One row, one prepend. |

  Use the same column shape and prose style as the surrounding rows. ASCII only.
- **Commit:** `docs(mill-plan): document verify PYTHONPATH= prefix + add validator fix row`

### Card 4: Update plan templates to show the prefix

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - `plugins/mill/templates/plan-overview.md`: change the Batch Index example line `verify: <command or null>` (around line 48) to `verify: PYTHONPATH= <command> or null`. Leave the top-level frontmatter line `verify: null` (line 33) unchanged -- top-level `verify:` is documentation-only and the validator does not check it; the example consistency in the mirror block is purely for human readers.
  - `plugins/mill/templates/plan-batch.md`: leave the frontmatter line `verify: null` (line 25) as-is, but add a leading-comment guidance line inside the HTML comment at the top of the file (the existing `<!-- ... -->` block at lines 1-17): append before the `Strip this HTML comment before writing.` line a new line reading `Non-null verify: commands MUST start with "PYTHONPATH= " (empty value, single space) so the test subprocess does not inherit the cache PYTHONPATH. The validator check verify-not-isolated enforces this.` The template comment is stripped by `_render.render` before substitution (see `_render._strip_leading_comment`), so this guidance reaches the planner LLM through SKILL.md + the visible template body, not the rendered plan file.
- **Commit:** `docs(templates): show PYTHONPATH= prefix in plan templates`

### Card 5: Add prefix comment to mill-config.yaml template

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/templates/mill-config.yaml`, locate the existing block at lines 192-201 ("mill-merge-in: verify allowlist" section). Insert a new comment-only block immediately above that block (so the verify-related comments stay grouped) with the following content (keep `#`-prefix comment style; ASCII only; do not introduce any new yaml keys):
  ```yaml
  # ---------------------------------------------------------------------------
  # verify command shape (canonical, enforced by _plan_validate.verify-not-isolated)
  # ---------------------------------------------------------------------------
  # Every non-null verify: in a per-batch plan file's frontmatter MUST start
  # with the literal token "PYTHONPATH=" followed by a single space and the
  # command. Example:
  #     verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  # The empty value on the same line scopes the PYTHONPATH reset to that one
  # command, so the test subprocess does not inherit the mill plugin-cache
  # scripts dir (set by every mill skill's PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"
  # invocation pattern). Without this reset, tests load V2-cache modules
  # instead of the worktree code they are meant to validate.
  # This is schema documentation only -- no key change here; the planner
  # bakes the prefix into each per-batch verify: command per mill-plan SKILL.
  ```
  No other lines in `mill-config.yaml` change. Run `yaml.safe_load(path.read_text())` mentally to confirm comments-only edits do not break the YAML.
- **Commit:** `docs(mill-config): document verify PYTHONPATH= prefix as schema comment`

### Card 6: Add verify-isolation note to root CLAUDE.md

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the project-root `CLAUDE.md`, locate the `## Script invocation` section. Append one new paragraph at the end of that section (after the existing "Exceptions:" sentence), reading exactly:

  > **Verify command shape.** Plan files' `verify:` commands MUST start with `PYTHONPATH=` (literal, empty value, single space) so the test subprocess does not inherit the cache `PYTHONPATH` and load V2-cache modules instead of worktree code. Enforced by `_plan_validate.py`'s `verify-not-isolated` check; mill-plan auto-prepends the prefix on validator failure.

  Place this as a new paragraph (blank line above and below); do not merge into the existing "Cache form" paragraph. ASCII only (no em-dash, no smart quotes).
- **Commit:** `docs(CLAUDE): document verify PYTHONPATH= prefix in Script invocation`

## Batch Tests

The batch's frontmatter `verify:` runs `plugins/mill/unit_tests/test-plan-validate.py` with `PYTHONPATH=` reset, executing every test in `main()`'s `tests` list. After cards 1-2 land, the seven new `test_check_verify_not_isolated_*` functions exercise the new check; the eighth (`test_check_verify_not_isolated_run_integration`) covers the end-to-end `_plan_validate.run()` path including the `errors.sort()` step that depends on the 5-key envelope. Cards 3-6 are documentation-only and have no runnable surface, but they ship in the same batch because their content is derived directly from the validator's behaviour — splitting them out would create a stale-doc-vs-code window for no benefit.
