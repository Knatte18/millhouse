# Discussion: 49 (A) — Defensive guards mot cwd-inni-wiki kjedereaksjoner

```yaml
task: 49 (A) — Defensive guards mot cwd-inni-wiki kjedereaksjoner
slug: fix-wiki-cwd-cascade
status: discussing
parent: main
```

## Problem

On 2026-05-11 the `discussion-review-gap-batching` thread invoked `millpy-bg --slug review-discussion-r1 -- ... millpy-review-discussion.py` with a cwd inside the wiki repo. The chain reaction was: `git rev-parse --show-toplevel` returned `c:\Code\millhouse\wiki`, `millpy-bg` wrote its scratch log to `wiki/.scratch/bg-20260511-103712-review-discussion-r1.log`, the spawned review process inherited that cwd, `_paths.resolve_git_root()` returned the wiki root, `_sibling.resolve_path("wiki", wiki_root)` produced the nonsense path `wiki.wiki` (prefix-form bug applied to wiki itself), `load_config` failed with `Missing config at C:\Code\millhouse\wiki.wiki\config.yaml`, and at the next `mill-wiki-push` the orphan bg-log was committed and pushed to wiki origin (commit `2abb004`) because `wiki/.gitignore` has no `.scratch/` entry.

A full audit on 2026-05-11 confirmed that no production code sets cwd to wiki — every wiki mutation goes through `git -C <wiki_path>` inside `_wiki.write_commit_push`. The actual source was operator-reported: an LLM thread improvised `cd .wiki && git pull --ff-only` instead of calling `_wiki.sync_pull(wiki_path)`. The codebase is clean; the thread instructions were not strict enough about staying out of the wiki cwd.

**Why now:** the orphan log already reached wiki origin. A second similar failure could write much worse content to wiki. The fix locks down `_paths.resolve_git_root` so scripts halt fast and loud the moment a stray operator or LLM `cd` puts cwd inside wiki, instead of silently producing garbage paths that pollute the shared wiki repo.

## Scope

**In:**

- `git rm` the orphan `wiki/.scratch/bg-20260511-103712-review-discussion-r1.log` and push via the wiki-lock helper.
- Defensive guard in `_paths.resolve_git_root()` that halts when cwd resolves inside the wiki clone.
- Defensive guard in `_sibling.resolve_path()` that halts when `repo_root.name == "wiki"`.
- Mirror the `_sibling.resolve_path` guard to the identical-twin copy at `plugins/codeguide/scripts/_sibling.py`.
- Defensive guard in `_paths.resolve_wiki_path()` matching the same `git_toplevel.name == "wiki"` rule.
- New CLAUDE.md `## Path invariants` bullet: "cwd is always cwd; scripts never rewrite it; halt on wiki-cwd."
- New CLAUDE.md `## Wiki access` subsection with anti-pattern → correct-replacement table.
- One-line "Wiki access: never `cd .wiki/`. Use the documented helpers." note at the top of each of: `mill-start`, `mill-plan`, `mill-go`, `mill-merge`, `mill-wiki-push`, `mill-setup`, `mill-claim`, `mill-spawn` SKILL.md files.
- New unit test `plugins/mill/unit_tests/test-no-wiki-cwd.py` that walks `plugins/mill/scripts/`, `plugins/mill/skills/`, `plugins/codeguide/scripts/`, `plugins/codeguide/skills/` and fails on any future occurrence of the documented anti-patterns.

**Out:**

- Adding `.scratch/` to `wiki/.gitignore`. The proposal is explicit: this would hide the symptom. Once guard (b) lands the bg log can never reach wiki.
- Changing `millpy-bg`'s cwd contract. It must continue to trust cwd; the guard lives upstream in `_paths.resolve_git_root`.
- Preventing operator-shell `cd .wiki/`. Navigating the wiki in a shell is a valid operator action; only scripted operations are constrained.
- Auditing or modifying `_wiki.write_commit_push` — its `git -C <wiki_path>` pattern is the correct contract and stays unchanged.
- Adding a runtime "auto-correct" that walks up to a non-wiki cwd. The guard halts; it does not silently recover.

## Decisions

### guard-placement

- Decision: Place the primary guard inside `_paths.resolve_git_root()`. Every script that touches paths goes through this function; one guard protects them all.
- Rationale: Maximum coverage with minimal per-script churn. The guard is invisible until it fires.
- Rejected: A separate opt-in `_paths.guard_not_in_wiki()` helper (would require every entry-point to remember to call it); per-script inline checks (12+ duplicate sites).

