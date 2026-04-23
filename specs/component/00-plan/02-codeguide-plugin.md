# Batch: codeguide-plugin

```yaml
task: codeguide sibling-mode + unified sibling-path convention
batch: codeguide-plugin
cards: 7
verify: null
depends-on: [foundation]
```

## Batch Scope

Upgrade the codeguide plugin to support sibling mode. Seven cards:

1. **Card 3** — fix the stale `millpy/codeguide/` path references in all four codeguide SKILL.md files (pre-existing bug; see spec).
2. **Card 4** — create `plugins/codeguide/scripts/_sibling.py` as a codeguide-local copy of the mill sibling helper. Zero cross-plugin imports.
3. **Card 5** — extend `plugins/codeguide/scripts/resolve.py` with the sibling lookup chain (inline → `.codeguide-root` → sibling via local `_sibling`).
4. **Card 6** — create `plugins/codeguide/scripts/codeguide_commit.py` (mode-aware commit helper).
5. **Card 7** — rewrite `codeguide-setup` SKILL.md for `--sibling` / `--from-url` flags.
6. **Card 8** — rewrite `codeguide-update` SKILL.md to call `codeguide_commit.py` and handle multi-codeguide-per-commit grouping.
7. **Card 9** — `@git-commit` step 2 note about sibling-mode interaction.

### Batch-local decision: no batch-level `verify:`

Unlike batches with runnable code, this batch is mostly skill markdown + pure-Python modules. The two Python modules (`_sibling.py` and `codeguide_commit.py`) get inline module-level validation via their own unit tests if added (out of scope for this iteration — we validate manually on the first real sibling setup). The SKILL.md files are executed by Claude at runtime; there is no static test that catches wording regressions. End-to-end validation happens when the engineer runs `/codeguide-setup --sibling` on the target third-party repo as the first real user of this code.

## Cards

### Card 3: fix stale `millpy/codeguide/` paths in all four codeguide skills

- **Reads:** `plugins/codeguide/skills/codeguide-setup/SKILL.md`, `plugins/codeguide/skills/codeguide-update/SKILL.md`, `plugins/codeguide/skills/codeguide-generate/SKILL.md`, `plugins/codeguide/skills/codeguide-maintain/SKILL.md`, `plugins/codeguide/scripts/resolve.py` (confirm path of the real script).
- **Modifies:** all four SKILL.md files above.
- **Creates:** (none)
- **Requirements:**
  - Replace every occurrence of `${CLAUDE_PLUGIN_ROOT}/scripts/millpy/codeguide/resolve.py` with `${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py`. There are currently four such references, one per skill — grep to confirm no others slipped in.
  - Do not touch other parts of the skills. This card is scoped strictly to the path fix.
  - Preserve `---` YAML frontmatter headers unchanged (these are SKILL.md files; `---` is allowed).
- **Commit:** `fix(codeguide): correct stale millpy/codeguide/ paths to flat scripts/`

### Card 4: `plugins/codeguide/scripts/_sibling.py` (codeguide-local copy)

- **Reads:** `plugins/mill/scripts/_sibling.py` (the authoritative reference from Card 1), `plugins/codeguide/scripts/resolve.py` (pattern for scripts in this plugin).
- **Modifies:** (none)
- **Creates:** `plugins/codeguide/scripts/_sibling.py`
- **Requirements:**
  - Content is IDENTICAL to `plugins/mill/scripts/_sibling.py` — same `resolve_path` function, same CLI entry point, same docstring approach.
  - Docstring explicitly states: "This file is a deliberate duplicate of `plugins/mill/scripts/_sibling.py`. Each plugin carries its own copy to avoid any cross-plugin import assumption. If you edit one, grep for the other and apply the same change."
  - No imports from the mill plugin. No reference to `plugins/mill/` paths. Self-contained.
- **Commit:** `feat(codeguide): add local _sibling.py (identical-twin of mill's)`

### Card 5: extend codeguide `resolve.py` with sibling lookup

- **Reads:** `plugins/codeguide/scripts/resolve.py`, `plugins/codeguide/scripts/_sibling.py` (post-Card-4), `plugins/codeguide/skills/codeguide-setup/SKILL.md` (post-Card-3 path fix).
- **Modifies:** `plugins/codeguide/scripts/resolve.py`
- **Creates:** (none)
- **Requirements:**
  - Preserve the existing inline walk-up lookup unchanged.
  - After the inline walk fails, check for `<git-toplevel>/.codeguide-root`. If present, read the single-line path (absolute or relative-to-toplevel); treat it as the sibling anchor.
  - If no `.codeguide-root`, compute the sibling anchor by importing from the LOCAL `_sibling` module (`from _sibling import resolve_path`), called as `resolve_path("codeguide", git_toplevel)`. Same-directory import, no `${CLAUDE_PLUGIN_ROOT}/../...` nonsense.
  - Sibling walk mirrors the inline walk: for each level from cwd to git-toplevel, check `<sibling_anchor>/<rel-path>/_codeguide/Overview.md`.
  - Return a structured result callers can destructure: `{mode: "inline" | "sibling", cg_root: Path, sibling_anchor: Path | None}`.
  - Exit-code 1 with a helpful message when nothing is found ("run /codeguide-setup first [--sibling]").
  - Preserve any existing public API signatures used by the other codeguide skills.
- **Commit:** `feat(codeguide): resolve.py adds sibling lookup chain (inline / .codeguide-root / sibling)`

### Card 6: `plugins/codeguide/scripts/codeguide_commit.py`

