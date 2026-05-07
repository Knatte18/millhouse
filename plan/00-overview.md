# Plan: 24 (A) — mill-misc-fixes

```yaml
task: 24 (A) — mill-misc-fixes
slug: mill-misc-fixes
approved: false
started: 20260507-055541
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: test-fixtures
    file: 01-test-fixtures.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: runtime-and-skills
    file: 02-runtime-and-skills.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: Canonical batch-card field names are `Context:` / `Edits:` / `Creates:` / `Deletes:`

- **Decision:** Every plan-batch fixture, integration sample, and review-template prose mention uses `Context:` / `Edits:` / `Creates:` / `Deletes:`. Legacy names `Reads:` / `Modifies:` are removed wherever they still appear in production-relevant assets. Test names and code comments referencing the legacy names as historical labels (e.g. `test_dirty_reads_nonexistent_path`) are out of scope.
- **Rationale:** The validator regex `(Context|Edits|Creates|Deletes)` (`_review_common.py` line 278; `_plan_validate.py` line 50) is the single source of truth. Drift between the validator and any fixture/template causes silent test failures (bug A's mechanism) or stale reviewer prose.
- **Applies to:** all batches.

### Decision: Error-detail snippets fall back from `stderr` → `stdout`, capped at 500 chars

- **Decision:** Anywhere `_llm_claude.py:_invoke` builds an error message from a non-zero subprocess result, the snippet is `(result.stderr or result.stdout or "")[:500]`. The 500-char cap is preserved unchanged. The fallback applies uniformly to LLMRateLimitError, LLMSessionError, and the generic LLMError raises.
- **Rationale:** The Claude CLI emits rate-limit signals to stdout (stream-json), not stderr, leaving the existing `stderr_snippet` empty. Generalizing the fallback removes a class of empty-message bugs across all three exception paths instead of patching only the rate-limit branch.
- **Applies to:** runtime-and-skills.

### Decision: `mill:cli` SKILL.md is the single owner of shell-tool guidance

- **Decision:** New rules about shell-tool behavior (Bash vs PowerShell vs Monitor; CLAUDE_PLUGIN_ROOT semantics) are added to `plugins/mill/skills/cli/SKILL.md`, not duplicated into per-skill SKILL.md files. Each new rule is a one-line bullet matching the existing PowerShell-section format.
- **Rationale:** `mill:cli` is invoked on startup by `mill:workflow` and is the documented home for shell-tool guidance. Per-skill duplication ages badly: every new skill that uses the Monitor tool would need its own copy of the rule.
- **Applies to:** runtime-and-skills.

### Decision: `${CLAUDE_PLUGIN_ROOT}` brace-form change is restricted to fenced bash code blocks

- **Decision:** The sweep that replaces `${CLAUDE_PLUGIN_ROOT}` with `$CLAUDE_PLUGIN_ROOT` only touches occurrences inside ```bash ... ``` fenced code blocks within SKILL.md files. Plain-prose mentions of `${CLAUDE_PLUGIN_ROOT}` (typical Markdown styling for env vars), HTML-comment mentions, table-cell mentions, and non-bash fenced blocks are left unchanged.
- **Rationale:** The brace form is a Markdown convention for env-var styling in prose. The Windows CC substitution issue is specifically observed when the form lands in a Bash subshell. Narrowing the sweep prevents prose churn while still covering every command the LLM might copy.
- **Applies to:** runtime-and-skills.

## All Files Touched

- `plugins/codeguide/skills/codeguide-generate/SKILL.md`
- `plugins/codeguide/skills/codeguide-maintain/SKILL.md`
- `plugins/codeguide/skills/codeguide-setup/SKILL.md`
- `plugins/codeguide/skills/codeguide-update/SKILL.md`
- `plugins/mill/integration_tests/fixtures/sample-plan/01-core.md`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/skills/cli/SKILL.md`
- `plugins/mill/skills/mill-abandon/SKILL.md`
- `plugins/mill/skills/mill-add/SKILL.md`
- `plugins/mill/skills/mill-claim/SKILL.md`
- `plugins/mill/skills/mill-cleanup/SKILL.md`
- `plugins/mill/skills/mill-color/SKILL.md`
- `plugins/mill/skills/mill-fetch-issues/SKILL.md`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-groom/SKILL.md`
- `plugins/mill/skills/mill-inspect/SKILL.md`
- `plugins/mill/skills/mill-list/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-resume/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-skills-from-scripts/SKILL.md`
- `plugins/mill/skills/mill-skills-index/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/mill-status/SKILL.md`
- `plugins/mill/skills/mill-terminal/SKILL.md`
- `plugins/mill/skills/mill-vscode/SKILL.md`
- `plugins/mill/skills/mill-worktree/SKILL.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