### guard-detection

- Decision: Belt-and-suspenders detection — `repo_root.name == "wiki"` (fast, config-free path) AND path equality with `_paths.resolve_wiki_path(...)` when resolvable (catches non-standard wiki dir names). Either match halts.
- Rationale: The name check is the common case and works even when the wiki path cannot be resolved (e.g. config absent). The equality check survives a future rename of the wiki dir. Combining both costs nothing and removes a class of edge cases.
- Rejected: Name-only (fragile to rename); equality-only (depends on config which may not be resolvable inside a borked cwd).

### guard-error-type

- Decision: Raise `SystemExit` with a user-facing message: `"cwd is inside wiki ({wiki_path}) — scripts must run from a task worktree or the main repo, not the wiki. Wiki mutations go through git -C <wiki_path> or _wiki.write_commit_push."`
- Rationale: Matches the existing `resolve_git_root` style (already raises `SystemExit`). User sees a clean halt message, not a stack trace.
- Rejected: `RuntimeError` (inconsistent with file's existing style despite proposal text using it); custom `WikiCwdError(SystemExit)` subclass (adds vocabulary for one call site).

### sibling-guard

- Decision: `_sibling.resolve_path()` raises `ValueError("resolve_path called from wiki repo — wiki cannot resolve its own wiki path")` when `repo_root.name == "wiki"`. The same change is applied byte-for-byte to `plugins/codeguide/scripts/_sibling.py` per the identical-twin rule in that file's docstring.
- Rationale: Defence in depth. Even if a future helper calls `_sibling.resolve_path` without going through `_paths.resolve_git_root`, the wiki cannot produce the nonsense `wiki.wiki` path. `ValueError` is appropriate because the input is malformed, not a runtime environment issue.
- Rejected: `SystemExit` (callable parity is less important than input-validation semantics); skipping the codeguide twin (violates the identical-twin invariant documented in the file itself).

### wiki-path-guard

- Decision: `_paths.resolve_wiki_path(git_toplevel)` halts with the same `SystemExit` message as `resolve_git_root` when `git_toplevel.name == "wiki"`. The check runs at the top of the function before any config reading. The full belt-and-suspenders (name check **plus** path equality) lives in `resolve_git_root`, which calls `resolve_wiki_path` externally and can then compare its own `git_root` against the returned wiki path.
- Rationale: Inside `resolve_wiki_path` the path-equality check would be circular — `resolve_wiki_path` is the function that resolves the wiki path. So the in-function defence is the name check only. `resolve_git_root` owns the equality check because that's the call site where both `git_root` and a resolved wiki path are available without recursion. Splitting the responsibility this way is still belt-and-suspenders: any path into config loading goes through one of the two guards. Test code and future callers that bypass `resolve_git_root` still get the name check inside `resolve_wiki_path`.
- Rejected: Doing the path-equality check inside `resolve_wiki_path` (circular and incoherent); trusting upstream guards only (leaves test code and future callers exposed when they call `resolve_wiki_path` directly).

### claude-md-placement

- Decision: New bullet at the bottom of the existing `## Path invariants` section: "**cwd is always cwd, and scripts never rewrite it.** Wiki mutations go through `git -C <wiki_path>` (or `_wiki.write_commit_push`) — never by changing cwd to wiki. If a script detects cwd is inside wiki, it halts with a clear error: that is operator error, not something to recover from."
- Rationale: Keeps related path rules co-located. Operators already scan `## Path invariants` for path-related contracts.
- Rejected: New `## CWD invariants` section (fragments the invariant set); inline in `## Conventions worth carrying` (this is harder than a convention — it is a hard rule).

### wiki-access-section

- Decision: New `## Wiki access` subsection in CLAUDE.md, placed immediately after `## Path invariants`. Content: short prose intro ("Scripts mutate the wiki only through `_wiki.write_commit_push` or `git -C <wiki_path>`. Reads only through helper APIs and `read_text(wiki_path / …)`.") followed by an anti-pattern table with the four rows from the proposal:

  | Anti-pattern | Correct replacement |
  |---|---|
  | `cd .wiki/ && git pull --ff-only` | `_wiki.sync_pull(wiki_path)` |
  | `cd .wiki/ && git <anything>` | `git -C <wiki_path> <anything>` |
  | `cd .wiki/ && cat <file>` | `read_text(wiki_path / "<file>")` |
  | `cwd=<wiki_path>` in subprocess | `cwd=<task_worktree>` + `git -C <wiki_path>` |

- Rationale: Tables surface anti-patterns at-a-glance for both LLM threads and humans. The four rows cover every observed misuse and the two plausible-future misuses.
- Rejected: Inline paragraph (less scannable); additional rows beyond the proposal (YAGNI — add when a new anti-pattern is observed).

### per-skill-notes

- Decision: Add a single-line note "Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`." at the top of each of: `mill-start/SKILL.md`, `mill-plan/SKILL.md`, `mill-go/SKILL.md`, `mill-merge/SKILL.md`, `mill-wiki-push/SKILL.md`, `mill-setup/SKILL.md`, `mill-claim/SKILL.md`, `mill-spawn/SKILL.md`. Placed alongside other in-skill invariant notes if present, otherwise as a leading note immediately under the H1.
- Rationale: SKILL.md files are loaded individually by Claude Code without sibling context — a thread running `mill-spawn` does not necessarily have CLAUDE.md fresh in mind. Re-stating the rule per skill catches the LLM where the anti-pattern would be improvised.
- Rejected: CLAUDE.md only (proven insufficient — the original incident happened with CLAUDE.md in context); all SKILLs that touch git (over-broad; only wiki-touching SKILLs need it).

### language

- Decision: English for all CLAUDE.md and SKILL.md additions, including the anti-pattern table and error strings.
- Rationale: The surrounding CLAUDE.md and every SKILL.md are English. The proposal happens to be Norwegian but the codebase prose is uniformly English. Error strings stay grep-able when uniform.
- Rejected: Norwegian (matches proposal source but breaks codebase uniformity).

### test-design

- Decision: New `plugins/mill/unit_tests/test-no-wiki-cwd.py`. Walks `plugins/mill/scripts/`, `plugins/mill/skills/`, `plugins/codeguide/scripts/`, `plugins/codeguide/skills/`. Reads every file ending in `.py`, `.md`, or `.sh`. Compiles four regexes matching the proposal patterns (`cd \.wiki\b`, `cd <wiki[^>]*>`, `os\.chdir\(.*wiki`, `cwd=.*wiki`) plus `cd .*\bwiki/` (catches `cd ../wiki/`). Fails with one line per match listing file + line number. No allowlist — the codebase has no legitimate match today and any future match is a regression.
- Rationale: Replicates the proposal's intent. Patterns are conservative (literal anti-patterns the operator can articulate). Walking both plugins respects the identical-twin rule symmetry. No allowlist keeps the test enforceable; adding one would degenerate into a permission table that fails open.
- Rejected: Bolting onto `test-paths.py` (mixes concerns); broader heuristics like `Path(...).chdir()` (false-positive risk on shared-string accidents); allowlist (turns the test into a permission database).

### cleanup-strategy

- Decision: Plain `git rm` + commit + push via `_wiki.write_commit_push` to remove the orphan `wiki/.scratch/bg-20260511-103712-review-discussion-r1.log`. History preserved.
- Rationale: The log is harmless content (review-thread stdout). Force-rewriting wiki history breaks every operator's local clone and adds risk without value. Removing the file going forward is sufficient.
- Rejected: Force-rewrite history (disruptive, no upside since file content is non-sensitive).

## Technical context

Relevant files for the implementation plan:

- `plugins/mill/scripts/_paths.py` — `resolve_git_root` (lines 106–111), `resolve_wiki_path` (lines 363–409). The new guard at the top of `resolve_git_root` runs the wiki-path lookup defensively wrapped: if `resolve_wiki_path` itself raises (config missing, etc.) fall back to the `name == "wiki"` check alone. The guard inside `resolve_wiki_path` runs before any config IO.
- `plugins/mill/scripts/_sibling.py` — `resolve_path` (lines 57–65). Add the `repo_root.name == "wiki"` check at the very top of the function, before the `parent.name == "wts"` branch.
- `plugins/codeguide/scripts/_sibling.py` — byte-for-byte copy. Apply the same change. Verify with `diff plugins/mill/scripts/_sibling.py plugins/codeguide/scripts/_sibling.py` — only the existing per-plugin docstring rows should differ after the fix.
- `plugins/mill/scripts/_wiki.py` — provides `sync_pull(wiki_path, *, slug)` and `write_commit_push(wiki_path, paths, msg, slug=...)` plus the `wiki_lock` context manager. These are the only correct mutation paths into wiki; reaffirm them in the new CLAUDE.md `## Wiki access` section.
- `CLAUDE.md` (lines 109–119) — existing `## Path invariants` section. Add the new bullet at the bottom, then insert a new `## Wiki access` section immediately after.
- `plugins/mill/skills/{mill-start,mill-plan,mill-go,mill-merge,mill-wiki-push,mill-setup,mill-claim,mill-spawn}/SKILL.md` — add the one-line note.
- `plugins/mill/unit_tests/run-all.py` — auto-discovers `test-*.py` files in the directory; the new test will be picked up automatically.
- `wiki/.scratch/bg-20260511-103712-review-discussion-r1.log` — the orphan file. Already in wiki repo at commit `2abb004`.

Gotchas:

- `_paths.resolve_git_root` is called from many test files via the helpers. The guard runs only when the resolved root is the wiki — none of the unit tests use wiki-cwd as a fixture, so the guard does not break any existing test. Verify with a dry-run of `python plugins/mill/unit_tests/run-all.py` before declaring the batch done.
- The defensive `resolve_wiki_path` guard depends on `git_toplevel` being already resolved (not the raw cwd). Callers that do `resolve_wiki_path(Path.cwd())` (none today, but plausible) would not trigger the guard via `name == "wiki"` alone if cwd is a subdir of wiki — the path-equality fallback covers that. Use `git_toplevel.resolve().samefile(wiki_path)` style comparison only after `wiki_path.exists()`; otherwise fall back to name check. Keep both — they compose without conflict.
- The codeguide `_sibling.py` twin's docstring carries plugin-specific examples (`codeguide` instead of `wiki`). The new guard text should be plugin-agnostic — say "wiki" in the error message (the role being requested is what matters, not which plugin's copy of the file is running).
- The unit test must use raw regex matches via `re.search` per line, not `re.match`. Skip the test file itself to avoid self-match on the regex source. Documentation files that legitimately quote the anti-pattern — `CLAUDE.md` (root) and the eight SKILL.md notes — are exempted via an explicit in-test allowlist of those file paths. Use the regex set from the `test-design` Decision unchanged; everything outside the allowlist is denied.
- The wiki repo lives outside the worktree at `<container>/wiki/`. The cleanup commit (`git rm`) runs against the wiki repo via `_wiki.write_commit_push`. Do not run it from inside the task worktree's `git` context — use the helper.

