# Plan: Migrate mill's generic skills to the shared scribe plugin

```yaml
task: Migrate mill's generic skills to the shared scribe plugin
slug: scribe-migration
approved: false
skip_checks: ["out-of-worktree-target"]
discussion_sha: 066a35ba8f1dd278288c82f79a2cd684f6d51de0
started: 20260929-131009
parent_branch: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: scribe-release
    file: 01-scribe-release.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-agents-defs.py
  - number: 2
    name: mill-skill-references
    file: 02-mill-skill-references.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-load-directive-convention.py test-language-skills-directive.py test-agents-defs.py test-mill-go-variants.py test-skills-index.py test-inplace.py
  - number: 3
    name: update-plugins
    file: 03-update-plugins.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-load-directive-convention.py && bash -n update-plugins.sh
```

## Shared Decisions

### Decision: scribe-publishes-before-millhouse-deletes

- **Decision:** Batch 1 card 1 commits, tags and pushes scribe `1.1.0` (with the Python and C# skills) before card 2 deletes `plugins/{golang,csharp,python}` from millhouse.
  The batches form a linear chain 1 -> 2 -> 3.
- **Rationale:** there is never a published state where the Python/C# skills exist nowhere.
  Batch 2 regenerates `SKILLS.md` and runs the forbidden-name guard, which only passes once the language plugins are gone.
- **Applies to:** all batches

### Decision: dependency-form-confirmed-from-docs

- **Decision:** mill's `plugin.json` declares `"dependencies": [{"name": "scribe", "marketplace": "scribe", "version": "^1.1.0"}]`;
  millhouse's `marketplace.json` gets top-level `"allowCrossMarketplaceDependenciesOn": ["scribe"]`.
  The scribe release tag is `scribe--v1.1.0`, not `v1.1.0`.
- **Rationale:** confirmed from https://code.claude.com/docs/en/plugins/dependencies.md during planning.
  The object form takes `name`, `version` (a node-semver range) and `marketplace`.
  A constraint resolves against git tags named `<plugin-name>--v<version>` on the repo hosting the plugin;
  scribe's marketplace entry uses a relative `./plugins/scribe` source, so the scribe marketplace repo carries the tag.
  When no tag satisfies the range, a relative-path plugin installs the marketplace's current copy and the constraint is checked at load; an out-of-range copy keeps the dependent plugin (mill) disabled.
- **Applies to:** scribe-release, update-plugins

### Decision: missing-dependency-is-a-hard-load-failure

- **Decision:** the `mill-setup` Preconditions bullet and the `update-plugins` not-installed message use the hard-failure wording: add the scribe marketplace and install scribe before installing mill.
- **Rationale:** the docs state that a cross-marketplace dependency declared in `plugin.json` that cannot be installed leaves the install complete without it, "and your plugin then fails to load";
  an installed scribe below `^1.1.0` likewise keeps mill disabled.
  The discussion's scribe-dependency decision says to use the hard-failure wording in that case.
- **Applies to:** mill-skill-references, update-plugins

### Decision: canonical-load-phrases

- **Decision:** the orchestrator Step-0 load directive is exactly "Load `scribe:prose`, then `scribe:conversation`, then `mill:conventions`." (the leading "L" may be lower-case mid-sentence).
  A two-skill directive is exactly "load `scribe:prose`, then `scribe:conversation`".
  `test-load-directive-convention.py` anchors on these phrases.
- **Rationale:** the discussion's load-order and load-directive-test decisions; the test enforces the wording mechanically.
- **Applies to:** mill-skill-references, update-plugins

### Decision: qualified-skill-names

- **Decision:** every mill-owned reference to a generic or language skill uses the plugin-qualified name: `scribe:prose`, `scribe:conversation`, `scribe:code-quality`, `scribe:testing`, `scribe:handoff`, `scribe:{python,csharp,golang}-{build,comments,testing}`, and `mill:conventions` for the mill layer.
  `scribe:code-quality`'s Comments section replaces every former `code-comments` pointer.
- **Rationale:** unqualified names are ambiguous while stale caches still carry `mill:prose` and `python@millhouse`.
- **Applies to:** all batches

### Decision: mill-version-stays-2-0-0

- **Decision:** mill's version stays `2.0.0` in both `plugins/mill/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
- **Rationale:** `update-plugins.{sh,ps1}` sync into `~/.claude/plugins/cache/millhouse/<name>/<version>` and skip a missing directory; `MILL_PYTHON` points into the `2.0.0` cache venv.
- **Applies to:** scribe-release

### Decision: no-lint-in-done-gate

- **Decision:** recommend no lint command for `pipeline.done_gate`.
- **Rationale:** `uvx ruff check .` from `git_root` at the current worktree tip exits 1 (pre-existing repo-wide lint debt unrelated to this task).
- **Applies to:** all batches

### Decision: done-gate-recommendation

- **Decision:** recommendation for the operator: set `pipeline.done_gate` to `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`.
  The currently effective value is `null`.
  Not applied: mill-go gates on the effective config value, not this Decision.
- **Rationale:** batch verifies are scoped to the tests the batches touch;
  the discussion's Testing section asks for the full unit suite once the migration lands, which also catches any test that read a deleted skill file.
- **Applies to:** all batches

## All Files Touched

- `.claude-plugin/marketplace.json`
- `.claude/skills/mill-pool/SKILL.md`
- `/home/knatte/Code/scribe/.claude-plugin/marketplace.json`
- `/home/knatte/Code/scribe/README.md`
- `/home/knatte/Code/scribe/plugins/scribe/.claude-plugin/plugin.json`
- `/home/knatte/Code/scribe/plugins/scribe/skills/INDEX.md`
- `/home/knatte/Code/scribe/plugins/scribe/skills/csharp-build/SKILL.md`
- `/home/knatte/Code/scribe/plugins/scribe/skills/csharp-comments/SKILL.md`
- `/home/knatte/Code/scribe/plugins/scribe/skills/csharp-testing/SKILL.md`
- `/home/knatte/Code/scribe/plugins/scribe/skills/python-build/SKILL.md`
- `/home/knatte/Code/scribe/plugins/scribe/skills/python-comments/SKILL.md`
- `/home/knatte/Code/scribe/plugins/scribe/skills/python-testing/SKILL.md`
- `CLAUDE.md`
- `SKILLS.md`
- `doc/turn-reduction-audit.md`
- `plugins/mill/.claude-plugin/plugin.json`
- `plugins/mill/agents/mill-implementer-high.md`
- `plugins/mill/agents/mill-implementer-low.md`
- `plugins/mill/agents/mill-implementer-max.md`
- `plugins/mill/agents/mill-implementer-medium.md`
- `plugins/mill/agents/mill-implementer-xhigh.md`
- `plugins/mill/agents/mill-implementer.md`
- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_inplace.py`
- `plugins/mill/scripts/millpy-skills-index.py`
- `plugins/mill/scripts/tools/mdreflow/mdreflow.py`
- `plugins/mill/scripts/tools/pydocreflow/pydocreflow.py`
- `plugins/mill/skills/ask-thread/SKILL.md`
- `plugins/mill/skills/conventions/SKILL.md`
- `plugins/mill/skills/git-commit/SKILL.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go2/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-self-report/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/workflow/SKILL.md`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/unit_tests/test-language-skills-directive.py`
- `plugins/mill/unit_tests/test-load-directive-convention.py`
- `update-plugins.ps1`
- `update-plugins.sh`
