# Discussion: Migrate mill's generic skills to the shared scribe plugin

```yaml
task: Migrate mill's generic skills to the shared scribe plugin
slug: scribe-migration
status: discussing
parent_branch: main
```

## Problem

Millhouse side of GitHub issue #1170 (https://github.com/Knatte18/millhouse/issues/1170).
The shared plugin `scribe@scribe` (repo `Knatte18/scribe`, local clone `/home/knatte/Code/scribe`) already holds merged, repo-agnostic `prose`, `conversation`, `code-quality` (with `code-comments` folded in), `testing`, `golang-{build,comments,testing}` and `handoff`,
plus a SessionStart hook asking every session to load `scribe:conversation` and `scribe:prose`.
With mill and scribe both installed, every session sees two copies of the same conventions,
and which rule an agent follows depends on which copy it happens to load.
This session shows it live: the skill list offers both `mill:prose` and `scribe:prose`, and both `python:python-build` and the golang skills from two plugins.

The fix: delete mill's generic copies, keep only what is mill-specific in a thin mill layer on top of scribe, move the Python and C# language skills into scribe, drop millhouse's language plugins, and point every reference at scribe.

## Scope

**In:**

- Delete `plugins/mill/skills/{prose,conversation,code-quality,code-comments,testing,handoff}`.
- Create one new mill skill, `mill:conventions`, holding the mill-specific rules extracted from mill's `conversation` (see Decisions).
- Rewrite every `mill:{prose,conversation,code-quality,code-comments,testing,handoff}` reference to `scribe:<skill>` or `mill:conventions`.
- Rewrite the load-directive convention test to enforce the new load order and to forbid the old names.
- Qualify the skill names `_agent_dispatch.language_skills_directive` emits (`scribe:prose`, `scribe:code-quality`, `scribe:{lang}-comments`, `scribe:{lang}-testing`) and update the implementer agent definitions that name language skills.
- In the scribe repo: add `python-{build,comments,testing}` and `csharp-{build,comments,testing}` under `plugins/scribe/skills/`, made repo-agnostic; add them to `plugins/scribe/skills/INDEX.md`; bump scribe to `1.1.0`; commit and push.
- Remove `plugins/{golang,csharp,python}` and their entries in `.claude-plugin/marketplace.json`.
- Declare `scribe@scribe` as a plugin dependency of `mill` in the manifest.
- `update-plugins.sh` and `update-plugins.ps1`: refresh an installed `scribe@scribe` to the latest published version, warn when it is still below the version mill's `dependencies` requires, and print an uninstall hint for installed `<name>@millhouse` plugins that are no longer in `marketplace.json`.
- Regenerate `SKILLS.md`; update CLAUDE.md, `doc/turn-reduction-audit.md`, `.claude/skills/mill-pool/SKILL.md`, script docstrings.

**Out:**

- Editing scribe's existing skills (`prose`, `conversation`, `code-quality`, `testing`, `golang-*`, `handoff`).
  Generic rules found missing from scribe go to "Follow-ups for scribe" below, not into this task.
- loomyard's removal of its own `plugins/scribe` (the loomyard orchestrator does it).
- Reopening the three drift conflicts named in #1170; scribe's initial commit settled them.
- `mill-config.yaml` and its template: exploration found no `csharp:`/`python:`/`golang:` skill references there, so neither file changes.
- `codeguide` and `weblens` plugins: no references to the deleted skills.
- Running `./update-plugins.sh` itself during the task: it is an operator action after merge (see post-merge-sequence).
  Making the script refresh scribe is in scope.

## Decisions

### mill-layer-shape

- Decision: one new skill `plugins/mill/skills/conventions/SKILL.md`, invoked as `mill:conventions`.
  Frontmatter `name: conventions`, description along the lines of "Mill-specific operating rules — new-thread prompts, task-state and scratch locations, sed reach into dispatched agents, worktree isolation. Builds on `scribe:prose` and `scribe:conversation`."
  The body opens by stating it builds on `scribe:prose` and `scribe:conversation`, which must be loaded first, and restates nothing they already say.
- Rationale: the mill-specific rules all come from mill's `conversation` and apply to the same sessions at the same moment, so one skill loaded right after `scribe:conversation` keeps the load site to one line.
  A distinct name makes `grep mill:conversation` a reliable zero-hit guard; reusing the name would keep "which copy did it load" ambiguous, which is the problem being fixed.
