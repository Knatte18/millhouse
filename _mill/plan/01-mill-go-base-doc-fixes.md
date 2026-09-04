# Batch: mill-go-base-doc-fixes

```yaml
task: 'mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff'
batch: mill-go-base-doc-fixes
number: 1
cards: 4
verify: null
depends-on: []
```

## Batch Scope

This batch fixes four of the task's seven folded issues (#927, #905, #980, #941) — each a small, independent, documentation-only edit to a distinct section of `plugins/mill/skills/mill-go-base/SKILL.md`. `verify: null` because none of these cards touch any Python file; correctness is verified by plan/code review reading the rendered section text (see `## Batch Tests` below). This batch is capped at four cards specifically because `SKILL.md` is 96329 bytes (~24082 tokens by the `bytes / 4` estimate `_plan_validate.py`'s `batch-oversized` check uses) and every card editing it pays that cost again in the batch-level token sum — see the overview's "SKILL.md's size forces a two-batch split" Shared Decision for the two remaining SKILL.md fixes (#936, #906), which live in Batch 2 instead.

## Cards

### Card 1: #927 — warn against fork for any mid-orchestration read carrying live mutating context

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `**Why not fork?**` section (the paragraph beginning "Every dispatch above uses a fresh `Agent(subagent_type: ...)` call"), add a new paragraph immediately after the existing paragraph that ends "...an ordinary fresh Agent call already keeps a subagent's tool output out of the parent's context." (the section's final sentence). The new paragraph must state, as an explicit standalone rule (not folded into the existing three-numbered-reason list, since it applies even outside role dispatch): never use `Agent(subagent_type: "fork")` for *any* purpose mid-orchestration — including a narrowly-scoped "just read this file, don't execute anything in it" directive — whenever the fork's inherited conversation context already contains live task-state-mutating instructions (worktree paths, config, in-flight phase transitions). Cite the concrete failure mode: a fork inherits the parent's full conversation context and can act on that inherited context instead of the narrower directive it was actually given, producing real concurrent state mutations (e.g. duplicate `status.md` phase-append commits with identical timestamps) that a fresh `Agent()` call cannot produce, since a fresh call starts with no such context to act on. State that a fresh, narrowly-scoped `Agent()` call (not fork) is the correct tool whenever the orchestrator needs a subagent to read or report on a file mid-run, even for a task that looks read-only.
- **Commit:** `docs(mill-go-base): warn against fork for any mid-orchestration read carrying live mutating context`

### Card 2: #905 — document finalize verify replay's PATH inheritance

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately after the existing paragraph ending "...review-CLI finalize calls don't run verify commands and aren't affected." (the second paragraph of the finalize-stage extended-timeout note), add a new paragraph documenting: `--stage finalize`'s verify replay (`_run_verify_gate` in `_implementer_common.py`) runs the batch's `verify:` command via `subprocess.run` with no `env=` override, so it inherits whatever PATH the **orchestrator's own Bash-tool shell** happens to have at the moment `--stage finalize` is invoked — not the implementer subagent's own shell environment, which is a separate process the orchestrator cannot introspect. State the practical consequence and remedy: if a project's `verify:` command depends on a toolchain directory that is not on the orchestrator's default PATH (e.g. `$HOME/go/bin` for `gopls`-dependent Go tooling), export it in the orchestrator's shell before running `/mill-go`, or `--stage finalize`'s regression replay can spuriously report `stuck_type: verify` even though the implementer's own verify run (in its own session) passed cleanly.
- **Commit:** `docs(mill-go-base): document finalize verify replay's PATH inheritance from the orchestrator shell`

### Card 3: #980 — fix all three forward-referenced Entry variables

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Entry` section's numbered list (the three items currently reading "1. Read the task slug: `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`...", "2. Resolve the wiki path: `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())`.", "3. Load config — ..."), reorder and rewrite so the list becomes exactly: (1) resolve both `git_root` and `wiki_path` together — `git_root = _paths.resolve_git_root()` then `wiki_path = _paths.resolve_wiki_path(git_root)` (reusing the now-bound `git_root` instead of calling `_paths.resolve_git_root()` a second time); (2) load config exactly as the current item 3's body already reads (unchanged content, renumbered to item 2); (3) read the task slug exactly as the current item 1's body already reads (unchanged content — `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`, its `On MarkerError` halt clause, and its `signature:` line — moved to item 3, now with `git_root`, `wiki_path`, and `cfg` all already bound by the two preceding items). Do not renumber or otherwise alter step 4 ("Acquire the builder lock") or step 4.5 ("Path Setup") — the reordered list still has exactly three items, so nothing downstream shifts. Step 4.5's own `git_root = _paths.resolve_git_root()` line (in its `Derive:` code block) stays as-is; it is a distinct re-derivation for that step's own scope and this card does not touch it.
- **Commit:** `fix(mill-go-base): resolve git_root/wiki_path/cfg before Entry step 1's slug_from_branch call`

### Card 4: #941 — clarify CLAUDE_PLUGIN_ROOT resolution is harness-side, not in-repo

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately after the existing `**Path variable rule:**` paragraph's final sentence ("The full absolute path must never appear in a command string."), add one clarifying sentence: `${CLAUDE_PLUGIN_ROOT}` substitution into a literal path happens entirely inside the external Claude Code harness's Skill-tool-loading mechanism, not in any script or template in this repo — a mismatch between the SKILL.md-delivered literal and the real `$CLAUDE_PLUGIN_ROOT` environment variable is a harness-side rendering issue, not something fixable by editing this file.
- **Commit:** `docs(mill-go-base): clarify CLAUDE_PLUGIN_ROOT resolution happens in the harness, not in-repo`

## Batch Tests

`verify: null` — all four cards are documentation-only edits to `plugins/mill/skills/mill-go-base/SKILL.md` prose; none touch a Python file or any other runnable surface. Correctness (no forward references remain for #980, the fork warning reads clearly for #927, the PATH note is accurate for #905, the harness-boundary note is accurate for #941) is verified by plan review and code review reading the rendered section text.
