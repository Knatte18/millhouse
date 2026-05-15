# Batch: wiki-and-template

```yaml
task: Make implementer model configurable via config.yaml
batch: wiki-and-template
number: 2
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Renames `wiki/reviewers.yaml` to `wiki/agents.yaml` (adding the `haiku` entry), adds `roles.implementer.model: sonnethigh` to `wiki/config.yaml`, and updates the `wiki-config.yaml` template to match. All wiki mutations happen inside a `_wiki.wiki_lock` block and are committed atomically to the wiki repo via `git -C wiki_path`. The worktree template file is committed to the task branch separately.

`verify: null` — no unit tests cover live wiki file operations.

---

### Card 4: Rename `wiki/reviewers.yaml` → `wiki/agents.yaml`; add haiku; update `wiki/config.yaml`

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Implement as a standalone Python script run directly (not as part of a review or plan pipeline). Use the following sequence:

  ```python
  import yaml
  from pathlib import Path
  import _paths, _wiki, _subprocess_util

  git_root = _paths.resolve_git_root()
  wiki_path = _paths.resolve_wiki_path(git_root)

  with _wiki.wiki_lock(wiki_path, slug="implementer-model-config"):
      # Step 1: read existing reviewers.yaml
      old_path = wiki_path / "reviewers.yaml"
      registry = yaml.safe_load(old_path.read_text(encoding="utf-8")) or {}

      # Step 2: add haiku entry (no effort field)
      registry["haiku"] = {
          "type": "single",
          "provider": "claude",
          "model": "claude-haiku-4-5-20251001",
      }

      # Step 3: write agents.yaml
      new_path = wiki_path / "agents.yaml"
      new_path.write_text(
          yaml.safe_dump(registry, default_flow_style=False, allow_unicode=True, sort_keys=True),
          encoding="utf-8",
      )

      # Step 4: delete reviewers.yaml
      old_path.unlink()

      # Step 5: update wiki/config.yaml — add model: sonnethigh under roles.implementer
      cfg_path = wiki_path / "config.yaml"
      cfg_text = cfg_path.read_text(encoding="utf-8")
      # Find "    self_fix_rounds: 2" under roles.implementer and append the model key
      # Use string replacement (preserves comments):
      cfg_text = cfg_text.replace(
          "    self_fix_rounds: 2\n",
          "    self_fix_rounds: 2\n    model: sonnethigh\n",
          1,  # replace only the first occurrence (under roles.implementer)
      )
      if "model: sonnethigh" not in cfg_text:
          raise RuntimeError(
              "wiki/config.yaml edit failed: 'model: sonnethigh' not found after "
              "replacement — check indentation of 'self_fix_rounds' line"
          )
      cfg_path.write_text(cfg_text, encoding="utf-8")

      # Step 6: stage and commit
      _subprocess_util.run(["git", "-C", str(wiki_path), "add", "-A"])
      _subprocess_util.run([
          "git", "-C", str(wiki_path), "commit",
          "-m", "feat(agents.yaml): rename reviewers.yaml to agents.yaml; add haiku; add roles.implementer.model",
      ])
      # Step 7: push
      _subprocess_util.run(["git", "-C", str(wiki_path), "push"])
  ```

  Run this script from the worktree root. Verify it succeeds (exit 0 on all subprocess calls). After the commit, `wiki/agents.yaml` must contain all the original entries from `reviewers.yaml` plus `haiku`, sorted alphabetically. `wiki/reviewers.yaml` must no longer exist.
- **Commit:** (no worktree commit for this card — changes land in the wiki repo)

---

### Card 5: Update `plugins/mill/templates/wiki-config.yaml`

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Two changes to `plugins/mill/templates/wiki-config.yaml`:

  1. Under the `roles.implementer:` section, add `model: sonnethigh` after `self_fix_rounds: 2`:
     ```yaml
       implementer:
         self_fix_rounds: 2
         model: sonnethigh
     ```

  2. Find any comment in the file that references `reviewers.yaml` and update it to reference `agents.yaml`. In particular, the line:
     ```
     # Reviewer names reference wiki/reviewers.yaml entries.
     ```
     becomes:
     ```
     # Reviewer names reference wiki/agents.yaml entries.
     ```
     Search the full file for all occurrences of `reviewers.yaml` in comments and update each one.
- **Commit:** `feat(wiki-config): add roles.implementer.model; update reviewers.yaml refs to agents.yaml`

## Batch Tests

`verify: null` — wiki file operations are not covered by unit tests. Correct behavior can be confirmed by inspecting `wiki/agents.yaml` and `wiki/config.yaml` after the batch runs.