- Rejected: keeping the name `mill:conversation` (ambiguity above); folding the rules into `workflow`, `cli` and `git-workflow` (worktree isolation and new-thread prompts fit none of them, and orchestrator Step 0 sites would have to load three skills to get them).

### mill-layer-content

Diffed each deleted mill skill against its scribe counterpart.
Only `conversation` has mill-specific content; `prose`, `code-quality`, `code-comments`, `testing` and `handoff` differ from scribe only in wording or in the settled drift points, so they are dropped outright.

`mill:conventions` carries exactly these sections, taken from `plugins/mill/skills/conversation/SKILL.md` and adjusted as noted:

- **Prompts for new threads** — verbatim from mill's `conversation` (`.scratch/prompt.md` / `.scratch/prompt-<slug>.md`, "Read .scratch/prompt.md and follow the instructions there.", overwrite-don't-diff, every prompt instructs the thread to write `.scratch/result-<slug>.md` and output only path + summary).
- **Task-state and scratch locations** — mill's text is stale (says task-state lives in the wiki).
  Rewrite to match CLAUDE.md: per-task working state (`status.md`, `discussion.md`, `plan/`, `reviews/`, `briefs/`) lives in `_mill/` on the task branch; the wiki holds only `Home.md` and daemon-rendered files; scripts resolve the wiki through `_paths.resolve_wiki_path`, never the `.wiki` junction.
  Keep the plugin-managed scratch note (shared `.scratch/`, subdirectories such as `test-review-<type>-<id>/`, `plans/`, `briefs/` created as needed) and that `.scratch/` is gitignored via `**/.scratch/`.
  Drop mill's "never write to /tmp" — scribe's File writing rule covers it.
  Keep mill's scratch-location rule as a mill-specific override, reworded: in a mill worktree `.scratch/` means the worktree root's `.scratch/`, because mill's scripts, fixtures and new-thread prompts (`.scratch/prompt.md`) resolve it from the worktree root.
  This intentionally narrows scribe's "`.scratch/` under the current working directory" for mill sessions; state it as such in the skill.
- **sed reach** — scribe already says the no-`sed` rule carries into forked and sub-agent sessions.
  The mill-specific addition: the rule also binds every prompt, brief, or script a mill orchestrator generates for a dispatched implementer, reviewer, or fixer (from CLAUDE.md's "Never use `sed`" bullet).
  State only that addition, not the rule itself.
- **Worktree isolation** — verbatim section from mill's `conversation`, including the `mill-merge`/`mill-cleanup` exemption and the 2026-04-13 incident rationale.
- **Skill authors** — mill's "any skill that prompts the user presents options as a numbered text list; when touching an existing mill skill that uses prose prompts, convert them."
  scribe covers the first half ("A skill that prompts the user presents its options the same way"); keep only the retroactive-conversion clause, scoped to mill skills.

Everything else in mill's `conversation` (response style, tone, user choices, file writing basics, sed basics) is covered by `scribe:conversation` and is dropped.

- Rejected: moving any of the above into scribe — each is tied to mill's layout (`_mill/`, `.scratch/` subdirs, wiki, worktree container) or mill's dispatch model.

### load-order

- Decision: every orchestrator Step-0 load directive becomes, verbatim modulo surrounding prose: "Load `scribe:prose`, then `scribe:conversation`, then `mill:conventions`."
  Sites: `plugins/mill/skills/mill-start/SKILL.md` (Entry Step 0), `plugins/mill/skills/mill-plan/SKILL.md` (Entry Step 0), `plugins/mill/skills/mill-go-base/SKILL.md` (Step 0b), `.claude/skills/mill-pool/SKILL.md` (Step 0).
  Each site's follow-on sentence ("`mill:conversation` builds on `mill:prose`, so load it first" / the defensive-load explanation / mill-start's numbered-options justification) is rewritten to name the scribe skills and to say `mill:conventions` builds on both.
- `plugins/mill/skills/mill-go2/SKILL.md` line 16 preloads `mill:code-quality` and `mill:prose` for forks → `scribe:code-quality` and `scribe:prose`.
- Rationale: scribe's SessionStart hook only asks to load scribe skills; a skill that writes its own agent instructions must still name what it needs (scribe's `INDEX.md` says so).
- Rejected: relying on the SessionStart hook alone — it cannot force-load, and dispatched workers may not honour it.

