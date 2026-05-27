# Plan: mill-merge / fixer teardown recovery

```yaml
task: "mill-merge / fixer teardown recovery"
slug: mill-merge-teardown-recovery
approved: true
started: "20260527-085451"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: archive-tag
    file: 01-archive-tag.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: merge-continue
    file: 02-merge-continue.md
    depends-on: []
    verify: null
  - number: 3
    name: status-gate
    file: 03-status-gate.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 4
    name: fixer-isolation
    file: 04-fixer-isolation.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: helper-extraction-for-test-surface

- **Decision:** Extract a Python helper module from a SKILL.md edit ONLY when that edit requires a unit-test surface. The archive-tag conflict resolution (batch 1) and the mill-go absent-status fallback (batch 3) both extract helpers (`_archive_tag.py`, `_phase_gate.py`) because their decision tables warrant tests. The `git merge --continue` edit (batch 2) is a pure one-line SKILL.md change with no decision logic — no helper, no test.
- **Rationale:** Helpers exist to expose decision logic to unit tests. SKILL.md prose has no other test surface. Don't extract for the sake of extraction.
- **Applies to:** all batches.

### Decision: tdd-test-first-for-new-helpers

- **Decision:** Each new helper card pair writes the failing unit test card first, then the implementation card that makes it pass. Implementer runs the test before implementation to confirm it fails, then implements to green. Card order is `test → impl` in every batch that adds a helper.
- **Rationale:** TDD with a real failing test is the test-quality forcing function. Writing the helper first risks producing a test that passes accidentally.
- **Applies to:** batches 1, 3, 4.

### Decision: skill-md-invokes-helpers-via-inline-python

- **Decision:** When a SKILL.md step calls a new Python helper, it does so via inline `$MILL_PYTHON -c "..."` matching the existing idiom at `mill-merge/SKILL.md` Step 7 (which already uses this pattern for `_client.set_phase`). No new CLI scripts; no shell-script wrappers.
- **Rationale:** Existing convention; one less surface to maintain; readable in the SKILL doc.
- **Applies to:** batches 1, 3.

### Decision: env-strip-named-blocklist

- **Decision:** The env-strip in `_llm_claude._invoke` is a named blocklist of exactly seven environment variables: `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`. Defined as a module-level constant `STRIP_VARS`. The implementation is `env = {k: v for k, v in os.environ.items() if k not in STRIP_VARS}`. NOT a `GIT_*` prefix strip — `GIT_PAGER`, `GIT_TERMINAL_PROMPT`, `GIT_CONFIG_GLOBAL`, `GIT_PYTHON_REFRESH` and other benign vars must survive.
- **Rationale:** Per discussion `### fixer-implementer-git-env-isolation`; prefix-strip would break benign git env vars. Allowlist would break if Claude CLI later needs a new benign `GIT_*` var.
- **Applies to:** batch 4.

### Decision: cli-state-commit-author-pinning

- **Decision:** Every CLI state commit in `millpy-fix.py` and `millpy-implement.py` is issued via `_subprocess_util.git_commit(cwd, message, *, name, email)`, which wraps `git -c user.name="$NAME" -c user.email="$EMAIL" commit -m "$MESSAGE"`. `name` and `email` are resolved once at the top of each CLI's `main()` from `git config --global --get user.name` / `--get user.email`. If either is unset (empty stdout after strip), the CLI exits 1 with a clear stderr message before doing any work.
- **Rationale:** Per discussion `### cli-commit-author-pinning`; immune to worktree-local config drift; fail-fast on misconfigured global identity.
- **Applies to:** batch 4.

### Decision: ascii-stdout-stderr-only

- **Decision:** All new `print` calls in `_archive_tag.py`, `_phase_gate.py`, `_subprocess_util.git_commit`, modified `_llm_claude._invoke`, `millpy-fix.py`, `millpy-implement.py` must be ASCII only. Use `--` not `—`, `->` not `→`, `'` not `'`.
- **Rationale:** Per CLAUDE.md `## Conventions`; Windows cp1252 crashes on non-ASCII stdout.
- **Applies to:** all batches.

### Decision: brief-edits-extend-existing-section

- **Decision:** The fixer/implementer brief edits in batch 4 extend the existing `## Cross-worktree isolation` section in each brief template — they do NOT add a new section. The existing prose about parent-worktree cd-banning is preserved; a new paragraph is appended generalising the prohibition to any cd outside the task worktree (including test fixtures under `.scratch/` or `unit_tests/fixtures/`).
- **Rationale:** One section keeps the cd-discipline rules co-located. Parallel sections risk contradicting each other as either evolves.
- **Applies to:** batch 4.

## All Files Touched

- `plugins/mill/scripts/_archive_tag.py`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_phase_gate.py`
- `plugins/mill/scripts/_subprocess_util.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/templates/fixer-batch-brief.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-archive-tag-conflict.py`
- `plugins/mill/unit_tests/test-cli-commit-author.py`
- `plugins/mill/unit_tests/test-fixer-env-isolation.py`
- `plugins/mill/unit_tests/test-mill-go-status-absent.py`
