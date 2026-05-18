# Batch: templates-config-skills

```yaml
task: '64 (A) -- Small infra fixes batch 9'
batch: templates-config-skills
number: 4
cards: 4
verify: null
depends-on: []
```

## Batch Scope

Four documentation / configuration fixes with no runtime test surface. Card 12 renames
the YAML-bound tokens in `plan-overview.md` and `plan-batch.md` so the H1 heading and
the fenced-yaml block receive differently-named tokens, allowing mill-plan to supply the
raw form for H1 and the `quote_scalar`-wrapped form for YAML. Card 13 updates
`mill-plan/SKILL.md` to supply both raw and YAML-quoted variants in its token dict.
Card 14 adds `model: haiku` to the template `mill-config.yaml` and `model: sonnethigh`
to the hub `mill-config.yaml`, and updates `millpy-merge-in-subagent.py` to read the new
key with a backward-compatible fallback. Card 15 fixes mill-go SKILL.md: corrects the
`load_config` argument order in Step 3 and adds per-invocation venv-check blocks before
each `millpy-bg.py` call.

Verify is null because all changes are in templates, config files, and SKILL.md — no
runnable test surface.

## Cards

### Card 12: Rename YAML-bound tokens in `plan-overview.md` and `plan-batch.md`

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  **`plan-overview.md`:**
  - Line 5 (Tokens comment): change `Tokens: <TASK_TITLE>, <SLUG>, <STARTED>, <PARENT_BRANCH>.`
    to `Tokens: <TASK_TITLE>, <TASK_TITLE_YAML>, <SLUG>, <STARTED>, <PARENT_BRANCH>.`
  - Line 27 (inside the fenced yaml block): change `task: <TASK_TITLE>` to
    `task: <TASK_TITLE_YAML>`.
  - Line 24 (H1): `# Plan: <TASK_TITLE>` — leave unchanged.

  **`plan-batch.md`:**
  - Line 5 (Tokens comment): change `Tokens: <TASK_TITLE>, <BATCH_NAME>, <BATCH_SLUG>.`
    to `Tokens: <TASK_TITLE>, <TASK_TITLE_YAML>, <BATCH_NAME>, <BATCH_NAME_YAML>, <BATCH_SLUG>.`
  - Line 21 (inside the fenced yaml block): change `task: <TASK_TITLE>` to
    `task: <TASK_TITLE_YAML>`.
  - Line 22 (inside the fenced yaml block): change `batch: <BATCH_NAME>` to
    `batch: <BATCH_NAME_YAML>`.
  - Line 18 (H1): `# Batch: <BATCH_NAME>` — leave unchanged.
- **Commit:** `fix(templates): introduce TASK_TITLE_YAML and BATCH_NAME_YAML tokens for YAML blocks`

### Card 13: Update mill-plan SKILL.md token dict — raw heading + quoted YAML variants

- **Context:**
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In Phase: Plan, in the code block that builds the `tokens` dict for `plan-overview.md`
  rendering:

  Change:
  ```python
  tokens = {
      "TASK_TITLE":    quote_scalar(task_title),
      "SLUG":          quote_scalar(slug),
      "STARTED":       quote_scalar(_timestamp.now_utc_compact()),
      "PARENT_BRANCH": quote_scalar(parent_branch),
  }
  ```
  to:
  ```python
  tokens = {
      "TASK_TITLE":      task_title,
      "TASK_TITLE_YAML": quote_scalar(task_title),
      "SLUG":            quote_scalar(slug),
      "STARTED":         quote_scalar(_timestamp.now_utc_compact()),
      "PARENT_BRANCH":   quote_scalar(parent_branch),
  }
  ```

  For the per-batch `plan-batch.md` rendering, add `BATCH_NAME_YAML` and change
  `BATCH_NAME` to raw:
  ```python
  tokens["BATCH_NAME"]      = batch_name
  tokens["BATCH_NAME_YAML"] = quote_scalar(batch_name)
  tokens["BATCH_SLUG"]      = batch_slug
  ```
  (Remove `quote_scalar` wrapping from `BATCH_NAME`; add new `BATCH_NAME_YAML` with it.)

  The prose above the code block that says "Pre-quote YAML-bound tokens" and refers to
  `<TASK_TITLE>` and `<BATCH_NAME>` going through `quote_scalar` should be updated to
  reflect that `<TASK_TITLE_YAML>` and `<BATCH_NAME_YAML>` are the YAML-quoted tokens
  and `<TASK_TITLE>` / `<BATCH_NAME>` are now the raw heading tokens.