### referential-rewrites

Mentions without a load verb:

- "per `mill:conversation`'s numbered-options rule" and similar (`mill-start` lines ~25 and ~407, `mill-setup` ~259, `mill-merge` ~55, `mill-self-report` ~75, `ask-thread` ~48, `_inplace.py` ~70, `mill-pool` ~104) → `scribe:conversation`.
- `mill-pool` ~85 "worktree isolation (see its CLAUDE.md and the mill:conversation ...)" → `mill:conventions`.
- `tools/mdreflow/mdreflow.py` docstring: line 1 "mill:prose skill's semantic-line-break rule" → `scribe:prose`, and lines 4-5 "per plugins/mill/skills/prose/SKILL.md's "Line breaks" section" → "per the `scribe:prose` skill's Line breaks section" (no path; the file no longer exists in this repo).
- `tools/pydocreflow/pydocreflow.py` docstring points at `plugins/python/skills/python-comments/SKILL.md` → "the `scribe:python-comments` skill's line-wrap rule" (no path; the file leaves this repo).
- `plugins/mill/skills/workflow/SKILL.md` Skill Invocation Table: `@mill:code-quality` → `@scribe:code-quality`; `@mill:testing` → `@scribe:testing` (+ `scribe:{lang}-testing`); `@mill:prose` → `@scribe:prose`; `@mill:conversation` → `@scribe:conversation`; add a row "For mill-specific operating rules (new-thread prompts, `_mill/` state, worktree isolation) | `@mill:conventions`"; the "language-specific" row → `@scribe:{lang}-*`.
  Language Detection table → `@scribe:python-build`, `scribe:python-comments`, `scribe:python-testing` and the C#/Go equivalents.
- `doc/turn-reduction-audit.md`: rewrite the `mill:prose`/`mill:conversation` mentions to the new three-skill load (the doc describes current SKILL.md Step 0 content, so it must track it).
- CLAUDE.md: `csharp-build` → `scribe:csharp-build`, `python-build` → `scribe:python-build` in the two Conventions bullets.
- `plugins/mill/skills/mill-plan/SKILL.md` ~262 "`csharp-build` defines no lint command" → `scribe:csharp-build`.
- `plugins/mill/skills/git-commit/SKILL.md` "`{lang}-build` skill" → `scribe:{lang}-build`.
- Deleted `mill:handoff`: no caller references it by qualified name; users invoke `/handoff`, now served by `scribe:handoff`.

### load-directive-test

