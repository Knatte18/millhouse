# Plan: 37 (A) — Codeguide bug-fix batch 1

```yaml
task: 37 (A) — Codeguide bug-fix batch 1
slug: codeguide-fixes-1
approved: false
started: 20260509-103409
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: scope-helper
    file: 01-scope-helper.md
    depends-on: []
    verify: python plugins/codeguide/unit_tests/run-all.py
  - number: 2
    name: skill-edits
    file: 02-skill-edits.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

### Decision: codeguide-plugin-independent-of-mill

- **Decision:** No new code under `plugins/codeguide/` may import from `plugins/mill/` or read mill-owned files (`task/status.md`, `.millhouse/config.yaml`). Parent-branch detection in `resolve_scope.py` is git-native (`git symbolic-ref refs/remotes/origin/HEAD`, fallback `origin/main`, fallback `origin/master`).
- **Rationale:** Codeguide is shipped to repos that may have no mill clone. Coupling to mill would break codeguide-only deployments. Discussed in `task/discussion.md` under decision `git-native-parent-detection`.
- **Applies to:** all batches.

### Decision: stdlib-only-for-new-python

- **Decision:** `resolve_scope.py` and the new unit tests use only Python stdlib (`subprocess`, `pathlib`, `argparse`, `sys`, `json`, `re`, `tempfile`, `os`). No third-party imports, no `pyyaml`, no `gitpython`.
- **Rationale:** Mirrors the existing `plugins/codeguide/scripts/resolve.py` and the mill-side helpers under `plugins/mill/scripts/`. Plugins ship without bundled venvs on user machines beyond what `pyproject.toml` declares.
- **Applies to:** scope-helper.

### Decision: claude-plugin-root-only-in-skill-prose

- **Decision:** All shell-command examples added or modified in SKILL.md files use `${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py`. Hardcoded `plugins/codeguide/...` and `plugins/mill/...` are banned in SKILL.md prose (per CLAUDE.md `## Conventions worth carrying`).
- **Rationale:** SKILL.md instructions execute on user machines that have no millhouse source checkout; only the cache resolves correctly via `${CLAUDE_PLUGIN_ROOT}`.
- **Applies to:** skill-edits.

### Decision: skill-frontmatter-untouched

- **Decision:** Skill edits change only body content. The YAML frontmatter (`name:`, `description:`, `argument-hint:`) of every SKILL.md is preserved byte-for-byte. The Resolution callout sits between the frontmatter's closing `---` (plus the one-paragraph description that follows it) and the first existing `##` heading.
- **Rationale:** `description:` is indexed by Claude Code's skill loader; changes there have side effects beyond this task. Discussion's `Out` list excludes those.
- **Applies to:** skill-edits.

### Decision: no-backwards-compat-shims

- **Decision:** When the new `## Resolution` callout makes an existing buried Step 1 (or Step 3 in `codeguide-setup`) redundant, the buried step collapses to a one-line back-reference (`See ## Resolution above.`) — never a "kept for compat" note. Renumbering of subsequent steps follows the back-reference's slot.
- **Rationale:** CLAUDE.md `# Doing tasks` section: "Don't add error handling, fallbacks, or validation for scenarios that can't happen" / "Don't use feature flags or backwards-compatibility shims when you can just change the code".
- **Applies to:** skill-edits.

## All Files Touched

- `plugins/codeguide/scripts/resolve_scope.py`
- `plugins/codeguide/skills/codeguide-generate/SKILL.md`
- `plugins/codeguide/skills/codeguide-maintain/SKILL.md`
- `plugins/codeguide/skills/codeguide-setup/SKILL.md`
- `plugins/codeguide/skills/codeguide-update/SKILL.md`
- `plugins/codeguide/unit_tests/run-all.py`
- `plugins/codeguide/unit_tests/test-resolve-scope.py`
- `plugins/mill/skills/git-commit/SKILL.md`