## Constraints

- `CONSTRAINTS.md` at the hub root: none discovered for this task (no file present).
- Identical-twin rule (`plugins/codeguide/scripts/_sibling.py` mirrors mill's): any change to mill's `_sibling.py` must be applied to codeguide's copy. Documented in both files' module docstrings.
- Junctions-as-IDE-convenience invariant (CLAUDE.md `## Path invariants`): scripts never resolve via `.wiki` junction; they always go through `_paths.resolve_wiki_path`. The new guards reinforce — they do not contradict — this invariant.
- `${CLAUDE_PLUGIN_ROOT}` invariant: no new hardcoded `plugins/mill/...` paths in SKILL.md or scripts. The unit test walks plugin source trees (mill + codeguide), but it lives under `plugins/mill/unit_tests/` which is the documented exception for runner-invoked tests.
- Working-state-in-task-branch invariant: discussion.md, plan, reviews stay in `task/`. The fix touches scripts, CLAUDE.md, SKILL.md, one unit test, and one wiki file — none of these go into `task/`.

## Testing

The fix is small (three guards, one cleanup commit, doc edits, one unit test). One implementer batch + one holistic review round is appropriate. TDD candidates and key scenarios:

- **`test-no-wiki-cwd.py`** (new). TDD candidate. Tests it walks both plugins, finds zero matches in the current tree (precondition for the fix landing), and synthesises a temp file with each of the four anti-patterns and asserts it flags every one. Use `tempfile.TemporaryDirectory` plus a small helper that re-points the walker root.
- **`test-paths.py`** (existing). Add cases:
  - `resolve_git_root` when cwd is the wiki root → `SystemExit` with the documented message. Patch `_subprocess_util.run` to return the wiki path; patch `resolve_wiki_path` to return that same path.
  - `resolve_git_root` when cwd is a subdirectory of wiki → same `SystemExit` (samefile comparison covers this).
  - `resolve_git_root` when wiki path cannot be resolved (config raises) but cwd's `name == "wiki"` → `SystemExit` via fast-path.
  - `resolve_wiki_path` when `git_toplevel.name == "wiki"` → `SystemExit`.
  - `resolve_wiki_path` when `git_toplevel` equals the resolved wiki path → `SystemExit`.
- **`test-sibling.py`** (existing). Add cases:
  - `resolve_path("wiki", Path("/c/Code/wiki"))` → `ValueError` with the documented message.
  - `resolve_path("plan", Path("/c/Code/wiki"))` → same `ValueError` (the role does not matter; the source repo being wiki does).
  - `resolve_path("wiki", Path("/c/Code/wts/millhouse"))` → returns the existing container-form result unchanged (regression guard).
- Manual smoke: from a fresh PowerShell, `cd c:\Code\millhouse\wiki`, then `uv run --project "$env:CLAUDE_PLUGIN_ROOT" "$env:CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" --slug demo -- echo hi` → must halt with the documented message before creating any file. Same with `millpy-review-discussion.py`. Run before merging.
- Integration: not added. The fail-fast guard is testable at the unit level; an integration run would only confirm the same SystemExit path.

## Q&A log

- **Q:** Should the bg-log cleanup rewrite wiki history? **A:** [auto-pick] Regular `git rm` + commit + push — history preserved. **Why:** log content is non-sensitive; rewriting wiki history disrupts every operator clone for no upside.
- **Q:** Where does the wiki-cwd guard live? **A:** [auto-pick] Inside `_paths.resolve_git_root()`. **Why:** one guard protects every caller without opt-in churn.
- **Q:** How does the guard detect "inside wiki"? **A:** [auto-pick] Both — `repo_root.name == "wiki"` fast path AND path-equality with the resolved wiki path. **Why:** name check works without config; equality survives renames. Combined cost is negligible.
- **Q:** Error type for the guard? **A:** [auto-pick] `SystemExit`. **Why:** matches existing `resolve_git_root` raise style; user sees a clean halt.
- **Q:** Mirror guard (c) to codeguide twin? **A:** [auto-pick] Yes — byte-for-byte. **Why:** identical-twin rule is documented in both files' docstrings.
- **Q:** `_sibling.resolve_path` error type? **A:** [auto-pick] `ValueError("resolve_path called from wiki repo — wiki cannot resolve its own wiki path")`. **Why:** input validation; matches proposal phrasing.
- **Q:** Defensive guard inside `_paths.resolve_wiki_path` too? **A:** [auto-pick] Yes. **Why:** belt-and-suspenders; not every caller routes through `resolve_git_root` (test code, future helpers).
- **Q:** CLAUDE.md placement for the new rule? **A:** [auto-pick] New bullet inside existing `## Path invariants`. **Why:** related rules stay co-located; operators scan that section for path contracts.
- **Q:** Language for new CLAUDE.md content? **A:** [auto-pick] English. **Why:** matches surrounding prose and keeps error strings grep-uniform.
- **Q:** Which SKILLs get a per-skill wiki-access note? **A:** [auto-pick] The eight from the proposal: mill-start, mill-plan, mill-go, mill-merge, mill-wiki-push, mill-setup, mill-claim, mill-spawn. **Why:** scoped to skills that actually touch wiki; covers every documented mutator and reader path.
- **Q:** Test file location? **A:** [auto-pick] New `plugins/mill/unit_tests/test-no-wiki-cwd.py`. **Why:** one purpose per test file matches existing layout; auto-discovered by `run-all.py`.
- **Q:** Test patterns? **A:** [auto-pick] Literal four patterns per proposal. **Why:** conservative; matches articulated anti-patterns; low false-positive risk.
- **Q:** Test scope? **A:** [auto-pick] mill + codeguide scripts/ + skills/. **Why:** identical-twin rule applies symmetrically; the codeguide copy is just as exposed.
- **Q:** Anti-pattern table rows? **A:** [auto-pick] Four rows from the proposal verbatim. **Why:** covers every observed and one plausible-future misuse; broader rows risk YAGNI.
- **Q:** Allowlist for legitimately-cwd-in-wiki contexts? **A:** [auto-pick] No allowlist for code; tiny allowlist (CLAUDE.md + the eight SKILL.md notes) for documentation files that quote the anti-pattern. **Why:** code has no legitimate match today; documentation files must mention the anti-pattern to teach against it.
- **Q:** Error-string language? **A:** [auto-pick] English. **Why:** matches the surrounding code and stays parseable.
