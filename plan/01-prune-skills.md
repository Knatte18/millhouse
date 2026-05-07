# Batch: Prune unused skills and scripts

```yaml
task: 27 (A) — Prune unused skills and scripts
batch: Prune unused skills and scripts
number: 1
cards: 8
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Delete three unused skills (`mill-list`, `mill-fetch-issues`, `mill-worktree`) along with their scripts and test files. Rescue the 8 `_render_body_with_comments` tests into a new `test-gh-issues.py`. Update the seven files that reference the deleted artifacts. Regenerate `SKILLS.md` and manually prune `SCRIPTS.md`. Cards must be executed in order: Card 1 before Card 2 (new test file before source deletion), all others after Card 2.

## Cards

### Card 1: Create test-gh-issues.py

- **Context:**
  - `plugins/mill/unit_tests/test-millpy-fetch-issues.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-gh-issues.py`
- **Deletes:** none
- **Requirements:** Create `test-gh-issues.py` by copying the 8 `_render_body_with_comments` test cases verbatim from `test-millpy-fetch-issues.py`. Keep the identical preamble: `HUB = Path(...).resolve().parent.parent.parent.parent`, `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))`, and `from _gh_issues import GhError, _render_body_with_comments`. Keep the same `main()` / `if __name__ == "__main__": sys.exit(main())` structure. The 8 cases to copy are: empty-comments, single, ordering, exact-10, 11-comments, 15-comments, deleted-author, empty-body. Omit the 3 CLI wrapper tests (happy path, --out override, GhError path on `mill_fetch_issues.main`). The final print line should read `"All gh-issues unit tests passed."`.
- **Commit:** `test(gh-issues): extract _render_body_with_comments tests into test-gh-issues.py`

### Card 2: Delete pruned skill directories, scripts, and test files

- **Context:** none
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/skills/mill-list/SKILL.md`
  - `plugins/mill/skills/mill-fetch-issues/SKILL.md`
  - `plugins/mill/skills/mill-worktree/SKILL.md`
  - `plugins/mill/scripts/millpy-list.py`
  - `plugins/mill/scripts/millpy-fetch-issues.py`
  - `plugins/mill/scripts/millpy-worktree.py`
  - `plugins/mill/unit_tests/test-millpy-fetch-issues.py`
  - `plugins/mill/unit_tests/test-millpy-worktree.py`
- **Requirements:** Delete all 8 files. After deleting each SKILL.md, also remove its now-empty parent directory (`plugins/mill/skills/mill-list/`, `plugins/mill/skills/mill-fetch-issues/`, `plugins/mill/skills/mill-worktree/`). Verify the three skill directories no longer exist under `plugins/mill/skills/`.
- **Commit:** `chore(mill): delete mill-list, mill-fetch-issues, mill-worktree skills and scripts`

### Card 3: Remove deleted scripts from SHORTCUT_SCRIPTS

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_shortcuts.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Remove `"millpy-list"`, `"millpy-worktree"`, and `"millpy-fetch-issues"` from the `SHORTCUT_SCRIPTS` list in `_shortcuts.py`. Preserve all remaining entries and their order. No other changes to the file.
- **Commit:** `chore(mill): remove pruned scripts from SHORTCUT_SCRIPTS`

### Card 4: Fix orphan-worktree message and config docstring

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-cleanup.py` around line 178: change the f-string segment `run 'mill-worktree remove {entry}' to clean up` to `run 'git worktree remove --force {entry}' to clean up`. In `_config.py` module docstring around line 10: remove `mill-worktree,` from the list that reads `mill-color, mill-terminal, mill-vscode, mill-worktree, and mill-spawn`; the result should read `mill-color, mill-terminal, mill-vscode, and mill-spawn`.
- **Commit:** `chore(mill): replace mill-worktree refs in cleanup message and config docstring`

### Card 5: Update test fixtures and assertions

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/unit_tests/test-shortcut-wrapper.py`
  - `plugins/mill/unit_tests/test-skill-writer.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-cleanup.py` line 272: change `"mill-worktree remove"` to `"git worktree remove --force"` in the `assert ... in orphan_lines[0]` check. In `test-shortcut-wrapper.py` lines 22–28: change both occurrences of `"millpy-list"` to `"millpy-status"` and `"millpy-list.py"` to `"millpy-status.py"` (two string literals in the render-test block). In `test-skill-writer.py` lines 155–173: change all four occurrences of `"mill-fetch-issues"` to `"mill-self-report"`, updating the `hyphen_path` assignment, the `write_skill_file` call, the directory-existence check, and the SKILL.md-existence check; update any path string that contains `"mill-fetch-issues"` to `"mill-self-report"`. Also in `test-skill-writer.py` lines 36–100 (the `iter_target_scripts` block): remove `"millpy-list"`, `"millpy-worktree"`, and `"millpy-fetch-issues"` from the `expected_stems` list (leaving 10 stems); change `if len(result) != 13:` to `if len(result) != 10:`; update the error/PASS messages from `13` to `10`; change the comment `# Touch one file per SHORTCUT_SCRIPTS entry (14 total)` to `(11 total)`; change the block heading comment from `the 13 expected paths` to `the 10 expected paths`.
- **Commit:** `test(mill): update fixtures and assertions for pruned skills`

### Card 6: Update mill-setup/SKILL.md reference

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** On the line containing `/mill-list to list them` (line ~463), change `/mill-list` to `/mill-status`. No other changes to the file.
- **Commit:** `docs(mill-setup): replace /mill-list reference with /mill-status`

### Card 7: Prune SCRIPTS.md

- **Context:** none
- **Edits:**
  - `plugins/mill/SCRIPTS.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Remove three sections from `SCRIPTS.md`. Each section spans from its `## millpy-<name>` heading to (not including) the next `##` heading. Sections to remove: `## millpy-fetch-issues` (lines 96–108), `## millpy-list` (lines 125–130), `## millpy-worktree` (lines 283–298). Also remove the bullet for `millpy-list.py` in the `## Generation notes` section at line 302 (the line that reads `- \`millpy-list.py\` — does not implement \`--help\`; invocation runs the script and prints the task list.`). No other changes.
- **Commit:** `docs(mill): remove SCRIPTS.md entries for pruned scripts`

### Card 8: Regenerate SKILLS.md

- **Context:**
  - `plugins/mill/scripts/millpy-skills-index.py`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** From the worktree root, run `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"`. This regenerates `SKILLS.md` at the repo root. Verify that the output no longer contains rows for `mill-list`, `mill-fetch-issues`, or `mill-worktree` in the mill section. No manual editing of `SKILLS.md` — the script is the sole writer.
- **Commit:** `docs: regenerate SKILLS.md — remove pruned mill skills`

## Batch Tests

The verify command `python plugins/mill/unit_tests/run-all.py` runs every `test-*.py` in `plugins/mill/unit_tests/` as a subprocess. After this batch:

- `test-gh-issues.py` is discovered and its 8 `_render_body_with_comments` tests pass
- `test-cleanup.py` passes with the updated `git worktree remove --force` assertion
- `test-shortcut-wrapper.py` passes with the `millpy-status` fixture and the reduced `SHORTCUT_SCRIPTS` count
- `test-skill-writer.py` passes with the `mill-self-report` fixture
- `test-millpy-fetch-issues.py` and `test-millpy-worktree.py` are absent — not discovered, no phantom failures
