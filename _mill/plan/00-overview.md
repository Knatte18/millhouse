# Plan: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps

```yaml
task: "Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps"
slug: "mill-cross-machine-resume-and-config-gaps"
approved: false
started: "2026-07-29T14:10:00Z"
parent: "main"
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: wiki-health-check-and-messaging
    file: 01-wiki-health-check-and-messaging.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-health-check.py test-wiki-daemon.py test-wiki-client-retry.py"
  - number: 2
    name: mill-resume-repair
    file: 02-mill-resume-repair.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-worktree.py test-paths.py test-resume-repair.py"
  - number: 3
    name: config-resolution-fixes-implement-and-small
    file: 03-config-resolution-fixes-implement-and-small.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-abandon.py test-millpy-validate-plan.py"
  - number: 4
    name: config-resolution-fixes-fix-and-merge
    file: 04-config-resolution-fixes-fix-and-merge.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py test-merge-in-subagent.py"
```

All four batches are independent (no shared edit targets, no data/control dependency between them) and can run in any order or in parallel. Batches 3 and 4 were split from a single "config-resolution-fixes" batch during Step 1.5's validator gate (`batch-oversized`: the original batch's `millpy-implement.py`/`millpy-fix.py` unit test files alone are ~1900/~1990 lines each, pushing the combined context estimate to ~139603 tokens against the 120000 cap) -- see each file's Batch Scope for the split rationale.

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: ASCII-only stdout/stderr in mill scripts

- **Decision:** Every new `print(...)`/log statement added to `plugins/mill/scripts/**` (including `wiki/`) uses ASCII only — no em/en dashes, no Unicode arrows. Use `--` for em-dash and `->`/`vs.` for arrows, per `CLAUDE.md`'s `print()` / `_log()` convention.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII output; this has bitten the codebase before (see `CLAUDE.md`).
- **Applies to:** wiki-health-check-and-messaging, mill-resume-repair.

### Decision: verify: command isolation

- **Decision:** Every non-null `verify:` in this plan (overview and per-batch) is a scoped `run-all.py --only <files>` invocation prefixed with the literal `PYTHONPATH= ` token, never an unscoped `run-all.py` run.
- **Rationale:** matches `plugins/mill/skills/mill-plan/SKILL.md`'s verify-command-shape and verify-command-scope rules; this is a Python project (`pyproject.toml` present), so the `PYTHONPATH=` prefix is mandatory to avoid loading stale cache modules.
- **Applies to:** all batches.

### Decision: no new abstractions beyond what each fix needs

- **Decision:** Every fix in this plan reuses an existing helper (`_pygit2_util.status_porcelain`, `_worktree.copy_millhouse`, `_junction.create`, `wiki/_sync.py`'s `pull()`) instead of re-implementing equivalent logic. New modules (`_resume_repair.py`) and functions (`_worktree.move`, `_paths.resolve_canonical_worktree_path`, `wiki/_sync.py`'s extracted `verify_git_repo`) are added only where no existing primitive covers the need, and are kept to the minimal surface the discussion's Decisions require.
- **Rationale:** YAGNI; matches `discussion.md`'s explicit "Out of scope: centralizing/refactoring load_config call-site convention repo-wide" and "no structural refactor" framing.
- **Applies to:** all batches.

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path
across every batch, sorted alphabetically (Move **source** paths are
excluded — they disappear, like `Deletes:` tokens). Cards are the
source of truth; this section is the input `_plan_validate.py`'s
`all-files-touched-mismatch` check cross-references against the derived
union of every card's `Edits:`/`Creates:`/Move-target paths, to catch
drift between the hand/agent-maintained list here and that derived
union._

- `plugins/mill/integration_tests/test-resume-relocate.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_resume_repair.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-abandon.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-validate-plan.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/scripts/wiki/_server.py`
- `plugins/mill/scripts/wiki/_sync.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-resume/SKILL.md`
- `plugins/mill/unit_tests/test-abandon.py`
- `plugins/mill/unit_tests/test-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-resume-repair.py`
- `plugins/mill/unit_tests/test-wiki-health-check.py`
- `plugins/mill/unit_tests/test-wiki-sync.py`
- `plugins/mill/unit_tests/test-worktree.py`
