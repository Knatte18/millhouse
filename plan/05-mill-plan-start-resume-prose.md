# Batch: mill-plan-start-resume-prose

```yaml
task: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel
batch: mill-plan-start-resume-prose
cards: 3
verify: null
depends-on: [wiki-lock-unification]
```

## Batch Scope

Three small prose batches that fix the `wiki.sync_pull()` pseudocall (#15 / #55) across mill-plan, mill-start, and mill-resume SKILL.md files, plus mill-plan's obsolete `wiki/active/<slug>/plan/` path in step 1.5 (#102). Depends on B01 because the new `_wiki.sync_pull(wiki_path, *, slug)` signature lands there. No code changes; pure SKILL.md edits.

mill-start SKILL.md is also touched by B01 (Card 5, Board discipline lock-API prose); B05 depends-on B01 so the two card sets land sequentially against the same file. The prose changes do not overlap line-wise: B01 rewrites Board discipline (~line 105); B05 rewrites Entry step 1 (~line 12). The implementer simply applies B05's edit on top of the post-B01 file content.

## Cards

### Card 21: Rewrite mill-plan SKILL.md Entry step 1 + step 1.5

- **Reads:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
- **Modifies:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Requirements:** Replace `1. wiki.sync_pull() on the wiki clone.` with the concrete invocation: `1. Resolve the wiki path via _paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd())) and call _wiki.sync_pull(wiki_path, slug="mill-plan").` Add the canonical signature line: `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None`. In step 1.5 (validator-fix commit, around line 93), replace `mill-plan commits the fix(es) to plan files via _wiki.write_commit_push(wiki_path, [f"active/{slug}/plan/"], f"mill-plan: validator-fix pass for {slug}")` with `mill-plan commits the fix(es) on the task branch: git -C <worktree> add plan/ && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"` (no push; matches the rest of mill-plan's task-branch commit pattern). The commit message keyword `validator-fix` is preserved to distinguish from `plan-fix-r{N}` LLM-fix-pass commits. Sweep the rest of the file for any other surviving `_wiki.write_commit_push` reference for plan/ or status.md (none expected from prior cleanups, but verify) and convert any found to the same task-branch pattern.
- **Commit:** `docs(mill-plan): replace pseudocall + obsolete wiki/active path`

### Card 22: Rewrite mill-start SKILL.md Entry step 1

- **Reads:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
- **Modifies:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Requirements:** Replace `1. wiki.sync_pull() on the wiki clone.` (~line 12) with: `1. Resolve the wiki path via _paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd())) and call _wiki.sync_pull(wiki_path, slug="mill-start").` Add the signature line: `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None`. Do NOT touch the Board discipline section (Card 5 in B01 owns those edits). Verify the file's other references to wiki state are unaffected.
- **Commit:** `docs(mill-start): replace pseudocall on Entry step 1`

### Card 23: Rewrite mill-resume SKILL.md sync invariant + entry sync

- **Reads:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
- **Modifies:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
- **Creates:** none
- **Requirements:** Find every reference to `wiki.sync_pull(cfg)` (or any pseudocall variant) in `mill-resume/SKILL.md` — currently lines 14, 39, 176 per the proposal sweep. Replace each with the concrete invocation: `_wiki.sync_pull(wiki_path, slug="mill-resume")` where `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd()))`. Add the signature line `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None` immediately after the first reference (typically the Sync invariant section). The third reference at line 176 is in a failure-mode table and may need rewording (e.g. "`_wiki.sync_pull` raises `WikiPushError`" instead of the pseudocall). Do not change semantic behaviour — sync_pull is still mandatory on entry; only the call shape changes.
- **Commit:** `docs(mill-resume): replace pseudocall sweep`

## Batch Tests

No `verify:` command — pure SKILL.md prose. Behavioural verification happens the next time a Builder runs `/mill-plan`, `/mill-start`, or `/mill-resume` and follows Entry step 1 verbatim without falling into the `cd .millhouse/wiki && git pull` antipattern that #55 documented.