- **Commit:** `fix(mill-plan): supply raw TASK_TITLE + quoted TASK_TITLE_YAML in token dict`

### Card 14: Add `merge.model` to config files and update `millpy-merge-in-subagent.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  **`plugins/mill/templates/mill-config.yaml`** — under the `merge:` block (around
  line 179, which currently has `verify_fix_rounds: 3`), add:
  ```yaml
  model: haiku
  ```
  immediately after `verify_fix_rounds: 3` (or before it, consistent with the
  surrounding style). Add a one-line comment above it:
  `# model: LLM alias for the merge-in sub-agent (haiku is sufficient for conflict resolution)`

  **`mill-config.yaml`** (hub root) — under the `merge:` block (around line 49, which
  currently has `verify_fix_rounds: 3`), add:
  ```yaml
  model: sonnethigh
  ```
  No documentation comment needed in the hub override file.

  **`plugins/mill/scripts/millpy-merge-in-subagent.py`** — around line 154-155:
  Change:
  ```python
  implementer_cfg = cfg.get("roles", {}).get("implementer", {})
  model_name = implementer_cfg.get("model", "sonnethigh")
  ```
  to:
  ```python
  implementer_cfg = cfg.get("roles", {}).get("implementer", {})
  model_name = cfg.get("merge", {}).get("model") or implementer_cfg.get("model", "haiku")
  ```
  The `or` fallback ensures backward compatibility for hubs that don't yet have
  `merge.model` configured.
- **Commit:** `feat(merge): add merge.model config key; default haiku, sonnethigh in hub`

### Card 15: Fix mill-go SKILL.md — load_config arg order + venv-check blocks

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  **Fix 1 — load_config arg order (Step 3):** Locate the line:
  ```
  _review_common.load_config(wiki_path, Path(".millhouse"))
  ```
  Change it to:
  ```
  _config.load_config(worktree_root, worktree_root)
  ```
  where `worktree_root = _paths.resolve_git_root()` (already established in Step 2).
  `_config.load_config(repo_root, worktree_root)` takes the git root as BOTH arguments
  when hub and worktree are the same directory; the function internally appends
  `.millhouse/config.local.yaml` to the second argument, so passing
  `worktree_root / ".millhouse"` would double-nest it.
  Update any surrounding prose that refers to `_review_common.load_config` to use
  `_config.load_config`.

  **Fix 2 — venv-check before per-batch millpy-bg call:** Locate the batch-loop section
  where `millpy-bg.py` is invoked for per-batch implementation. Immediately before that
  invocation, add the following bash block:
  ```bash
  if [ ! -f "$MILL_PYTHON" ]; then
      echo "[mill-go] venv missing at $MILL_PYTHON -- attempting uv sync"
      uv sync --project "${PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
      if [ ! -f "$MILL_PYTHON" ]; then
          echo "HALT: MILL_PYTHON not found at $MILL_PYTHON -- venv lost mid-session. Run 'uv sync --project ${PLUGIN_ROOT}' manually."
          exit 1
      fi
  fi
  ```

  **Fix 3 — venv-check before holistic review millpy-bg call:** Locate the holistic
  review section where `millpy-bg.py` is invoked. Add the same venv-check block
  (with `${PLUGIN_ROOT}` in the message, not the literal `plugins/mill`) immediately
  before that invocation.

  The venv-check block is identical in both locations. Do NOT add it elsewhere (step 0
  already performs the initial check; only the per-invocation sites need it).
- **Commit:** `fix(mill-go): correct load_config arg order; add per-invocation venv checks`

## Batch Tests

Verify is null — all changes are in templates (`.md`), config (`.yaml`), and SKILL.md
files with no runnable test surface. Manual spot-check for card 12/13: render a
`plan-overview.md` template with a title containing a colon (`foo: bar`) and verify
the H1 is raw (`# Plan: foo: bar`) while the YAML block has the quoted form.
