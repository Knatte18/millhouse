# Batch: codeguide-setup-skill

```yaml
task: '3 (A) — codeguide improvements: sibling placement + --branch flag'
batch: codeguide-setup-skill
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Updates `plugins/codeguide/skills/codeguide-setup/SKILL.md` so the one-repo-many-branches pattern works: a single shared remote (e.g. `HenrikNORCE/all-codeguides`) with one branch per project. Two coupled changes: argument parsing replaces `--from-url <url>` with `--sibling <url>` (URL becomes a direct positional argument to `--sibling`) and adds `--branch <name>`; Step 4's "create the sibling anchor" branch picker gains a three-way decision tree driven by `git ls-remote --heads`. Independent of the codeguide-generate batch — they touch different SKILL.md files, share no state.

External interface this batch produces: an updated SKILL.md whose argument-hint is `[--sibling [<url>]] [--branch <name>] [.cs .py .ts]`, whose Step 1 parsing knows about `--sibling <url>` and `--branch <name>`, and whose Step 4 distinguishes "no URL", "URL no branch", "URL + branch exists on remote", "URL + branch absent from remote", and "non-zero ls-remote exit". No code consumes this — agents read the SKILL.md.

Batch-local decisions: none beyond the Shared Decisions in the overview.

## Cards

### Card 3: Update argument-hint and Step 1 parsing for `--sibling <url>` + `--branch <name>`

- **Reads:**
  - `plugins/codeguide/skills/codeguide-setup/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/codeguide/skills/codeguide-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Two coordinated edits to the same file. First, replace the front-matter `argument-hint:` value — currently `"[--sibling] [--from-url <git-url>] [.cs .py .ts]"` — with `"[--sibling [<url>]] [--branch <name>] [.cs .py .ts]"`. Second, rewrite Step 1's three sub-bullets. The current bullets read: (1) `--sibling → sibling mode`; (2) `--from-url <git-url> → when creating the sibling repo for the first time, git clone <git-url> instead of git init. Ignored without --sibling.`; (3) extension tokens. Replace with: (1) `--sibling` or `--sibling <url>` → sibling mode; an optional URL argument (the next non-flag token following `--sibling`) clones from that URL instead of `git init`; (2) `--branch <name>` → branch to use when cloning or initializing the sibling anchor; requires `--sibling <url>` (a URL must be present). If `--branch` is given without a URL in `--sibling`, the agent must stop with the error message `"--branch requires a URL — use --sibling <url> --branch <name>"`. (3) Extension tokens unchanged. The `--from-url` flag is removed entirely — no alias, no deprecation note. Search the rest of the file for any other reference to `--from-url` and update each one to `--sibling <url>` (notably the existing reference inside Step 4). Do not modify Step 4's structural logic in this card; that is Card 4. Step numbering stays unchanged.
- **Commit:** `docs(codeguide-setup): replace --from-url with --sibling <url>, add --branch flag`

### Card 4: Update Step 4 to add `git ls-remote`-driven clone/orphan branch logic

- **Reads:**
  - `plugins/codeguide/skills/codeguide-setup/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/codeguide/skills/codeguide-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Step 4's "Compute target root" sub-bullet for sibling mode currently says: `If <sibling-anchor> does not exist yet: create it with git init, OR git clone <git-url> <sibling-anchor> when --from-url <url> was given.` Replace this single sentence with a five-way decision tree mirroring `discussion.md` Technical context "New step 4". The decision tree applies only when the sibling anchor does not yet exist; the existing-anchor case continues to read `If <sibling-anchor> already exists and is a git repo: <root> = <sibling-anchor> / <rel-path>` and must additionally state that `--branch` is ignored when the anchor already exists (matches the `### --branch when anchor already exists` decision). The five new-anchor branches: (a) no URL → `git init <sibling-anchor>`; (b) URL, no `--branch` → `git clone <url> <sibling-anchor>`; (c) URL + `--branch <name>` → first run `git ls-remote --heads <url> <branch>`, then dispatch on (c.i) exit 0 with non-empty stdout → `git clone -b <branch> --single-branch <url> <sibling-anchor>`; (c.ii) exit 0 with empty stdout → `git init <sibling-anchor>` then `git -C <sibling-anchor> remote add origin <url>` then `git -C <sibling-anchor> checkout -b <branch>` (orphan branch; do NOT push at setup time — first commit pushes); (c.iii) non-zero exit → stop with an error message identifying the network/auth failure. Format the decision tree as a nested bullet list under the Step 4 sibling-mode bullet so the structure is scannable. Do not change any other Step 4 sub-bullet (`<rel-path>` computation, the inline-mode branch, the `.codeguide-root` override). Step numbering stays unchanged.
- **Commit:** `docs(codeguide-setup): add ls-remote-driven branch decision tree in Step 4`

## Batch Tests

`verify: null` — pure SKILL.md prose, no executable surface. Manual integration verification per `discussion.md` Testing section: clone-case, orphan-case, no-URL+--branch error, existing-anchor+--branch ignore, no-`--branch` regression (default-branch clone).
