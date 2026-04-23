# Batch: codeguide-plugin

```yaml
task: codeguide sibling-mode + unified sibling-path convention
batch: codeguide-plugin
cards: 5
verify: null
depends-on: [foundation]
```

## Batch Scope

Upgrade the codeguide plugin to support the sibling mode. Changes are split between the resolver (new lookup chain), the setup skill (new --sibling / --from-url flags + auto-git-init), the update skill (new commit helper), and a new `codeguide_commit.py` script that handles mode-aware commits.

No `verify:` command at the batch level — the plugin is pure prose + scripts that are exercised by humans or by mill-go in later tasks. Unit-level testing for pure-Python pieces is covered by the batch's individual card tests where practical; the full integration happens in a later spec when mill-v2 drives a codeguide seed end-to-end (spec 13).

### Batch-local decision

Unlike batch-level `verify:` on other batches, this batch deliberately skips repeatable verification. The reason: the skill markdown is executed by Claude at runtime; there is no static test that catches wording regressions. A later spec that wires mill-plan through codeguide-setup on a real sibling will double as the integration test.

## Cards

### Card 3: extend codeguide `resolve.py` with sibling lookup

- **Reads:** `plugins/codeguide/scripts/millpy/codeguide/resolve.py`, `plugins/mill/scripts/_sibling.py`, `plugins/codeguide/skills/codeguide-setup/SKILL.md`.
- **Modifies:** `plugins/codeguide/scripts/millpy/codeguide/resolve.py`
- **Creates:** (none)
- **Requirements:**
  - Preserve the existing inline walk-up lookup unchanged.
  - After the inline walk fails, check for `<git-toplevel>/.codeguide-root`. If present, read the single-line path (absolute or relative-to-toplevel); treat it as the sibling anchor.
  - If no `.codeguide-root`, compute the sibling anchor by invoking `_sibling.resolve_path("codeguide", git_toplevel)`. Import from the mill plugin via `${CLAUDE_PLUGIN_ROOT}/../mill/scripts/_sibling.py` — resolve the path at call time; do NOT require mill source to be present at import time. If mill plugin is not installed, fail with a readable error.
  - Sibling walk mirrors the inline walk: for each level from cwd to git-toplevel, check `<sibling_anchor>/<rel-path>/_codeguide/Overview.md`.
  - Return a structured result that callers can destructure: `{mode: "inline" | "sibling", cg_root: Path, sibling_anchor: Path | None}`.
  - Exit-code 1 with a helpful message when nothing is found ("run /codeguide-setup first [--sibling]").
- **Commit:** `feat(codeguide): resolve.py adds sibling lookup chain`

### Card 4: `codeguide_commit.py` helper

- **Reads:** `plugins/codeguide/scripts/millpy/codeguide/resolve.py` (post-Card-3 state), `plugins/mill/skills/git-commit/SKILL.md`.
- **Modifies:** (none)
- **Creates:** `plugins/codeguide/scripts/millpy/codeguide/codeguide_commit.py`
- **Requirements:**
  - Accept arguments: list of changed cg-doc paths (`--file <path>` repeatable) and commit message (`-m <msg>`).
  - Call `resolve.py` to determine mode.
  - Inline mode → `git add <file> …` in the current repo (target repo). Do not commit — leave that to the outer `@git-commit` skill that invoked us.
  - Sibling mode → `git -C <sibling_anchor> add <file> …` (the file paths are already rooted under the sibling) and `git -C <sibling_anchor> commit -m <msg>`. Commit in the sibling repo directly. Return 0 on success.
  - Stdout is a one-line JSON summary: `{"mode": "...", "committed": true|false, "files": [...]}`. Stderr carries subprocess transcripts.
- **Commit:** `feat(codeguide): commit.py helper for mode-aware staging/commit`

### Card 5: rewrite `codeguide-setup` SKILL.md for sibling mode

