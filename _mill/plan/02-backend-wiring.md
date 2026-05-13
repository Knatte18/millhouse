# Batch: backend-wiring

```yaml
task: "(B) — Size-based reviewer switch (mechanism + configurable target)"
batch: backend-wiring
number: 2
cards: 4
verify: null
depends-on: [1]
```

## Batch Scope

This batch wires `maybe_switch_spec_for_large_prompt` (added in batch 1) into the holistic review paths of all three backends and adds the `large_prompt:` schema documentation to `wiki-config.yaml` template. After this batch the switch is fully functional end-to-end. No unit tests are included here — those are in batch 3.

Batch-local decision: the switch call is placed after `prompt_text = render_prompt(...)` but before the first `_reviewer_single.run(...)` call. The `reviewer_name` variable is updated so any NEED_CONTEXT retry that uses `spec` also gets the override — the retry prompt never re-embeds `reviewer_model`, so no re-render is needed.

## Cards

### Card 3: Wire helper in `_review_discussion.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In the `from _review_common import (` block (lines 20-32), add `maybe_switch_spec_for_large_prompt` to the import list. Place it alphabetically (between `load_task_title` and `parse_blocking_count`).
  2. After `prompt_text = render_prompt(...)` (lines 95-103) and before the `# 5. Invoke reviewer` comment (line 105), insert:
     ```python
     spec, reviewer_name = maybe_switch_spec_for_large_prompt(
         prompt_text, spec, reviewer_name, cfg, "discussion-review", "holistic", registry
     )
     ```
  3. `spec` is the variable defined at line 76 (`spec = _reviewers.resolve(registry, reviewer_name)`). `reviewer_name` is defined at line 72 (`reviewer_name = cfg["roles"]["discussion-review"]["holistic"]["reviewer"]`). Both are in scope at the insertion point.
  4. The existing `_reviewer_single.run(spec, prompt_text)` at line 109 will automatically use the (possibly updated) `spec`.
  5. No re-render of `prompt_text` is required — the reviewer model logged in the review file is an operational detail; the effective spec is what actually runs.

- **Commit:** `feat(review-discussion): wire large-prompt reviewer switch in holistic path`

### Card 4: Wire helper in `_review_plan.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In the `from _review_common import (` block near the top of the file, add `maybe_switch_spec_for_large_prompt` to the import list alphabetically.
  2. In the holistic path, after `prompt_text = render_prompt("review-plan-holistic", ...)` (lines 487-495) and before `try: raw, session_id = _reviewer_single.run(holistic_spec, prompt_text, timeout=holistic_timeout)` (line 498), insert:
     ```python
     holistic_spec, holistic_name = maybe_switch_spec_for_large_prompt(
         prompt_text, holistic_spec, holistic_name, cfg, "plan-review", "holistic", registry
     )
     ```
  3. `holistic_spec` is defined at line 329-331 (`holistic_spec = _reviewers.resolve(registry, holistic_name)`). `holistic_name` is defined at line 327 (`holistic_name = cfg["roles"]["plan-review"]["holistic"]["reviewer"]`). Both are in scope at the insertion point.
  4. The NEED_CONTEXT retry at line ~531 uses `holistic_spec` directly — since the variable is updated before the first call, the retry automatically uses the override spec. No additional changes needed in the retry path.
  5. Do NOT touch the per-batch path (`_review_one_batch` function or any code under the batch-review branch). The switch is holistic-only.

- **Commit:** `feat(review-plan): wire large-prompt reviewer switch in holistic path`

### Card 5: Wire helper in `_review_code.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In the `from _review_common import (` block (lines 39-63), add `maybe_switch_spec_for_large_prompt` to the import list alphabetically.
  2. In the `run()` function, after `prompt_text = render_prompt(template_name, **prompt_kwargs)` (line 306) and before `# 5. Dispatch + record` (line 308), insert:
     ```python
     if batch_name is None:
         spec, reviewer_name = maybe_switch_spec_for_large_prompt(
             prompt_text, spec, reviewer_name, cfg, "code-review", "holistic", registry
         )
     ```
  3. `spec` is defined at lines 280-281 (`spec = _reviewers.resolve(registry, reviewer_name)`). `reviewer_name` is set at lines 272-274 (batch vs holistic branch). `registry` is set at line 280 (`registry = _reviewers.load(wiki_root)`). All are in scope at the insertion point.
  4. The NEED_CONTEXT retry at line ~347 uses `spec` directly — since the variable is updated before the first call, the retry automatically uses the override spec. No additional changes needed in the retry path.
  5. The guard `if batch_name is None` ensures the switch never fires in per-batch mode. Both the `batch_name is not None` and `batch_name is None` branches share the same `spec` variable, but the switch block is only reached when `batch_name is None`.

- **Commit:** `feat(review-code): wire large-prompt reviewer switch in holistic path`

### Card 6: Document `large_prompt` schema in `wiki-config.yaml` template

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  The template's `roles:` section currently has `holistic:` blocks for three roles. After the `reviewer:` line inside each `holistic:` block, add three commented-out lines documenting the `large_prompt` key.

  For `discussion-review.holistic` (currently ends with `reviewer: sonnetmax_tool`), add:
  ```yaml
      # large_prompt:            # optional: override reviewer for large prompts
      #   threshold_ktok: 100    # switch when estimated tok count >= this (char/4000)
      #   reviewer: null         # override reviewer from reviewers.yaml; null = disabled
  ```

  For `plan-review.holistic` (currently ends with `reviewer: sonnetmax`), add the same three lines.

  For `code-review.holistic` (currently ends with `reviewer: sonnetmedium`), add the same three lines.

  The comment block uses 4-space indentation (matching the `reviewer:` line it follows). The comment explains that `reviewer: null` disables the switch (the default). Operators enable it by setting a non-null reviewer name from `reviewers.yaml`.

  Do NOT add `large_prompt:` blocks under `batch:` scopes — the switch is holistic-only and no batch-level config key exists.

- **Commit:** `docs(template): add large_prompt schema comment to wiki-config.yaml roles`

## Batch Tests

`verify: null` — this batch only modifies call sites in the three backend modules and a comment-only template edit. The actual switch logic is in batch 1 and tested in batch 3. There is no isolated test surface for call-site wiring beyond running a real review, which requires a live LLM.
