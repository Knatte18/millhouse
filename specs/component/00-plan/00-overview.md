# Plan: codeguide sibling-mode + unified sibling-path convention

```yaml
task: codeguide sibling-mode + unified sibling-path convention
slug: 00-codeguide-sibling-mode
approved: false
started: 20260423-085500
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py && python plugins/mill/integration_tests/test-spawn.py && python plugins/mill/integration_tests/test-merge.py && python plugins/mill/integration_tests/test-plan-assets.py && python plugins/mill/integration_tests/test-go-assets.py
```

## Batch Index

```yaml
batches:
  - name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-sibling.py
  - name: codeguide-plugin
    file: 02-codeguide-plugin.md
    depends-on: [foundation]
    verify: null
  - name: mill-integration
    file: 03-mill-integration.md
    depends-on: [foundation]
    verify: python plugins/mill/integration_tests/test-spawn.py && python plugins/mill/integration_tests/test-merge.py
  - name: docs
    file: 04-docs.md
    depends-on: [mill-integration, codeguide-plugin]
    verify: null
```

## Shared Decisions

### Decision: Hub-form detection is a single string check

- **Decision:** `repo_root.name == "hub"` — the repo directory's name is the entire signal.
- **Rationale:** Deterministic, zero-config, zero-heuristic. Existing Millhouse layout triggers it automatically; every other repo gets prefix-form naming.
- **Applies to:** `_sibling.resolve_path`, and every consumer (mill-spawn, mill-setup, codeguide resolve.py).

### Decision: One `_sibling.py` helper governs wiki, worktrees, and codeguide

- **Decision:** `plugins/mill/scripts/_sibling.py` exposes `resolve_path(role, repo_root) -> Path`. Roles = `{"wiki", "codeguide", "worktrees"}` initially; extensible by string.
- **Rationale:** Single source of truth. Future additions (e.g. `logs/`) land without re-deriving the hub-form rule.
- **Applies to:** every batch touching sibling paths.

### Decision: Resolve chain for codeguide ends with "run /codeguide-setup first"

- **Decision:** Inline (walked up from cwd to git-toplevel) → `.codeguide-root` override at git-toplevel → sibling via `_sibling.resolve_path("codeguide", git_toplevel)` walked through the same path levels → bail with a friendly message.
- **Rationale:** Predictable. Inline wins when the user set it up inline; sibling only activates when it exists.
- **Applies to:** codeguide-plugin batch.

### Decision: Plugin scripts always reference `${CLAUDE_PLUGIN_ROOT}`

- **Decision:** Never assume the millhouse source is cloned on the user's machine. Rule already in `CLAUDE.md` as of this spec's first commit.
- **Rationale:** Codeguide + mill plugins install on foreign repos; those repos cannot be expected to carry the source tree.
- **Applies to:** codeguide-plugin + mill-integration batches, and any future sibling-touching work.

### Decision: Sibling repo is always its own git repo

- **Decision:** `codeguide-setup --sibling` runs `git init` (or `git clone --from-url`) on first use; later invocations from subfolders just `mkdir` + commit inside it.
- **Rationale:** Versioned docs without polluting the target repo. Matches how mill-setup handles the wiki.
- **Applies to:** codeguide-plugin batch.

### Decision: Commit discipline diverges between inline and sibling

- **Decision:** Inline → `@git-commit` stages cg files in the same commit. Sibling → `codeguide_commit.py` helper commits into the sibling repo independently; `@git-commit` does not try to stage its output.
- **Rationale:** Cross-repo commits don't exist; sibling-repo gets its own history.
- **Applies to:** codeguide-plugin batch.

## All Files Touched

New files:
- `plugins/mill/scripts/_sibling.py`
- `plugins/mill/unit_tests/test-sibling.py`
- `plugins/codeguide/scripts/millpy/codeguide/codeguide_commit.py`

Modified files:
- `plugins/codeguide/scripts/millpy/codeguide/resolve.py`
- `plugins/codeguide/skills/codeguide-setup/SKILL.md`
- `plugins/codeguide/skills/codeguide-update/SKILL.md`
- `plugins/mill/skills/git-commit/SKILL.md`
- `plugins/mill/scripts/mill-spawn.py`
- `plugins/mill/scripts/mill-setup.py` (if it reads wiki_path default today)
- `plugins/mill/integration_tests/test-spawn.py`
- `plugins/mill/integration_tests/test-merge.py`
- `wiki/config.yaml` (drops `spawn.worktrees_dir` default; updates `<WIKI_PATH>` header-comment)
- `specs/component/13-mill-codeguide.md` (one-line edit: "inline or sibling")