- Decision: rewrite `plugins/mill/unit_tests/test-load-directive-convention.py` to guard the new convention:
  1. A line is a load directive when it names `scribe:conversation` or `mill:conventions` and carries a load verb (same `_LOAD_VERB_RE`).
  2. A file with a directive naming `scribe:conversation` must contain the canonical phrase "load `scribe:prose`[,] then `scribe:conversation`".
     A file with a directive naming `mill:conventions` must contain the canonical three-skill phrase "load `scribe:prose`, then `scribe:conversation`, then `mill:conventions`".
  3. New regression guard: no shipped file (every `*.md` under `plugins/` and `.claude/skills/` — not only `SKILL.md`, so companion files such as `mill-go-base/holistic-review.md` are covered — plus `*.py` under `plugins/mill/scripts/`, `*.md` under `doc/`, and `CLAUDE.md`) names `mill:prose`, `mill:conversation`, `mill:code-quality`, `mill:code-comments`, `mill:testing` or `mill:handoff`.
     The same guard also forbids the path forms `plugins/mill/skills/(prose|conversation|code-quality|code-comments|testing|handoff)/` and `plugins/(python|csharp|golang)/`, so a stale file-path citation (like `mdreflow.py`'s) is caught, not only `mill:<name>`.
     `_mill/` is excluded (task working state), and the test file excludes itself.
- Keep the existing in-memory `check_text` cases, re-expressed with scribe names, plus cases for the three-skill phrase and the forbidden-name guard; keep the tree-walk case.
- Rationale: brief requires the test enforce the new order; the forbidden-name guard makes the migration's completeness mechanically checked instead of grep-once.

### implementer-skill-directive

- Decision: `plugins/mill/scripts/_agent_dispatch.py` `language_skills_directive` emits fully qualified names: base list `` `scribe:prose` ``, `` `scribe:code-quality` ``; per detected language `` `scribe:{prefix}-comments` ``, `` `scribe:{prefix}-testing` ``.
  `LANG_MAP` prefixes stay `golang`/`python`/`csharp`.
  Docstring updated to match.
- `plugins/mill/agents/mill-implementer*.md` (all six): the "for Python files load `python-comments` and `python-testing`; for C# files load `csharp-comments` and `csharp-testing`" lines → `scribe:` qualified; check the same files for any Go line or bare `prose`/`code-quality` and qualify those too.
- Update `plugins/mill/unit_tests/test-language-skills-directive.py` assertions to the qualified names.
- Rationale: with the language plugins gone, a bare `python-comments` resolves to nothing specific; qualified names are unambiguous while stale caches still carry `mill:prose`.
- Rejected: leaving bare names (ambiguous with two plugins during cache transition).

### scribe-language-skills

- Decision: copy `plugins/python/skills/python-{build,comments,testing}/SKILL.md` and `plugins/csharp/skills/csharp-{build,comments,testing}/SKILL.md` to `/home/knatte/Code/scribe/plugins/scribe/skills/<same-name>/SKILL.md`, keeping frontmatter `name`, then make them repo-agnostic:
  - `python-comments` / `csharp-comments` line 8 "Load the `code-comments` skill first." → "Load `scribe:code-quality` first — its Comments section is the language-agnostic base."
  - `python-comments` ~48 pointer to "`code-comments` skill's 'many comments needed' corollary" → `scribe:code-quality`'s Comments section ("Restraint first").
  - Where a `*-comments` skill restates a generic comment rule that `scribe:code-quality` states differently (notably the file-header rule, which scribe settled as "skip when the file is the only one in its directory"), drop the restatement and keep only the language mechanics (placement, syntax, tooling), mirroring how scribe's `golang-comments` builds on `code-quality`.
  - `python-testing` ~14 / `csharp-testing` ~15 "See `@code:testing`" → "See `scribe:testing`".
  - `csharp-build` ~23 "A long mill-orchestrated ..." and ~29 "(mill-go verify, git-commit lint, any pass/fail check)" → orchestrator-neutral wording ("a long orchestrated session", "(a verify step, a pre-commit lint, any pass/fail check)").
  - `python-build` import-ordering example (~lines 51-54: `from solgt.timeseries import convert_date_to_t`, `import utils_config`) and ~71 "(e.g., `utils_config.py`)" are from a specific project → genericise to neutral names (e.g. `from mypackage.timeseries import to_period_index`, `import project_config`, "(e.g., `project_config.py`)"), keeping the ordering rule the example illustrates.
  - Final check, two parts: `grep -nE "mill|millhouse|_mill|plugins/|@code:|solgt|utils_config"` over the six new files returns nothing;
    and a read-through of each file for any other identifier naming a specific repo, package, or path (the grep cannot know every project name).
- Add six rows to `plugins/scribe/skills/INDEX.md`, grouped like the golang rows, using each skill's frontmatter description.
- Version bump `1.0.0` → `1.1.0` in `plugins/scribe/.claude-plugin/plugin.json` and in the `scribe` entry of `/home/knatte/Code/scribe/.claude-plugin/marketplace.json` (both the marketplace-level `version` and the plugin entry); extend both `description` strings to mention Python and C# mechanics.
- Tag the release: after the version-bump commit, `git -C /home/knatte/Code/scribe tag v1.1.0` and push the tag with the branch (`git -C /home/knatte/Code/scribe push --follow-tags`, or push the tag explicitly).
  Tag regardless of what the docs say about range resolution; it is cheap and makes `^1.1.0` resolvable if Claude Code resolves ranges against tags.
  If the docs name a different tag format for dependency resolution, use that format.
- Commit in the scribe repo with `git -C /home/knatte/Code/scribe add ... && git -C /home/knatte/Code/scribe commit -m "..."`, then `git -C /home/knatte/Code/scribe push`. Never `cd`.
- Ordering: the scribe change is its own first batch and must be pushed before millhouse's language plugins are deleted, so there is never a published state where the skills exist nowhere.
- Rationale: brief mandates it; scribe's `golang-*` are the precedent.

### remove-language-plugins

- Decision: `git rm -r plugins/golang plugins/csharp plugins/python`; delete the `python`, `csharp`, `golang` entries from `.claude-plugin/marketplace.json`.
  Update the `mill` entry's description (both in `marketplace.json` and `plugins/mill/.claude-plugin/plugin.json`) to drop "code quality" (now scribe's).
