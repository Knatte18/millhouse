# Plan: Deactivate codeguide integration in millhouse

```yaml
task: "Deactivate codeguide integration in millhouse"
slug: deactivate-codeguide
approved: true
started: "20260923-102903"
parent: main
root: ""
verify: null
discussion_sha: "6cac2cec1ab187f92c6a57916504a9338795e9f8"
```

## Batch Index

```yaml
batches:
  - number: 1
    name: deactivate-call-sites
    file: 01-deactivate-call-sites.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
  - number: 2
    name: prose-cleanup
    file: 02-prose-cleanup.md
    depends-on: []
    verify: null
  - number: 3
    name: close-issue
    file: 03-close-issue.md
    depends-on: [1, 2]
    verify: PYTHONPATH= sh -c "! grep -q CODEGUIDE_PLUGIN_ROOT plugins/mill/skills/git-commit/SKILL.md && ! grep -q codeguide-update plugins/mill/skills/mill-merge-in/SKILL.md && uv run --project plugins/mill python plugins/mill/unit_tests/test-sibling.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py"
```

## Shared Decisions

### Decision: deletion, not a feature flag

- **Decision:** Every codeguide call site is deleted outright. No `mill-config.yaml` toggle is added anywhere in this plan.
- **Rationale:** No such toggle exists today. A flag checked before or after codeguide's own `resolve.py` would still pay some or all of the resolve-and-check cost the user wants removed; deleting the calling code removes it entirely with nothing left to maintain.
- **Applies to:** all batches.

### Decision: `plugins/codeguide/` plugin and general-purpose plumbing are out of scope

- **Decision:** The `plugins/codeguide/` plugin itself (its skills, scripts, templates) is never edited. `_sibling.py` (`resolve_path` and its `"codeguide"` role branch) and `_parent_branch.py`'s `resolve`/`check_liveness`/`resolve_dead_parent`/`ParentBranchError` are never edited — only `_parent_branch.resolve_for_codeguide` (batch 1, card 3) is in scope, since it is the one function with exactly one caller, that caller being deleted in this same plan.
- **Rationale:** `_sibling.py`'s `resolve_path` is called from ~30 files via `_paths.resolve_wiki_path` for wiki-path resolution, unrelated to codeguide; its `"codeguide"` role branch exists only to keep it byte-identical to `plugins/codeguide/scripts/_sibling.py` (asserted by `test-sibling.py`). `_parent_branch.py`'s other functions are load-bearing across the merge/finalize/plan/implement/go pipeline, independent of codeguide.
- **Applies to:** all batches.

### Decision: purely-conditional `_codeguide/` prose mentions are left unedited

- **Decision:** `mill-start/SKILL.md`'s Explore-phase navigation guidance, `workflow/SKILL.md`'s and `code-comments/SKILL.md`'s mentions of `_codeguide/` as a place durable notes/module docs can live, and `millhouse-issue/SKILL.md`'s example usage string are not touched by this plan.
- **Rationale:** none of these invoke codeguide — they degrade gracefully if `_codeguide/` never exists and stay correct if a repo still has pre-existing codeguide docs on disk. Editing them would be scope creep beyond "stop calling into codeguide."
- **Applies to:** batch 2 (prose-cleanup), by omission.

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/_parent_branch.py`
- `plugins/mill/skills/git-clone/SKILL.md`
- `plugins/mill/skills/git-commit/SKILL.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-quick/SKILL.md`
- `plugins/mill/templates/fixer-batch-brief.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-parent-branch.py`
