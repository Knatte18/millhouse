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
- **Applies to:** every implementation of the sibling-path rule (both plugin-local copies).

### Decision: Each plugin ships its own `_sibling.py` — no cross-plugin import

- **Decision:** `plugins/mill/scripts/_sibling.py` and `plugins/codeguide/scripts/_sibling.py` are separate files with identical 3-line logic. Neither plugin imports from the other's `scripts/` directory.
- **Rationale:** Plugin install paths are not guaranteed to be relative siblings of each other. Cross-plugin `${CLAUDE_PLUGIN_ROOT}/../mill/scripts/...` is fragile. Three lines of pure arithmetic is cheaper to duplicate than to share. Divergence risk is low; a pre-merge grep catches it if it ever happens.
- **Applies to:** foundation batch (mill copy), codeguide-plugin batch (codeguide copy).

### Decision: `_sibling.py` exposes a CLI entry point in addition to `resolve_path`

- **Decision:** Both copies support `python _sibling.py <role> <repo_root>` → print resolved path on stdout, exit 0. Plus the Python import surface `from _sibling import resolve_path`.
- **Rationale:** SKILL.md prose (mill-setup, codeguide-setup) invokes Python via subprocess — it needs a stable CLI. Python callers (mill-spawn) import directly.
- **Applies to:** foundation batch; and a mirrored CLI in the codeguide copy for symmetry.

### Decision: Resolve chain for codeguide ends with "run /codeguide-setup first"

- **Decision:** Inline (walked up from cwd to git-toplevel) → `.codeguide-root` override at git-toplevel → sibling via `_sibling.resolve_path("codeguide", git_toplevel)` walked through the same path levels → bail with a friendly message.
- **Rationale:** Predictable. Inline wins when the user set it up inline; sibling only activates when it exists.
- **Applies to:** codeguide-plugin batch.

### Decision: Plugin scripts always reference `${CLAUDE_PLUGIN_ROOT}`

- **Decision:** Never assume the millhouse source is cloned on the user's machine. Rule already in `CLAUDE.md` as of this spec's first commit.
- **Rationale:** Codeguide + mill plugins install on foreign repos; those repos cannot be expected to carry the source tree.
- **Applies to:** codeguide-plugin + mill-integration batches, and any future sibling-touching work.

### Decision: Fix stale `millpy/codeguide/` paths before anything else in the codeguide-plugin batch

- **Decision:** The four existing codeguide skills (`codeguide-setup`, `codeguide-update`, `codeguide-generate`, `codeguide-maintain`) reference `${CLAUDE_PLUGIN_ROOT}/scripts/millpy/codeguide/resolve.py`. That path does not exist — the file is at `${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py`. The first card of the codeguide-plugin batch corrects all four files.
- **Rationale:** The scoped-out bug blocks the sibling work: we cannot extend `resolve.py` if callers can't locate it in the first place. Fixing it is a precondition.
- **Applies to:** codeguide-plugin batch (Card 3).

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
- `plugins/codeguide/scripts/_sibling.py`
- `plugins/codeguide/scripts/codeguide_commit.py`

Modified files:
- `plugins/codeguide/scripts/resolve.py`
- `plugins/codeguide/skills/codeguide-setup/SKILL.md`
- `plugins/codeguide/skills/codeguide-update/SKILL.md`
- `plugins/codeguide/skills/codeguide-generate/SKILL.md` (stale-path fix only)
- `plugins/codeguide/skills/codeguide-maintain/SKILL.md` (stale-path fix only)
- `plugins/mill/skills/git-commit/SKILL.md`
- `plugins/mill/scripts/mill-spawn.py`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/integration_tests/test-spawn.py`
- `plugins/mill/integration_tests/test-merge.py`
- `wiki/config.yaml` (drops `spawn.worktrees_dir` default; updates `<WIKI_PATH>` header-comment)
- `specs/component/13-mill-codeguide.md` (one-line edit: "inline or sibling")
