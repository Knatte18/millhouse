# Plan: 4 (A) — mill-setup: --from-url for separate wiki repo

```yaml
task: '4 (A) — mill-setup: --from-url for separate wiki repo'
slug: mill-setup-wiki-url
approved: true
started: 20260506-060141
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches. Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - name: helpers
    file: 01-helpers.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - name: skill-and-template
    file: 02-skill-and-template.md
    depends-on: [helpers]
    verify: null
```

## Shared Decisions

### Decision: helper-module placement

- **Decision:** New helpers live in their topical module: `clone_or_init` in `_wiki.py`; `set_local_wiki_overrides` in `_config.py`. Tests are added to the existing `test-wiki.py` and `test-config.py` (one test file per helper module is the established pattern — `run-all.py` globs `test-*.py` so no registration step is needed).
- **Rationale:** Matches existing convention. Keeps the diff small.
- **Applies to:** all batches

### Decision: subprocess mocking pattern

- **Decision:** Tests mock `_wiki._subprocess_util.run` (or `_config._subprocess_util.run` if needed) via `unittest.mock.patch`, returning stub objects with `.returncode`, `.stdout`, `.stderr`. No real git, no real network. Use `tempfile.TemporaryDirectory()` for filesystem paths.
- **Rationale:** Matches existing `test-wiki.py` style (see `_ok_result` / `_ok_run` helpers in that file).
- **Applies to:** helpers

### Decision: yaml load+dump for config persistence

- **Decision:** `_config.set_local_wiki_overrides` uses `yaml.safe_load` + `yaml.safe_dump(sort_keys=False)`. Comments in `.millhouse/config.local.yaml` are lost on rewrite when this helper fires. The file is gitignored and per-machine, so comment loss is acceptable. `ruamel.yaml` is not added.
- **Rationale:** Matches the design decision recorded in discussion.md ("Comment preservation in config.local.yaml — yaml load + dump"). Keeps dependency surface unchanged.
- **Applies to:** helpers

### Decision: orphan-branch upstream tracking via git config (not git push -u)

- **Decision:** When `clone_or_init` initialises a new orphan branch, it sets `branch.<name>.remote = origin` and `branch.<name>.merge = refs/heads/<name>` via `git config` calls during the init path. The first push by `_wiki.write_commit_push` (Phase 3.1, Phase 6, Phase 6a) then succeeds without modifying the helper.
- **Rationale:** Avoids threading "is this the first push?" logic through `_wiki.write_commit_push`, which is depended on widely. Pre-setting `branch.*.remote`/`merge` is exactly what `git push -u origin <name>` does internally.
- **Applies to:** helpers

### Decision: argument-parsing pattern (codeguide-setup style)

- **Decision:** mill-setup parses `$ARGUMENTS` in skill prose via token-walk. `argument-hint:` lives in YAML frontmatter. Unknown tokens halt with a usage hint. No Python helper for parsing.
- **Rationale:** Two flags don't justify a helper; matches codeguide-setup's existing pattern.
- **Applies to:** skill-and-template

### Decision: precedence on re-run — CLI > config > derived

- **Decision:** Effective `<wiki-url>` is `--from-url` if given, else `wiki.repo_url:` from `.millhouse/config.local.yaml` if present, else derived `<origin>.wiki.git`. Same precedence for `--branch` / `wiki.branch:` / `None` (remote HEAD). When `<wiki-dir>` already exists as a git repo and its actual `origin`/branch differ from the effective values, mill-setup halts (no silent switch).
- **Rationale:** Matches discussion.md decisions. CLI primary keeps first-run UX simple; config persistence makes re-runs work without re-typing flags; halt-on-mismatch matches the existing "never overwrite user data" principle.
- **Applies to:** all batches

### Decision: persistence trigger — only when CLI flag was given

- **Decision:** Phase 3.2 writes the `wiki:` block to `.millhouse/config.local.yaml` only when `--from-url` or `--branch` was supplied on the CLI in this run. When the value is read from config (re-run without flags) or derived (default GitHub-wiki path), Phase 3.2 is a no-op.
- **Rationale:** Avoids polluting the gitignored config with derivable defaults; matches discussion.md Q9=1.
- **Applies to:** skill-and-template

### Decision: Phase 2 reachability message — conditional

- **Decision:** When `<effective-from-url-source>` is `'derived'` (no CLI flag and no config override), Phase 2 keeps the existing GitHub-wiki guidance ("Open `https://github.com/<owner>/<repo>/wiki`, create the Home page"). When the source is `'cli'` or `'config'`, Phase 2 emits a generic "URL `<url>` unreachable" message.
- **Rationale:** GitHub-wiki guidance is misleading when the user is targeting a normal repo. Conditional branching keeps both flows clear.
- **Applies to:** skill-and-template

## All Files Touched

- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_wiki.py`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/templates/config.local.yaml`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-wiki.py`