- **Reads:** `plugins/codeguide/scripts/resolve.py` (post-Card-5 state), `plugins/mill/skills/git-commit/SKILL.md`, `plugins/mill/scripts/_subprocess_util.py` (pattern for git-invoking helpers).
- **Modifies:** (none)
- **Creates:** `plugins/codeguide/scripts/codeguide_commit.py`
- **Requirements:**
  - CLI args: `--file <path>` (repeatable), `-m <msg>`.
  - Call `resolve.py` (or directly import its logic) to determine mode.
  - **Inline mode** → `git add <file> …` in the current repo (target repo). Do NOT commit — leave that to the outer `@git-commit` skill that invoked us.
  - **Sibling mode** → `git -C <sibling_anchor> add <file> …` (the file paths are already rooted under the sibling) and `git -C <sibling_anchor> commit -m <msg>`. Commit in the sibling repo directly. Return 0 on success.
  - Stdout is a one-line JSON summary: `{"mode": "...", "committed": true|false, "files": [...]}`. Stderr carries subprocess transcripts.
  - No cross-plugin imports. If subprocess-to-git needs argument escaping, handle it locally; do not reach into mill's `_subprocess_util`.
- **Commit:** `feat(codeguide): codeguide_commit.py mode-aware staging/commit helper`

### Card 7: rewrite `codeguide-setup` SKILL.md for sibling mode

- **Reads:** `plugins/codeguide/skills/codeguide-setup/SKILL.md` (post-Card-3), `plugins/codeguide/scripts/resolve.py` (post-Card-5), `plugins/codeguide/scripts/_sibling.py`.
- **Modifies:** `plugins/codeguide/skills/codeguide-setup/SKILL.md`
- **Creates:** (none)
- **Requirements:**
  - **Preserve the existing `---` YAML frontmatter header** (`name:`, `description:`, `argument-hint:`). Update `argument-hint:` to `[--sibling] [--from-url <git-url>] [.cs .py .ts]`. Do not convert frontmatter to fenced `yaml` — SKILL.md uses `---` per project convention.
  - Without `--sibling`: existing behaviour unchanged (inline setup in cwd-rooted `_codeguide/`).
  - With `--sibling`:
    - Resolve sibling-anchor by invoking `python ${CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py codeguide <git-toplevel>` via subprocess. Parse the stdout path.
    - If anchor doesn't exist: `git init` it (locally, no remote), or `git clone <url>` if `--from-url` provided.
    - Compute `rel-path = cwd.relative_to(git_toplevel)`.
    - Create `<anchor>/<rel-path>/_codeguide/` and copy plugin-owned templates into it.
    - Commit in the sibling repo with message `codeguide-setup: init <rel-path>` (or `init root` when rel-path is empty).
  - Subfolder-refresh and new-subfolder-activation modes (current) behave correctly when invoked inside sibling mode — they mirror into `<anchor>/<rel-path>/` instead of cwd.
  - Mention the `.codeguide-root` override file but do NOT auto-create it; users who want a non-default sibling anchor create it themselves.
  - **Never modify the target repo.** Don't touch `.gitignore`, don't drop marker files, don't auto-commit anything into it.
  - Drop any notion of a `mode:` field written into Overview.md frontmatter — the spec's decisions section does not include such a field, and the resolve chain is deterministic without it.
- **Commit:** `feat(codeguide): setup skill gains --sibling / --from-url flags`

### Card 8: rewrite `codeguide-update` SKILL.md to call `codeguide_commit.py`

- **Reads:** `plugins/codeguide/skills/codeguide-update/SKILL.md` (post-Card-3), `plugins/codeguide/scripts/codeguide_commit.py` (post-Card-6), `plugins/codeguide/scripts/resolve.py` (post-Card-5).
- **Modifies:** `plugins/codeguide/skills/codeguide-update/SKILL.md`
- **Creates:** (none)
- **Requirements:**
  - Preserve the existing `---` YAML frontmatter.
  - Replace the "Does not commit" disclaimer at the top: "In inline mode, the outer `@git-commit` skill commits; in sibling mode, codeguide_commit.py commits in the sibling repo."
  - After updating cg-doc files, invoke `python ${CLAUDE_PLUGIN_ROOT}/scripts/codeguide_commit.py --file … --file … -m "…"` with the actual file list and a generated message.
  - **Multi-codeguide grouping:** when the staged diff touches files under two subfolders that each have their own codeguide, the skill walks each diff-file through `resolve.py` to find its governing cg-root, groups files by root, and processes each group (update + commit) independently.
  - Preserve the existing "update stale docs / flag orphan / update Overview routing" logic verbatim.
- **Commit:** `feat(codeguide): update skill uses codeguide_commit.py + group-by-root`

### Card 9: `@git-commit` step 2 note about sibling mode

- **Reads:** `plugins/mill/skills/git-commit/SKILL.md`, `plugins/codeguide/skills/codeguide-update/SKILL.md` (post-Card-8).
- **Modifies:** `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** (none)
- **Requirements:**
  - Step 2 continues to invoke `@codeguide:codeguide-update` when `_codeguide/Overview.md` exists anywhere (inline OR sibling — resolve.py handles both).
  - Add a note: "In sibling mode, codeguide-update commits into the sibling repo itself via codeguide_commit.py. Do not attempt to stage sibling-rooted files in this commit — the sibling has its own history."
  - Keep the staging rule for inline mode intact.
  - Preserve the existing `---` YAML frontmatter.
- **Commit:** `feat(git-commit): note sibling-mode interaction with codeguide-update`

## Batch Tests

No automatic batch verify. End-to-end validation happens when the engineer runs `/codeguide-setup --sibling` on the target third-party repo; a clean sibling repo created, zero files written to target repo, one commit landed in sibling. That is the smoke test; it happens outside mill-v2's test infrastructure.
