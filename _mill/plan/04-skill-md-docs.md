# Batch: skill-md-docs

```yaml
task: "Sub-project repo (hub_relative_path) support"
batch: "skill-md-docs"
number: 4
cards: 1
verify: null
depends-on: [1]
```

## Batch Scope

This batch corrects every SKILL.md document that propagated the `repo_root` / `wiki_path` naming bug and the related mill-go step-4.5 worktree_root derivation error. All edits are pure markdown; no Python runs against the changes, so `verify:` is null. The batch depends on batch 1 because the renamed arg `hub_root` is the canonical name being documented — running this batch before batch 1 would land docs ahead of the code.

Five SKILL.md files are edited; each edit is small (one-line signature change or one-paragraph prose update). One card consolidates all edits because they are conceptually one change (align documentation with the corrected helper signatures).

Batch-local decisions:
- No code is touched; no tests run.
- Where a SKILL.md edits a code snippet inside a fenced block, preserve the surrounding fence and indentation exactly.

## Cards

### Card 11: align SKILL.md docs with hub_root signatures and resolve_active_hub usage

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the following edits exactly as discussed in `_mill/discussion.md` `### mill-go SKILL.md edits`, `### mill-finalize SKILL.md fix`, and `### Other SKILL.md edits`:
  - `mill-start/SKILL.md:49` — change the signature annotation line `signature: _config.load_config(wiki_path: Path, worktree_root: Path) -> dict` to `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict`. The annotation appears as part of step 3 (the load-config step). The prose `Load config -- deep-merge` may also reference `<WIKI_PATH>/config.yaml` -- update that prose to `deep-merge <hub_root>/mill-config.yaml with .millhouse/config.local.yaml` consistent with the actual loader behaviour.
  - `mill-plan/SKILL.md:19` — same signature annotation correction as mill-start. Also update the surrounding prose if it references `<WIKI_PATH>/config.yaml` to instead describe the hub-overlay layering.
  - `mill-merge-in/SKILL.md:56` — change `cfg = _config.load_config(wiki_path, git_root)` to `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`. If `wiki_path` is established as a local variable earlier in the step, the prose must still pass `_paths.resolve_hub_path()` -- do not leave `wiki_path` as the first arg. Leave the second arg `git_root` unchanged.
  - `mill-go/SKILL.md` — two locations:
    1. Step 3 (line 25): change `_review_common.load_config(_paths.resolve_git_root(), Path(".millhouse"))` to `_review_common.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path() / ".millhouse")`. The previous form passed a relative `Path(".millhouse")` to the loader; the new form spells out the hub-relative mill_dir.
    2. Step 4.5 (lines 38-47): replace the `worktree_root = _paths.resolve_git_root()` derivation with the three-line block:
       ```python
       git_root      = _paths.resolve_git_root()
       container_path = _paths.resolve_container_path(git_root)
       worktree_root  = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)
       ```
       Add a short prose line noting that `slug` is in scope from step 1 and `cfg` from step 3. Keep the rest of the step (`status_path`, `plan_dir`, `overview_path`, `reviews_dir`, `task_dir`) unchanged.
  - `mill-finalize/SKILL.md:15-16` — change `cfg = _config.load_config(repo_root, git_root)` to `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)` (the undefined `repo_root` local is replaced by the canonical helper call). The signature annotation immediately below it (line 16) becomes `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict -- deep-merges <hub_root>/mill-config.yaml with <worktree_root>/.millhouse/config.local.yaml`.

  After all edits, grep each touched SKILL.md for residual `repo_root`, `wiki_path` (as first arg of `_config.load_config`), or `_review_common.load_config(_paths.resolve_git_root()` patterns; none should remain in the edited sections.
- **Commit:** `docs(skills): align load_config signatures with hub_root; fix mill-go step 4.5 worktree_root`

## Batch Tests

`verify: null` — this batch edits only markdown documentation. There is no runnable surface. Markdown lint is not run by this codebase, so manual visual review during the plan-review and code-review rounds is the verification gate.