- `update-plugins.sh` and `update-plugins.ps1` already derive the plugin list from `marketplace.json`, so no list edit.
  Add one step to each: after the sync loop, read `~/.claude/plugins/installed_plugins.json`, and for every installed `<name>@<marketplace>` whose marketplace equals ours but whose name is not in `marketplace.json`, print `Orphaned: <name>@<marketplace> is no longer in this marketplace -- run 'claude plugin uninstall <name>@<marketplace>'.`
  Print only; don't uninstall.
- Rationale: removing the entries does not uninstall `python@millhouse`/`golang@millhouse` from existing machines (this machine has both installed and enabled), so without the hint the duplicate-conventions problem survives on every machine that had them.
- Rejected: auto-running `claude plugin uninstall` from the script (mutates user plugin state from a sync script; the hint is enough); doing nothing (leaves duplicates).

### scribe-refresh

- Problem: scribe is installed from its GitHub marketplace, and `~/.claude/plugins/installed_plugins.json` pins `scribe@scribe` at `1.0.0` (cache `~/.claude/plugins/cache/scribe/scribe/1.0.0`, commit `5e5179f`).
  `update-plugins.{sh,ps1}` only rsync millhouse's own `plugins/<name>` into the millhouse cache, and mill reaches its cache through that rsync rather than an install/update, so the manifest `dependencies` entry never triggers a scribe update.
  Without a refresh step, after merge the implementer directive and agent files name `scribe:python-*` / `scribe:csharp-*`, which the installed 1.0.0 lacks; once `python@millhouse` is uninstalled, Python/C# conventions exist nowhere on that machine.
- Decision: add a scribe step to both `update-plugins.sh` and `update-plugins.ps1`, run before the millhouse sync loop:
  1. If `scribe@scribe` is in `installed_plugins.json`, run `claude plugin marketplace update scribe`, then `claude plugin update scribe@scribe`.
     A failing command prints a `WARNING:` line and the script continues (same tolerance as the existing `uv sync` step).
  2. Re-read `installed_plugins.json` and compare the installed scribe version against the minimum in mill's `plugins/mill/.claude-plugin/plugin.json` `dependencies` entry (read from the manifest, never a second hard-coded copy).
     Derive the minimum from the range by stripping a leading operator (`^`, `~`, `>=`, `=`) and parsing the remainder as a dotted integer tuple; compare tuples.
     When the dependency entry carries no version (the bare `"scribe@scribe"` fallback), skip the comparison; step 1 and step 3 still run.
     Below the minimum → print `WARNING: scribe@scribe is <v>, mill needs <min> -- run 'claude plugin marketplace update scribe' and 'claude plugin update scribe@scribe'.`
  3. If `scribe@scribe` is not installed at all → print the two install commands (`/plugin marketplace add Knatte18/scribe`, `/plugin install scribe@scribe`).
  The plan confirms the exact `claude plugin marketplace update` / `claude plugin update` CLI syntax (`claude plugin --help`) before writing it.
  All printed text ASCII.
- Rejected: leaving the scribe refresh to the operator's memory (the gap the review found); a separate `update-scribe.sh` (the operator already runs `update-plugins.sh` after every plugin change).

### post-merge-sequence

The one-time operator sequence after this task merges, stated in the merge summary (not in a permanent doc).
CLAUDE.md's existing `./update-plugins.sh` bullet gains one clause: the script also refreshes `scribe@scribe`.

1. Run `./update-plugins.sh` (or `.ps1`) from the hub root — it refreshes scribe to ≥ `1.1.0` first, then syncs mill.
2. Uninstall the orphans it lists (`claude plugin uninstall python@millhouse`, `golang@millhouse`, `csharp@millhouse` where installed).
3. Restart Claude Code sessions so they load the new skill set.

### scribe-dependency

