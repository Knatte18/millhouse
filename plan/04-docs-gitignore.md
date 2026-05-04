# Batch: Docs and gitignore

```yaml
task: 'script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo'
batch: Docs and gitignore
cards: 3
verify: python plugins/mill/unit_tests/test-gitignore-phase.py
depends-on: []
```

## Batch Scope

This batch ships the (B) half of the task: the source-vs-cache rule that prevents Claude Code from invoking mill scripts as `plugins/mill/scripts/...` from the source tree. Three cards: (1) tighten CLAUDE.md with an explicit ban on source-tree paths in operational Bash plus a wrong/right example; (2) add wrong/right examples to `mill-add` and `mill-setup` SKILL.md and run a verify pass over every operational SKILL.md to fix any stragglers; (3) add `**/plugins/*/uv.lock` to `_gitignore.GLOB_ENTRIES` and to the current `.gitignore` mill-managed block, plus a test assertion. This batch is parallel-safe with all other batches — it touches no Python module that batches 01-03 modify (with the single exception of `_gitignore.py`, which is unique to this batch). The verify pass over SKILL.md is bounded: descriptive prose mentions of `plugins/mill/scripts/...` are left alone; only operational `uv run` / `python ...` invocations that name source-tree paths are corrected.

Batch-local decisions:
- The verify-pass-over-other-SKILL.md scope is limited to mill-owned skills (under `plugins/mill/skills/`). The codeguide plugin is out of scope.
- The CLAUDE.md `## Path invariants` one-line note about `.wiki` is added in Card 13 (with the source-vs-cache rule) so the file changes for batch 04 are concentrated in one card per file.

## Cards

### Card 13: CLAUDE.md tightening

- **Reads:**
  - `CLAUDE.md`
- **Modifies:**
  - `CLAUDE.md`
- **Creates:** none
- **Requirements:** In the `## Conventions worth carrying` section, after the existing first bullet about `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths, add a new bullet: **In operational Bash commands typed at the agent level, never reference `plugins/mill/...` or `plugins/codeguide/...` source-tree paths. Use `${CLAUDE_PLUGIN_ROOT}` (which resolves to the cache). Tests run as `python plugins/mill/unit_tests/...` are the sole exception, and only when explicitly invoked from a test runner.** Pair the bullet with one wrong/right code-fence example showing `uv run --project plugins/mill plugins/mill/scripts/millpy-spawn.py` (WRONG — invokes from source tree) versus `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-spawn.py"` (RIGHT — invokes from cache). The example fence uses ` ```bash`. In the `## Path invariants` section, after the existing bullets, add a one-line bullet: **Future `.wiki` junction (introduced by `rename-hub-junctions`) follows the same `cwd / ".wiki"` convention as `.millhouse/` — scripts must resolve it via `_paths.py`, not treat the junction as a code path.** Do not modify any other section of CLAUDE.md.
- **Commit:** `docs(CLAUDE.md): add source-vs-cache rule with wrong/right example, .wiki invariant note`

### Card 14: SKILL.md wrong/right examples + verify pass

- **Reads:**
  - `plugins/mill/skills/mill-add/SKILL.md`
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
  - `plugins/mill/skills/conversation/SKILL.md`
  - `plugins/mill/skills/code-quality/SKILL.md`
  - `plugins/mill/skills/git-workflow/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-add/SKILL.md`
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
- **Creates:** none
- **Requirements:** In `mill-add/SKILL.md` and `mill-setup/SKILL.md`, locate the operational Bash invocation examples (the lines that show the `uv run` or `python` command Claude Code is supposed to run when executing the skill). For each, ensure the project path and script path resolve via the `${CLAUDE_PLUGIN_ROOT}` token, not via the `plugins/mill/...` source path. If a wrong/right example pair is appropriate (i.e. the skill currently demonstrates an invocation pattern), add a short comment block — keep it to two fenced bash examples, labeled WRONG and RIGHT, mirroring the CLAUDE.md style. Run a verify-pass over every other operational SKILL.md file inside the mill skills directory: grep each for `plugins/mill/scripts` or `plugins/codeguide/scripts` substrings; classify each hit as descriptive prose (keep, no change), file-path reference inside Reads/Modifies/Creates lists or other markdown (keep, no change), or operational Bash command (FIX — replace with the `${CLAUDE_PLUGIN_ROOT}/scripts/...` form). The hit list from the discussion's verify pass: `mill-add/SKILL.md` lines 8/122/151 (descriptive — keep), `mill-resume/SKILL.md` line 127 (descriptive — keep), `mill-skills-index/SKILL.md` line 20 (verify whether it is operational; if so, fix; this is why mill-skills-index/SKILL.md is listed in Modifies). If the verify pass uncovers an additional operational invocation outside the three files listed in Modifies, halt with a request to re-run plan validation rather than silently expanding scope.
- **Commit:** `docs(skills): use ${CLAUDE_PLUGIN_ROOT} for operational mill script invocations`

### Card 15: Add `**/plugins/*/uv.lock` to gitignore + test

- **Reads:**
  - `plugins/mill/scripts/_gitignore.py`
  - `.gitignore`
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
- **Modifies:**
  - `plugins/mill/scripts/_gitignore.py`
  - `.gitignore`
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
- **Creates:** none
- **Requirements:** In `_gitignore.py`, append `"**/plugins/*/uv.lock"` to the `GLOB_ENTRIES` list. Position it after the existing `**/portals/` entry — the order is irrelevant to behavior but ordering is stable. In `.gitignore`, locate the mill-managed block (between `# === mill-managed (regenerated by mill-setup) ===` and `# === end mill-managed ===`). Add the line `**/plugins/*/uv.lock` to the glob entries inside the block, in the same position as in `GLOB_ENTRIES`. The marker block format is preserved exactly. In `test-gitignore-phase.py`, add an assertion (one new test function, or extend an existing test) confirming `_gitignore.render_block(_gitignore.GLOB_ENTRIES, _gitignore.ANCHORED_ENTRIES)` includes the substring `**/plugins/*/uv.lock` between the START and END markers. Do not delete the stale `plugins/mill/uv.lock` file from the main worktree as part of this card — that deletion belongs to mill-merge's cleanup step (per the discussion's "Out" scope: stale uv.lock removal is bundled with mill-merge cleanup, not committed in this task's branch).
- **Commit:** `fix(_gitignore): add **/plugins/*/uv.lock to GLOB_ENTRIES and propagate to .gitignore`

## Batch Tests

Verify command: `python plugins/mill/unit_tests/test-gitignore-phase.py`

Covers Card 15 directly. Cards 13 and 14 are documentation changes with no automated test surface — they are verified during plan review (the holistic reviewer reads CLAUDE.md and the SKILL.md files in scope and flags any remaining source-tree-path operational invocations) and during the final mill-merge review pass.