- **Reads:** `plugins/codeguide/skills/codeguide-setup/SKILL.md`, `plugins/codeguide/scripts/millpy/codeguide/resolve.py` (post-Card-3), `plugins/mill/scripts/_sibling.py`.
- **Modifies:** `plugins/codeguide/skills/codeguide-setup/SKILL.md`
- **Creates:** (none)
- **Requirements:**
  - New argument-hint: `[--sibling] [--from-url <git-url>] [.cs .py .ts]`.
  - Without `--sibling`: existing behaviour unchanged (inline setup in cwd-rooted `_codeguide/`).
  - With `--sibling`:
    - Resolve sibling-anchor via `_sibling.resolve_path("codeguide", git_toplevel)`.
    - If anchor doesn't exist: `git init` it (locally, no remote), or `git clone --from-url <url>` if provided.
    - Compute `rel-path = cwd.relative_to(git_toplevel)`.
    - Create `<anchor>/<rel-path>/_codeguide/` and copy plugin-owned templates into it.
    - Commit in the sibling repo with message `codeguide-setup: init <rel-path>` (or `init root` when rel-path is empty).
  - Mode the skill writes into the overview's frontmatter: `mode: inline | sibling`. Resolve.py reads this as a cross-check.
  - Subfolder-refresh and new-subfolder-activation modes (current) behave correctly when invoked inside sibling mode — they mirror into `<anchor>/<rel-path>/` instead of cwd.
  - Mention the `.codeguide-root` override file but do NOT auto-create it; users who want a non-default sibling anchor create it themselves.
  - **Never modify the target repo.** Don't touch `.gitignore`, don't drop marker files, don't auto-commit anything into it.
- **Commit:** `feat(codeguide): setup skill gains --sibling / --from-url flags`

### Card 6: rewrite `codeguide-update` SKILL.md to call `codeguide_commit.py`

- **Reads:** `plugins/codeguide/skills/codeguide-update/SKILL.md`, `plugins/codeguide/scripts/millpy/codeguide/codeguide_commit.py` (post-Card-4).
- **Modifies:** `plugins/codeguide/skills/codeguide-update/SKILL.md`
- **Creates:** (none)
- **Requirements:**
  - After updating cg-doc files, invoke `codeguide_commit.py --file … --file … -m "…"` with the actual file list and a generated message (matching current skill's style).
  - In the "Does not commit" disclaimer at the top: change wording from "Does not commit" to "In inline mode, the outer `@git-commit` skill commits; in sibling mode, codeguide_commit.py commits in the sibling repo."
  - Group-by-root logic: the skill takes a staged-diff file list, walks it through `resolve.py` to find each file's cg-root, groups, and processes each group (update + commit) independently. Covers the multi-codeguide case where one commit touches two subfolder codeguides.
  - Preserve the existing "update stale docs / flag orphan / update Overview routing" logic verbatim.
- **Commit:** `feat(codeguide): update skill uses commit.py + group-by-root`

### Card 7: update `@git-commit` step 2 to mention sibling mode

- **Reads:** `plugins/mill/skills/git-commit/SKILL.md`, `plugins/codeguide/skills/codeguide-update/SKILL.md` (post-Card-6).
- **Modifies:** `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** (none)
- **Requirements:**
  - Step 2 continues to invoke `@codeguide:codeguide-update` when `_codeguide/Overview.md` exists anywhere (inline OR sibling — resolve.py handles both).
  - Add a note: "In sibling mode, codeguide-update commits into the sibling repo itself via codeguide_commit.py. Do not attempt to stage sibling-rooted files in this commit — the sibling has its own history."
  - Keep the staging rule for inline mode intact.
- **Commit:** `feat(git-commit): note sibling-mode interaction with codeguide-update`

## Batch Tests

None runnable automatically in this batch. The plugin changes are exercised when codeguide is actually used on a sibling repo — which happens in spec 13's eventual implementation, or when the engineer runs this on the upcoming third-party codebase. Integration test for sibling setup is out of scope for this spec (would require either a live sibling-init test or stubbing `git init`).

Manual smoke: on the engineer's target third-party repo, run `/codeguide-setup --sibling` from a subfolder. Expect: sibling dir created at `<parent>/<repo>.codeguide/<rel-path>/_codeguide/`, initial commit in sibling repo, nothing written to target repo.