- Decision: declare the dependency in the mill manifest instead of a mill-setup check.
  Claude Code supports `dependencies` in `plugin.json`, including cross-marketplace ones (https://code.claude.com/docs/en/plugins/dependencies.md#depend-on-a-plugin-from-another-marketplace):
  - `plugins/mill/.claude-plugin/plugin.json`: add `"dependencies": [{"name": "scribe", "marketplace": "scribe", "version": "^1.1.0"}]` — `1.1.0` is the first scribe version carrying the Python/C# skills mill's implementer directive names.
  - `.claude-plugin/marketplace.json` (millhouse): add top-level `"allowCrossMarketplaceDependenciesOn": ["scribe"]` — without it Claude Code does not install a cross-marketplace dependency.
  - Plan must first fetch the docs page and confirm the exact object-form field names and the version-range syntax; if the object form or `version` key differs, use the documented form (bare `"scribe@scribe"` is the fallback when version ranges are not supported for cross-marketplace deps).
  - From the same docs, the plan also confirms what happens when a mill install cannot resolve the dependency (the `scribe` marketplace not added on that machine): hard install failure or warning.
    Either way the dependency stays — mill does not work without scribe's skills — but the `mill-setup` precondition text must describe the actual behaviour: on hard failure, "add the scribe marketplace before installing mill"; on warning, "mill installs, but its skills reference `scribe:*`; add and install scribe".
    The same wording goes into the `update-plugins` not-installed message (scribe-refresh step 3).
- `mill-setup`: no runtime check (brief: "use that if it exists, the check otherwise").
  Add one Preconditions bullet to `plugins/mill/skills/mill-setup/SKILL.md`: "`scribe@scribe` is installed and enabled (mill declares it as a dependency; if the `scribe` marketplace is not yet added: `/plugin marketplace add Knatte18/scribe`, then `/plugin install scribe@scribe`)."
- Rationale: the manifest mechanism installs/enables scribe at mill install time; a hand-rolled check duplicates it.
- Rejected: a `_claude_settings` helper that reads `enabledPlugins` / `installed_plugins.json` (redundant once the dependency exists).

### indexes

- Regenerate `SKILLS.md` with `millpy-skills-index.py` after the deletions and the new `conventions` skill; it scans `plugins/*/skills/`, so removed plugins and deleted mill skills drop out and `conventions` appears.
- scribe's `INDEX.md` is covered under scribe-language-skills.
- There is no mill-level skill `INDEX.md`; the removed plugins' `INDEX.md` files go with their directories.

## Technical context

- Mill skills live in `plugins/mill/skills/<name>/SKILL.md`; `SKILLS.md` at repo root is generated by `plugins/mill/scripts/millpy-skills-index.py` (run via the `mill-skills-index` skill).
- Reference census (from `grep -rnE "mill:(prose|conversation|code-quality|code-comments|testing|handoff)"`, excluding `_mill/`): `.claude/skills/mill-pool/SKILL.md`, `doc/turn-reduction-audit.md`, `plugins/mill/scripts/_inplace.py`, `plugins/mill/scripts/tools/mdreflow/mdreflow.py`, and SKILL.md files `ask-thread`, `handoff` (deleted), `mill-go2`, `mill-go-base`, `mill-merge`, `mill-plan`, `mill-self-report`, `mill-setup`, `mill-start`, `workflow`, plus the load-directive test. Re-run the grep during implementation rather than trusting this list.
- Language-skill references: `grep -rnE "(csharp|python|golang):|(csharp|python|golang)-(build|comments|testing)|code-comments"` outside the removed plugin directories — hits in `workflow/SKILL.md`, `mill-go2/SKILL.md`, `mill-plan/SKILL.md`, `git-commit/SKILL.md`, `agents/mill-implementer*.md`, `_agent_dispatch.py`, `test-language-skills-directive.py`, `pydocreflow.py`, `SKILLS.md`, CLAUDE.md.
- Path references to the removed plugin dirs: `SKILLS.md` (regenerated), `pydocreflow.py`, `.claude-plugin/marketplace.json`.
- `update-plugins.sh` derives `(name, version)` pairs from `.claude-plugin/marketplace.json` via an inline `python3 -c`; `update-plugins.ps1` is its Windows twin — edit both identically in behaviour.
- `~/.claude/plugins/installed_plugins.json` has a top-level `plugins` object keyed `name@marketplace`.
- scribe repo layout: `/home/knatte/Code/scribe/.claude-plugin/marketplace.json`, `/home/knatte/Code/scribe/plugins/scribe/.claude-plugin/plugin.json`, `/home/knatte/Code/scribe/plugins/scribe/skills/<name>/SKILL.md`, `/home/knatte/Code/scribe/plugins/scribe/skills/INDEX.md`, `hooks/hooks.json`.
  Clean working tree, single commit `5e5179f`.
- scribe's `code-quality` merges mill's `code-quality` and `code-comments`; its Comments section is the target for every "load code-comments first" pointer.
- Sessions on the old cache keep loading `mill:prose` until `./update-plugins.sh` runs — expected, not a bug.
- Self-hosting caveat (CLAUDE.md): verify source against the worktree, never `${CLAUDE_PLUGIN_ROOT}`; the cache still has the old skills.

## Constraints

- Never `sed`, in any Bash call or generated script/prompt.
- Operate on the scribe repo only with `git -C /home/knatte/Code/scribe ...`; never `cd`.
- Semantic line breaks in all new/edited markdown (`scribe:prose`).
- Python `print()` output ASCII only (the `update-plugins` orphan hint included).
- No `_mill/` path cited from any permanent doc.

## Testing

- `test-load-directive-convention.py` — TDD candidate: write the new `check_text` cases (scribe two-skill phrase, three-skill phrase, forbidden `mill:<generic>` names, referential mention passes) first; they fail against the current tree, pass after the rewrites. Tree-walk case covers every shipped file.
- `test-language-skills-directive.py` — update expectations to `scribe:`-qualified names; cover Go-only, Python-only, C#-only, mixed, no-language batches (existing scenarios).
- `test-skills-index.py` — confirm it does not depend on the removed plugin dirs; adjust fixtures if it does.
- Full unit suite via `run-all.py` (`PYTHONPATH= uv run --project plugins/mill ...`).
- Manifest validity: `python3 -c "import json; json.load(open(...))"` over both marketplace files and both `plugin.json` files; `claude plugin validate` if available.
- `update-plugins.{sh,ps1}`: no unit test (they shell out to `claude` and rsync into the real cache).
  Keep the new version-comparison and orphan-detection logic in the inline Python the scripts already use; verify with `bash -n update-plugins.sh` and a side-by-side reading that both scripts behave identically.
- scribe repo: grep check from scribe-language-skills returns no hits; `INDEX.md` lists every directory under `plugins/scribe/skills/`.
- Final repo-wide grep for `mill:(prose|conversation|code-quality|code-comments|testing|handoff)` and `(python|csharp|golang):` returns only intended hits (none outside `_mill/`).

## Follow-ups for scribe

Generic rules in mill's deleted skills that scribe lacks — not done here:

- mill `code-quality` "File management": "Before creating a markdown or documentation file, confirm with the user." scribe's `code-quality` has no equivalent.

## Q&A log

- **Q:** Name and shape of the mill layer? **A:** [auto-pick] One new skill `mill:conventions`. **Why:** single load site after `scribe:conversation`; a distinct name makes the old name greppable to zero.
- **Q:** Which deleted skills contribute mill-specific content? **A:** [auto-pick] Only `conversation`; the rest are dropped. **Why:** the diffs show wording-only or settled-drift differences.
- **Q:** Plugin dependency mechanism or mill-setup check? **A:** [auto-pick] Manifest `dependencies` with `allowCrossMarketplaceDependenciesOn`. **Why:** Claude Code documents cross-marketplace dependencies; the brief says to use it when it exists.
- **Q:** How to handle `python@millhouse`/`golang@millhouse` left installed on existing machines? **A:** [auto-pick] `update-plugins` scripts print an uninstall hint for orphaned installs. **Why:** removing marketplace entries does not uninstall them, and the duplicates are the problem being fixed.
- **Q:** How does the installed scribe reach 1.1.0 after merge? **A:** [auto-pick] `update-plugins.{sh,ps1}` run `claude plugin marketplace update scribe` + `claude plugin update scribe@scribe`, then warn if still below mill's declared minimum. **Why:** the rsync path never resolves manifest dependencies; the operator already runs this script after every plugin change.
- **Q:** Bare or qualified skill names in the implementer directive? **A:** [auto-pick] Qualified `scribe:<skill>`. **Why:** unambiguous while old caches coexist.
- **Q:** Should the load-directive test also forbid the old names? **A:** [auto-pick] Yes, a forbidden-name guard over shipped files. **Why:** makes migration completeness mechanically checked.
