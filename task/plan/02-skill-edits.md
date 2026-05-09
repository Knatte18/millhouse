# Batch: skill-edits

```yaml
task: 37 (A) — Codeguide bug-fix batch 1
batch: skill-edits
number: 2
cards: 3
verify: null
depends-on: [1]
```

## Batch Scope

SKILL.md prose edits that operationalise both fixes. Card 3 promotes `resolve.py` to a top-of-file `## Resolution` callout in all four `codeguide-*` SKILL.md files (#203). Card 4 wires `codeguide-update` to call the new `resolve_scope.py` for default-scope file enumeration (#210). Card 5 rewrites `git-commit`'s codeguide-detection step to call `resolve.py` instead of hardcoded layout checks (also #203, the `git-commit` slice).

`depends-on: [1]` because Card 4 references `resolve_scope.py` by path in user-facing instructions; the helper must exist (and pass tests) before the doc references ship. mill-go's per-card pipeline doesn't lint SKILL.md, so this batch has no `verify:` of its own — review-plan and review-code catch any structural issues.

Batch-local decisions:

- **Resolution callout body is verbatim across the three "consumer" codeguide skills (`codeguide-generate`, `codeguide-maintain`, `codeguide-update`).** Identical paragraph text in those three skills keeps the agent's mental model consistent and lets a future global edit happen via `replace_all`. `codeguide-setup` gets its own variant: the consumer skills halt on `found == false` (no codeguide to operate on), but for `codeguide-setup` `found == false` is the *primary* first-time-setup case — its callout describes how `found`/`mode`/`cg_root`/`sibling_anchor` feed the first-time/refresh/subfolder dispatch in Step 5 instead. The per-file variation in *which* existing step the back-reference replaces stays as before (Step 1 in `codeguide-generate` / `codeguide-maintain`, Step 3 in `codeguide-setup`; `codeguide-update`'s Step 1 is rewritten by Card 4).
- **No frontmatter changes.** The `description:` field was discussed and explicitly rejected as the discoverability fix (it's too subtle).
- **Step renumbering keeps stable identifiers.** When `codeguide-update`'s old Step 1 splits into 1a (resolve root) and 1b (enumerate scope), every cross-reference inside the same file is updated in the same edit (e.g. "## Steps" tables, prose like "see step 1"). No dangling references.

## Cards

### Card 3: Promote resolver call to a `## Resolution` callout in every codeguide-* SKILL.md

- **Context:**
  - `plugins/codeguide/scripts/resolve.py`
- **Edits:**
  - `plugins/codeguide/skills/codeguide-generate/SKILL.md`
  - `plugins/codeguide/skills/codeguide-maintain/SKILL.md`
  - `plugins/codeguide/skills/codeguide-setup/SKILL.md`
  - `plugins/codeguide/skills/codeguide-update/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In each of the four files, insert a `## Resolution` block immediately after the YAML frontmatter (the closing `---`) AND any one-paragraph description that follows it, but BEFORE the first existing `##` heading. The block content depends on the file:

    For `codeguide-generate/SKILL.md`, `codeguide-maintain/SKILL.md`, and `codeguide-update/SKILL.md` — verbatim, identical across all three:

    ```
    ## Resolution

    Before doing anything else, run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` to find the codeguide root for this repo. The script prints a JSON object: `{mode, cg_root, sibling_anchor, found}`. If `found == false`, halt and tell the user to run `/codeguide-setup` first.
    ```

    For `codeguide-setup/SKILL.md` — different variant, because `found == false` is the primary first-time-setup case and Steps 1–2 (flag parsing, git-toplevel detection) must run before `resolve.py`:

    ```
    ## Resolution

    After parsing flags (Step 1) and detecting the git toplevel (Step 2), run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` to discover existing codeguide state. The script prints `{mode, cg_root, sibling_anchor, found}`. The `found` flag — together with `mode`, `cg_root`, and `sibling_anchor` — drives the first-time / refresh / subfolder dispatch in Step 5. Do NOT halt on `found == false`; that is the expected result for first-time setup.
    ```

  - Replace the existing buried resolver step with a one-line back-reference:
    - In `codeguide-generate/SKILL.md`: existing Step 1 ("Find `_codeguide/`: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` and parse the JSON object …") is replaced by `1. **Resolve codeguide root.** See `## Resolution` above. Bind `git_toplevel` separately via `git rev-parse --show-toplevel` for the placement-rule logic in Step 9.` (The `git_toplevel` binding is preserved because Step 9's placement rule depends on it; only the resolver-call portion of the original Step 1 collapses.)
    - In `codeguide-maintain/SKILL.md`: existing Step 1 ("Find `_codeguide/`: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py` …") is replaced by `1. **Resolve codeguide root.** See `## Resolution` above.`
    - In `codeguide-setup/SKILL.md`: existing Step 3 ("Resolve existing codeguide state: Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` …") is replaced by `3. **Resolve existing codeguide state.** See `## Resolution` above. Parse the JSON for `{mode, cg_root, sibling_anchor, found}` to drive the first-time/refresh/subfolder dispatch in Step 5.` (The dispatch dependency on the JSON is preserved.)
    - In `codeguide-update/SKILL.md`: existing Step 1 ("Resolve per file → group by cg-root. For each source file in scope, run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` …") is NOT replaced by Card 3. Card 4 rewrites that step. Card 3 only adds the `## Resolution` callout to `codeguide-update`; the Step 1 body is left as-is for Card 4 to modify.
  - Step renumbering: in `codeguide-generate/SKILL.md` and `codeguide-maintain/SKILL.md` no renumbering is needed (Step 1 stays at 1, just shrunk). In `codeguide-setup/SKILL.md` Steps 1, 2, 4–12 are unchanged; only Step 3 is shrunk.
  - YAML frontmatter (`name:`, `description:`, `argument-hint:`) is byte-for-byte unchanged in every file.
  - Cross-references: scan each file after editing for any prose like "see Step 1" / "as resolved in Step 3" — none currently exist that would break, but verify with a final read.
  - Do not modify any other section of any of the four files (no `## Modes`, no `## Scope`, no `## Rules`, no `## Parallelism`).
- **Commit:** `docs(codeguide): promote resolver call to top-of-file Resolution callout`

### Card 4: Delegate default-scope file enumeration in `codeguide-update` to `resolve_scope.py`

- **Context:**
  - `plugins/codeguide/scripts/resolve_scope.py`
- **Edits:**
  - `plugins/codeguide/skills/codeguide-update/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Edit only `plugins/codeguide/skills/codeguide-update/SKILL.md`. Do not touch the other codeguide skills.
  - In the `## Scope` section, retain the bulleted list explaining `$ARGUMENTS` shapes (no-arg / `1h` / `HEAD~3` / explicit paths). Append one paragraph after the list:

    ```
    On a non-base branch with no argument, the no-arg default expands to `<parent-branch>..HEAD ∪ current-diff` so the post-commit / pre-PR case (clean tree, work already committed) is non-empty. Parent detection is git-native: `origin/HEAD` first, then `origin/main`, then `origin/master`; if none exist, the helper degrades to current-diff-only. File enumeration is delegated to `resolve_scope.py` — see Step 1b below.
    ```

  - Restructure the `## Steps` section as follows:
    - **Old Step 1** ("Resolve per file → group by cg-root.") splits into **new Step 1a** and **new Step 1b**. Renumber inline.
    - **New Step 1a:** `1. **Resolve codeguide root.** See `## Resolution` above.` (This is the back-reference Card 3 didn't write for this file.)
    - **New Step 1b:** `2. **Enumerate source files in scope.** Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_scope.py $ARGUMENTS` from the repo root. Stdout is one absolute path per line, deduped. Stderr's last non-empty line is a JSON summary `{mode, parent, base_branch, included_committed, included_diff}` for traceability. The helper handles `$ARGUMENTS` parsing (no-arg / `1h` / `HEAD~3` / explicit paths), parent-branch detection via `origin/HEAD`/`origin/main`/`origin/master`, and the `<parent>..HEAD ∪ current-diff` union for the no-arg-on-task-branch case.`
    - **New Step 3** (was old Step 1's per-file resolve): `3. **Resolve per file → group by cg-root.** For each source file from Step 2, run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` from that file's directory to get `{mode, cg_root, sibling_anchor}`. Group files whose resolve result shares the same `cg_root`. Files with `found == false` (no governing codeguide) → flag and skip. Most repos have a single root codeguide, so typically you get one group. Multi-codeguide repos (repo-level + one-or-more subfolder workspaces) get one group per subtree.`
    - **Old Step 2** (the long "For each group" body with sub-steps a–g) becomes **new Step 4**, body verbatim. Sub-steps a–g are unchanged.
    - **Old Step 3** ("Report …") becomes **new Step 5**, body verbatim.
  - Cross-references: the old SKILL.md uses "Step 1" / "Step 2" only inside the long "For each group" body's prose. Scan after editing; replace any "Step 1" reference that means "the per-file resolve step" with "Step 3", and any "Step 2" reference that means "the per-group processing" with "Step 4". (The current file does not appear to contain such references; verification is part of the card.)
  - The `## Scope` bulleted list itself does NOT change shape (the four bullets stay). The added paragraph is appended after the bullets.
  - The `## Rules` section is unchanged.
  - YAML frontmatter unchanged.
- **Commit:** `docs(codeguide-update): delegate scope enumeration to resolve_scope.py`

### Card 5: Replace `git-commit`'s codeguide-detection prose with a `resolve.py` call

- **Context:**
  - `plugins/codeguide/scripts/resolve.py`
  - `plugins/codeguide/skills/codeguide-update/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Edit only `plugins/mill/skills/git-commit/SKILL.md`. The target is the `## Pre-commit steps` → `### 2. Codeguide sync (only if codeguide is initialized)` subsection.
  - Replace the current first paragraph of that subsection (which begins "Run `@codeguide:codeguide-update` whenever codeguide is initialized for this repo — either **inline** … or **sibling** …") with:

    ```
    Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` from the repo root. Parse the JSON object `{mode, cg_root, sibling_anchor, found}`. If `found == false`, skip this step entirely (codeguide is not initialised for this repo). Otherwise invoke `@codeguide:codeguide-update`; the `codeguide-update` skill re-resolves per file and handles inline / sibling itself.
    ```

  - Keep the two existing inline-vs-sibling explainer bullets that follow the rewritten paragraph:
    - `- **Inline mode** → doc files live inside this repo. \`codeguide-update\`'s helper (\`codeguide_commit.py --mode inline\`) stages them; this skill commits them alongside source changes as part of step 3.`
    - `- **Sibling mode** → doc files live in the sibling repo and are committed there by \`codeguide_commit.py --mode sibling\` as its own commit. **Do not** try to stage sibling-rooted paths in this commit — the sibling has its own history.`

    These describe consequences for git-commit's own staging behavior, not detection logic, so they remain. Keep the `mode` value reading consistent — the prose continues to say "inline mode" / "sibling mode" matching `resolve.py`'s `mode:` JSON field.
  - The heading `### 2. Codeguide sync (only if codeguide is initialized)` is unchanged.
  - The other subsections of `## Pre-commit steps` (Lint) and the `## Rules` section are unchanged.
  - YAML frontmatter (`name:`, `description:`, `argument-hint:`) unchanged.
- **Commit:** `docs(git-commit): use resolve.py for codeguide detection`

## Batch Tests

No `verify:` for this batch — every change is documentation. Correctness is enforced by:

- **mill-plan's plan-review** (already running on this plan) — catches structural issues in the cards themselves.
- **mill-go's per-batch code-review** — reads the actual SKILL.md edits and confirms the back-references resolve, frontmatter is preserved, and the cross-references in `codeguide-update` after step renumbering still make sense.
- **The next user-driven `/codeguide-update` invocation** — first real-world test of the delegation. No automated harness covers this and the discussion explicitly excluded an integration test (Q8 = A).
