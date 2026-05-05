# Discussion: 3 (A) — codeguide improvements: sibling placement + --branch flag

```yaml
task: '3 (A) — codeguide improvements: sibling placement + --branch flag'
slug: codeguide-improvements
status: discussing
parent: main
```

## Problem

Two independent gaps in the codeguide plugin's SKILL.md files. First: `codeguide-generate` SKILL.md says nothing about where `_codeguide/` folders go in sibling mode, so agents default to placing all docs under a flat `_codeguide/modules/` at the sibling anchor root — collapsing per-project structure. The correct layout mirrors inline mode: each project gets its own `_codeguide/` at the mirrored path under the sibling anchor. `resolve.py`'s sibling walk already handles this correctly; the rule just isn't written down.

Second: `codeguide-setup` supports `--sibling --from-url <url>` to clone an existing remote repo as the sibling anchor, but has no way to specify a branch. The one-repo-many-branches pattern (one shared remote with a branch per project's codeguide) requires `--branch <name>`. Additionally, the current `--from-url` flag design is awkward — URL should be an argument to `--sibling`, not a separate flag.

## Scope

**In:**
- `plugins/codeguide/skills/codeguide-generate/SKILL.md` —
  - Step 1: switch from `resolve.py` to `resolve.py --json` so Step 9 has access to `mode` and `sibling_anchor`; also fetch `git rev-parse --show-toplevel` for relative-path computation
  - Step 9: add sibling placement rule + multi-project worked example using the values from Step 1
- `plugins/codeguide/skills/codeguide-setup/SKILL.md` — replace `--from-url <url>` with `--sibling <url>` (URL as direct argument); add `--branch <name>` flag with clone-or-orphan logic; update argument-hint and step 4

**Out:**
- `plugins/codeguide/scripts/resolve.py` — no changes; sibling walk already correct
- `plugins/codeguide/scripts/_sibling.py` — no changes
- Any other codeguide scripts or templates
- `codeguide-maintain`, `codeguide-update` SKILL.md files
- mill-setup or wiki-setup (parallel task 4 handles that)

## Decisions

### Sibling placement rule location

- Decision: Add the rule inline in Step 9 of codeguide-generate SKILL.md ("Create docs for new project"), where docs are actually written. Step 1 is updated in tandem to expose the values Step 9 needs (`mode`, `sibling_anchor`, `git_toplevel`).
- Rationale: Most contextually relevant — an agent reading the steps encounters the rule exactly where it needs it. A separate section before the steps creates a reading split. Step 1 carries the prerequisite resolution (matches codeguide-setup's Step 3 pattern).
- Rejected: New `## Placement` section before Steps (reading split); rule in Step 1 only (writing happens later, easy to miss).

### Worked example scope

- Decision: Multi-project monorepo showing two projects at different paths.
- Rationale: The mirroring rule is only non-obvious when there are multiple projects — a single-project example doesn't show that each project gets its own `_codeguide/`, not a shared one.
- Rejected: Single project (doesn't illustrate the mirroring).

### --from-url redesign

- Decision: Replace `--from-url <url>` with URL as direct argument to `--sibling`. Old `--from-url` flag is removed.
- Rationale: `--sibling <url>` reads naturally; `--sibling --from-url <url>` is redundant indirection. No backward-compatibility concern — SKILL.md is instructions for an agent, not a published CLI.
- Rejected: Keep `--from-url` and add `--sibling <url>` as alias (two ways to do the same thing).

### New CLI shape

- Decision: `--sibling` takes an optional positional URL argument: `--sibling` (local init) or `--sibling <url>` (clone from URL). `--branch <name>` is a separate flag.
- Rationale: Clean separation — mode flag vs. target spec.
- Rejected: `--url <url>` as standalone flag (loses the "sibling" grouping).

### --branch without URL

- Decision: If `--branch` is given but `--sibling` has no URL, report an error: "`--branch` requires a URL — use `--sibling <url> --branch <name>`."
- Rationale: No remote means no branch to clone or create on; silent ignore would hide a likely misconfiguration.
- Rejected: Silently ignore (hides misconfiguration).

### --branch when anchor already exists

- Decision: Ignore `--branch` — the anchor is already a git repo with its own branch history. Only applies during "creating the sibling for the first time."
- Rationale: Switching branches on an existing sibling with uncommitted state is destructive. Out of scope.
- Rejected: `git -C <anchor> checkout <branch>` (risky, out of scope).

### Orphan branch creation — no push at setup time

- Decision: When branch doesn't exist on remote: `git init <anchor>` + `git remote add origin <url>` + `git checkout -b <branch>`. Do not push.
- Rationale: Push requires network + credentials and should happen on first commit (step 11 already commits in sibling mode, which the agent can then push via `@git-commit`).
- Rejected: Immediate `git push --set-upstream origin <branch>` (requires credentials at setup, no content to push yet).

## Technical context

**codeguide-generate SKILL.md** (`plugins/codeguide/skills/codeguide-generate/SKILL.md`):

Step 1 currently reads:

> Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py` to locate the nearest `_codeguide/` containing config.yaml.

This returns only the path, with no information about mode or anchor — so Step 9 has nothing to base placement on. Update Step 1 to:

> Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json` and parse `{mode, cg_root, sibling_anchor, found}`. Also fetch `git_toplevel` via `git rev-parse --show-toplevel`.

(Same pattern that codeguide-setup Step 3 already uses.)

Step 9 currently reads:

> Create `_codeguide/` and `_codeguide/modules/`
> Write `_codeguide/Overview.md` …

No mention of sibling mode at all. The rule to add: when `mode == "sibling"`, place `_codeguide/` at `<sibling_anchor>/<project_path.relative_to(git_toplevel)>/_codeguide/` — NOT at `<sibling_anchor>/_codeguide/` flat. When `mode == "inline"`, behavior is unchanged (place at `<project_path>/_codeguide/`). `resolve.py`'s `_sibling_walk` already walks this same structure: `anchor / rel / "_codeguide" / filename`.

Worked example to add:

```
Repo: c:/Code/acme/wts/acme/          (git toplevel)
  src/csharp/Api/                      (project A)
  src/csharp/Worker/                   (project B)

Sibling anchor: c:/Code/acme/codeguide/

Docs land at:
  c:/Code/acme/codeguide/src/csharp/Api/_codeguide/
  c:/Code/acme/codeguide/src/csharp/Worker/_codeguide/

NOT at:
  c:/Code/acme/codeguide/_codeguide/modules/  ← wrong flat structure
```

**codeguide-setup SKILL.md** (`plugins/codeguide/skills/codeguide-setup/SKILL.md`):

Current step 1 argument parsing:
```
- `--sibling` → sibling mode
- `--from-url <git-url>` → clone instead of git init
```

New step 1:
```
- `--sibling` or `--sibling <url>` → sibling mode; optional URL clones instead of git init
- `--branch <name>` → branch to use (requires URL in --sibling)
```

Current step 4 sibling-anchor creation:
```
If not exist: git init OR git clone <url> when --from-url given
```

New step 4:
```
If not exist:
  - No URL: git init <anchor>
  - URL, no --branch: git clone <url> <anchor>
  - URL + --branch: check via `git ls-remote --heads <url> <branch>`
      - exit 0 + non-empty stdout (branch exists): git clone -b <branch> --single-branch <url> <anchor>
      - exit 0 + empty stdout (branch absent): git init <anchor> + git remote add origin <url> + git checkout -b <branch>
      - non-zero exit (network/auth error): stop with error message, do not proceed
If already exists: proceed as before; ignore --branch
```

`_sibling.py` resolution is unchanged — sibling anchor path is computed from `(role="codeguide", git_toplevel)` regardless of how it was created.

## Testing

Both changes are SKILL.md prose — no executable code to test. Verification is manual/integration-level:

- **Task A — Step 1**: Verify `resolve.py --json` output is parsed and `mode`/`sibling_anchor`/`git_toplevel` are bound for use in later steps.
- **Task A — Step 9**: Run `/codeguide-generate` on a multi-project repo in sibling mode and confirm docs land at `<anchor>/<rel>/_codeguide/` not `<anchor>/_codeguide/modules/`. Inline mode regression: confirm docs still land at `<project>/_codeguide/`.
- **Task B — clone case**: Run `/codeguide-setup --sibling <url> --branch <existing-branch>` and verify `<anchor>` is cloned on the right branch.
- **Task B — orphan case**: Run `/codeguide-setup --sibling <url> --branch <new-branch>` and verify `<anchor>` is initialized with remote set and local branch checked out.
- **Task B — no URL + --branch**: Verify agent reports the error message.
- **Task B — existing anchor + --branch**: Verify anchor is used as-is without branch switching.
- **Task B — no --branch**: Verify clone of default branch (regression test for existing behavior).

## Q&A log

- **Q:** Where in codeguide-generate SKILL.md should the placement rule go? **A:** Inline in Step 9 (where docs are created); Step 1 updated in tandem to expose `mode`/`sibling_anchor`/`git_toplevel`.
- **Q:** Single or multi-project worked example? **A:** Multi-project — the mirroring is only non-obvious with multiple projects.
- **Q:** Keep `--from-url` or replace with `--sibling <url>`? **A:** Replace — `--sibling <url>` is cleaner, no backward-compat concern.
- **Q:** `--branch` without URL: error or ignore? **A:** Error with clear message.
- **Q:** `--branch` when anchor already exists: act or ignore? **A:** Ignore.
- **Q:** Push orphan branch at setup time? **A:** No — push on first commit.
