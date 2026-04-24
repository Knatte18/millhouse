# Batch: scratch-move

```yaml
task: junction-rule enforcement + _paths.py consolidation
batch: scratch-move
cards: 4
verify: python plugins/mill/integration_tests/test-spawn.py && python plugins/mill/integration_tests/test-merge.py
depends-on: []
```

## Batch Scope

Move the scratch directory from `.millhouse/scratch/` to `.scratch/` at cwd-root. Touches:

- `.gitignore` — add `**/.scratch/`.
- `_worktree.py` — drop the `scratch` name from the default-exclude set in `copy_millhouse` (obsolete once scratch is outside `.millhouse/`).
- 8 integration tests + 1 PowerShell bootstrap — each holds a `SCRATCH = HUB / ".millhouse" / "scratch"` constant (or a `$scratch` variable in the PowerShell case).
- 4 SKILL.md files — each references `.millhouse/scratch/` somewhere in prose.
- 1 unit test — `test-worktree.py` asserts the `scratch` exclusion; that assertion becomes meaningless and must be removed or re-purposed.
- `specs/component/README.md` + `specs/component/11-mill-groom-skill.md` — prose references to `.millhouse/scratch/` that describe current convention.

Done-* specs are historical and are NOT touched.

This batch is independent of `foundation` and `callsite-migration` — could run in parallel. Sequenced only because `docs` batch (04) wants both landed so CLAUDE.md's new Path invariants section describes the final state.

## Cards

### Card 6: `.gitignore` + `_worktree.copy_millhouse` cleanup

- **Reads:** `.gitignore`, `plugins/mill/scripts/_worktree.py`, `plugins/mill/unit_tests/test-worktree.py`.
- **Modifies:** `.gitignore`, `plugins/mill/scripts/_worktree.py`, `plugins/mill/unit_tests/test-worktree.py`.
- **Creates:** (none)
- **Requirements:**
  - `.gitignore`: add `**/.scratch/` alongside the existing `**/.millhouse/` entry. Group them together under a comment like `# mill local state` if one exists; otherwise insert right next to `.millhouse/`.
  - `_worktree.py`: inspect `copy_millhouse`'s `exclude` parameter and its default set. Drop the `scratch` entry from any default-set literal. If `exclude` has no default and callers pass the set explicitly, update callers (check `mill-spawn.py`'s invocation `_worktree.copy_millhouse(src=..., dst=..., exclude={"scratch", "wiki", "active"})` — drop `"scratch"` there too).
  - `test-worktree.py`: the current test asserts that a `scratch` directory in `.millhouse/` is excluded from propagation. After the move, `scratch` no longer lives in `.millhouse/` at all, so the test is meaningless. Either (a) delete that branch, keeping the `keep`/`plainfile` branches, OR (b) repurpose it to assert that `wiki` and `active` are still excluded (the two remaining name-exclusions). Prefer (b) — preserves one regression-guard for the exclude parameter's general behaviour.
- **Commit:** `refactor(scratch): move scratch out of .millhouse/ — .gitignore + copy_millhouse + test-worktree`

### Card 7: integration tests swap `.millhouse/scratch` → `.scratch`

- **Reads:** All integration tests under `plugins/mill/integration_tests/`.
- **Modifies:** `plugins/mill/integration_tests/test-spawn.py`, `test-merge.py`, `test-plan-assets.py`, `test-go-assets.py`, `test-review-discussion.py`, `test-review-plan.py`, `test-review-code.py`, `smoke-llm-claude.py`, `test-bootstrap.ps1`.
- **Creates:** (none)
- **Requirements:**
  - Each Python test has a module-level constant. Variable names vary: `test-spawn.py`, `test-merge.py`, `test-plan-assets.py`, `test-go-assets.py`, and `smoke-llm-claude.py` use `SCRATCH`; `test-review-discussion.py`, `test-review-plan.py`, and `test-review-code.py` use `_SCRATCH` (underscore prefix — internal-use marker). Both forms assign `HUB / ".millhouse" / "scratch"` (or the equivalent `HUB / ".millhouse/scratch"`). Replace the path half with `HUB / ".scratch"` in every file regardless of variable name. Keep the path ABSOLUTE — all tests use it as an absolute fixture-root.
  - `test-bootstrap.ps1`: BOTH the prose comment (around line 22, "Per conversation/SKILL.md: never use `$env:TEMP`; use `.millhouse/scratch/` instead.") AND the variable (`$scratch = Join-Path $hubRoot '.millhouse' 'scratch'`) reference the old path. Update BOTH — the comment text to say `.scratch/`, and the variable to `$scratch = Join-Path $hubRoot '.scratch'` (drop the intermediate directory arg). Verify the test still runs in PowerShell 5 (the environment convention from global CLAUDE.md).
  - Do NOT change the per-test subdirectory naming (`spawn-test-<hex>/`, `merge-test-<hex>/` etc.) — only the parent directory.
  - Clean up any stale `.millhouse/scratch/` directory from the hub's workspace via the test-cleanup `finally` blocks is NOT this batch's job — existing cleanup runs against the variable, which now points at `.scratch/`. The old location becomes orphan-but-harmless (gitignored, user may delete at leisure).
  - One card covers all 9 files — the edit is literally find-replace per file; grouping keeps the diff reviewable in one sitting.
- **Commit:** `test(scratch): integration tests use <cwd>/.scratch/ fixture root`

### Card 8: SKILL.md prose updates

- **Reads:** `plugins/mill/skills/conversation/SKILL.md`, `plugins/mill/skills/mill-merge/SKILL.md`, `plugins/mill/skills/mill-self-report/SKILL.md`, `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`.
- **Modifies:** all four SKILL.md files above.
- **Creates:** (none)
- **Requirements:**
  - Replace every mention of `.millhouse/scratch/` (or `.millhouse/scratch`) with `.scratch/` (or `.scratch`).
  - `conversation/SKILL.md` is the canonical scratch-rule source (cited from CLAUDE.md). Its prose must read clean after the edit — re-read the whole paragraph around each match to make sure pronouns / context still work.
  - Preserve `---` YAML frontmatter unchanged.
  - Do NOT touch done-* specs or `done-*.md` historical notes.
- **Commit:** `docs(scratch): SKILL.md files mention <cwd>/.scratch/`

### Card 9: active-spec prose updates

- **Reads:** `specs/component/README.md`, `specs/component/11-mill-groom-skill.md`.
- **Modifies:** `specs/component/README.md`, `specs/component/11-mill-groom-skill.md`.
- **Creates:** (none)
- **Requirements:**
  - `README.md` line 51 references `.millhouse/scratch/` as the fixture location convention — update to `.scratch/`.
  - `11-mill-groom-skill.md` line 30 and line 43 reference `.millhouse/scratch/groom-proposal.md` as the approval-gate artefact. Update both to `.scratch/groom-proposal.md`.
  - Do NOT touch `done-02-*.md`, `done-06-*.md`, or any other frozen historical spec.
  - Do NOT touch `14-junction-rule-wiki-resolve.md` — it deliberately describes the old state as the justification for the move.
- **Commit:** `docs(scratch): active specs mention <cwd>/.scratch/`

## Batch Tests

`test-spawn.py` and `test-merge.py` both create their own isolated fixtures under `SCRATCH`. If the constant moved correctly AND the tests still find their fixtures, the move is functional end-to-end. Both must pass.

If either fails, the most likely cause is a file that holds the literal string `.millhouse/scratch` somewhere NOT listed in "All Files Touched" — the implementer greps for the literal one final time as a self-check before marking the batch done.
