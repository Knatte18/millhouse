# Batch: config-docs

```yaml
task: "8 (A) — Disable per-batch reviews (config-driven)"
batch: config-docs
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch adds the `review.code.per_batch` config key and updates doc comments in both the live config (`wiki/config.yaml`) and the new-repo template (`plugins/mill/templates/wiki-config.yaml`). It also edits mill-go's SKILL.md to read and honour the new key. No Python code changes — these are text-only edits.

## Cards

### Card 3: mill-go SKILL.md — add per_batch config read and execute gate

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Two edits to `plugins/mill/skills/mill-go/SKILL.md`:

  **Edit 1 — Entry step 3 config reads (currently ends at line 21):**
  After the existing bullet:
  ```
     - `review.code.holistic` — if true, run one holistic code review after all batches approve.
  ```
  Add a new bullet on the next line:
  ```
     - `review.code.per_batch` — if false (missing key defaults to true), skip per-batch code review for all batches.
  ```

  **Edit 2 — Execute loop "### 3. Code Review loop" section (currently line 79):**
  The section currently opens with:
  ```
  - Set batch state → `reviewing`, `review_round: 1`.
  ```
  Insert the following gate as the very first content under "### 3. Code Review loop", before the "Set batch state" line:

  ```
  If `review.code.per_batch` is false: set batch state → `approved`, `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: approve batch {batch_name} (per-batch review disabled)"`, and continue to the next batch. Skip the rest of this section.

  ```

  The gate must appear before the "Set batch state → `reviewing`" line so that when per_batch is false, no `reviewing` phase is ever written to status.md.

- **Commit:** `docs(mill-go): add review.code.per_batch config read and execute gate`

### Card 4: config doc comments and new per_batch key

- **Reads:**
  - `wiki/config.yaml`
  - `plugins/mill/templates/wiki-config.yaml`
- **Modifies:**
  - `wiki/config.yaml`
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Apply identical edits to both files (the review block structure is the same in both).

  **Edit A — plan.batch comment:**
  Current line (in both files):
  ```yaml
      batch: sonnetmax            # per-batch reviewer; MODE must be "bulk"
  ```
  Replace with:
  ```yaml
      batch: sonnetmax            # per-batch reviewer; MODE must be "bulk". null = skip per-batch (holistic must be set)
  ```

  **Edit B — add per_batch key after holistic in code block:**
  Current lines in the `code:` block (in both files):
  ```yaml
      holistic: true              # run one end-of-task holistic code review after all batches approve
      self_fix_rounds: 2
  ```
  Replace with:
  ```yaml
      holistic: true              # run one end-of-task holistic code review after all batches approve
      per_batch: true             # false = skip per-batch code review; holistic gate is independent
      self_fix_rounds: 2
  ```

  Note: `wiki/config.yaml` uses `# per-batch reviewer; MODE must be "bulk"` comment padding to align with existing comments (match existing style — do not adjust other lines' spacing). The template file (`wiki-config.yaml`) uses `sonnetmax_tool` for the discussion reviewer but `sonnetmax` for plan/code, same as the live config — do not change reviewer names.

  Back-compat: existing live configs that already have `batch: sonnetmax` without `per_batch` will continue to behave as before — the key is read with `.get("per_batch", True)` in the mill-go SKILL.md (the default-true fallback is stated in Card 3's gate text).

- **Commit:** `docs(config): add review.code.per_batch key and null-batch comment`

## Batch Tests

`verify: null` — no runnable test surface for YAML and Markdown edits. Correctness is validated by the plan reviewer reading the files.
