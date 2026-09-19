# Batch: fix-citation-scan-pathspec

```yaml
task: mill-finalize/mill-merge-in citation-scan pathspec `:!_mill` fails on git 2.53+
batch: fix-citation-scan-pathspec
number: 1
cards: 2
verify: PYTHONPATH= git grep -q '.' -- . ':(exclude)_mill' ':(exclude)plugins/**/SKILL.md' ':(exclude)plugins/**/unit_tests/**' ':(exclude)plugins/**/integration_tests/**'
depends-on: []
```

## Batch Scope

This batch fixes the git-2.53+ pathspec-magic bug in both citation-scan snippets by switching their four `:!<pattern>` short-form exclusions to the long-form `:(exclude)<pattern>` syntax. The two cards are independent (each edits a different file, no shared state), grouped into one batch because they are the same one-line mechanical fix applied twice and share one verify command. No `## Rename mechanic` section is needed — neither card performs a `Moves:`.

## Cards

### Card 1: Fix mill-finalize/SKILL.md citation-scan pathspec

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the "Citation scan (non-blocking)" section's fenced `bash` block (the `git -C <worktree> grep` invocation), replace the four short-form exclude pathspecs with the long-form `:(exclude)` equivalent. The exact current text to replace, reproduced byte-for-byte at its own existing indentation:
  ```
    ':!<task_dir>' ':!plugins/**/SKILL.md' ':!plugins/**/unit_tests/**' ':!plugins/**/integration_tests/**'
  ```
  becomes:
  ```
    ':(exclude)<task_dir>' ':(exclude)plugins/**/SKILL.md' ':(exclude)plugins/**/unit_tests/**' ':(exclude)plugins/**/integration_tests/**'
  ```
  Change only these four pathspec tokens on this one line. Do not change the preceding `git -C <worktree> grep -InE '\]\([./]*_mill/discussion\.md\)' -- . \` line, and do not change any of the explanatory prose in the surrounding "Citation scan (non-blocking)" section — none of it quotes the pathspec syntax itself, so none of it needs to change.
- **Commit:** `fix(mill-finalize): switch citation-scan pathspec to long-form :(exclude) syntax`

### Card 2: Fix mill-merge/SKILL.md citation-scan pathspec

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the "Citation scan (non-blocking, #930)" section's fenced `bash` block (the `git -C <worktree> grep` invocation), replace the same four short-form exclude pathspecs with the long-form `:(exclude)` equivalent — identical substitution to Card 1, applied to this file's own copy of the snippet. The exact current text to replace, reproduced byte-for-byte at its own existing indentation:
  ```
    ':!<task_dir>' ':!plugins/**/SKILL.md' ':!plugins/**/unit_tests/**' ':!plugins/**/integration_tests/**'
  ```
  becomes:
  ```
    ':(exclude)<task_dir>' ':(exclude)plugins/**/SKILL.md' ':(exclude)plugins/**/unit_tests/**' ':(exclude)plugins/**/integration_tests/**'
  ```
  Change only these four pathspec tokens on this one line. Do not change the preceding `git -C <worktree> grep -InE '\]\([./]*_mill/discussion\.md\)' -- . \` line, and do not change any of the explanatory prose in the surrounding section.
- **Commit:** `fix(mill-merge): switch citation-scan pathspec to long-form :(exclude) syntax`

## Batch Tests

`verify:` runs `git grep -q '.' -- . ':(exclude)_mill' ':(exclude)plugins/**/SKILL.md' ':(exclude)plugins/**/unit_tests/**' ':(exclude)plugins/**/integration_tests/**'` from the worktree root (plain-string form, `cwd: git_root`).

This deliberately does NOT reuse the citation-scan snippets' own literal search pattern (`\]\([./]*_mill/discussion\.md\)`) as the verify command: that pattern currently has zero matches in this repo, so `git grep` would exit 1 on the documented no-matches case — a false verify failure unrelated to the bug. Instead, the broad pattern `'.'` (matches any non-empty line) is guaranteed to match at least one line among the many non-excluded files in this repo, so a clean exit 0 specifically tests "does this exact `:(exclude)`-form pathspec list parse and execute without the `fatal: Unimplemented pathspec magic` error" — the actual regression this batch fixes — independent of whether any real citation happens to exist right now.

Confirmed locally before writing this plan: the pre-fix short-form pathspec list (`':!_mill' ':!plugins/**/SKILL.md' ':!plugins/**/unit_tests/**' ':!plugins/**/integration_tests/**'`) makes this exact verify command exit 128 with `fatal: Unimplemented pathspec magic '_' in ':!_mill'` on the installed git 2.53.0; the post-fix long-form list exits 0. One verify command covers both cards, since both cards apply the identical pathspec-list substitution (to two different files) and the command under test names the pathspec list itself, not either file's path.

No unit/integration test exists or is warranted for this fix — see `_mill/discussion.md`'s Testing section for why (the bug is in the installed git binary's pathspec parsing, not in any mill script or Python module).
