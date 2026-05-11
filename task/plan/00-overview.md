# Plan: 44 (A) — Bug-fix batch 4

```yaml
task: 44 (A) — Bug-fix batch 4
slug: mill-misc-fixes-4
approved: false
started: 20260511-104259
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: gitignore-and-claudemd
    file: 01-gitignore-and-claudemd.md
    depends-on: []
    verify: null
  - number: 2
    name: llm-claude-fast-fail-retry
    file: 02-llm-claude-fast-fail-retry.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py
  - number: 3
    name: review-common-divergence-warning
    file: 03-review-common-divergence-warning.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
  - number: 4
    name: review-fixture-seeding
    file: 04-review-fixture-seeding.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-discussion-flow.py
  - number: 5
    name: review-code-error-aggregation
    file: 05-review-code-error-aggregation.md
    depends-on: [4]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py
  - number: 6
    name: merge-in-briefs-protocol-violation
    file: 06-merge-in-briefs-protocol-violation.md
    depends-on: []
    verify: null
  - number: 7
    name: wiki-config-template-sync
    file: 07-wiki-config-template-sync.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-setup-hub-links.py
  - number: 8
    name: skill-md-edits
    file: 08-skill-md-edits.md
    depends-on: [5]
    verify: null
```

## Shared Decisions

### Decision: Verify-command pattern uses `uv run`

- **Decision:** Every batch's `verify:` command begins with `uv run --project plugins/mill python plugins/mill/unit_tests/<test>.py`. Doc-only batches use `verify: null`.
- **Rationale:** Matches the established pattern (see commit 82dae6d8 task 34). `uv run` resolves the right interpreter via the `plugins/mill/pyproject.toml`; explicit per-test invocation is faster than `run-all.py` for narrow batches.
- **Applies to:** all batches with `verify:` non-null.

### Decision: `_yaml_writer.quote_scalar` not used for status-timeline values

- **Decision:** Timeline rows in `task/status.md` are written by `_status.append_phase`; the helper handles its own quoting. Plan-level token substitution (Batch Index, frontmatter) uses `quote_scalar` per mill-plan SKILL.md.
- **Rationale:** Layered responsibility — `_status` owns status.md formatting; the plan template owns frontmatter formatting.
- **Applies to:** all batches.

### Decision: SKILL.md text references `${CLAUDE_PLUGIN_ROOT}`

- **Decision:** Every new bash example added to a `plugins/mill/skills/**/SKILL.md` file in this batch uses `${CLAUDE_PLUGIN_ROOT}` (or `$CLAUDE_PLUGIN_ROOT`) for the plugin directory, never `plugins/mill/...`. Existing surrounding text style (single vs braced) is matched.
- **Rationale:** CLAUDE.md project rule — external repos using mill as a plugin have no millhouse source checkout.
- **Applies to:** batch 8.

### Decision: Implementer commits go through `@git-commit`

- **Decision:** Every card's `Commit:` value is a one-line conventional-commit message. The implementer invokes the `@git-commit` skill once per card (per `implementer-brief.md`).
- **Rationale:** Existing mill-go convention. Per-card commits trigger lint + codeguide-update; squashing into batch-level commits would lose that signal.
- **Applies to:** all batches.

### Decision: No SKILL.md text describes behavior shipped in a later batch

- **Decision:** Batch 8 (SKILL.md edits) depends-on Batch 5 (ERROR aggregation in `_review_code.py`). The new mill-go SKILL.md step 4.5 must NOT be added until the code returning top-level `verdict: "ERROR"` is in place.
- **Rationale:** A SKILL.md describing nonexistent code creates a window where the documented behavior is unreachable; a future engineer reading the SKILL would be misled.
- **Applies to:** batches 5 → 8 ordering.

## All Files Touched

- `.gitignore`
- `CLAUDE.md`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_setup.py`
- `plugins/mill/scripts/_wiki.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/merge-in-conflict-brief.md`
- `plugins/mill/templates/merge-in-verify-brief.md`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/_test_helpers.py`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-setup-hub-links.py`
