# Discussion: 37 (A) — Codeguide bug-fix batch 1

```yaml
task: 37 (A) — Codeguide bug-fix batch 1
slug: codeguide-fixes-1
status: discussing
parent: main
```

## Problem

Two codeguide-domain bugs surfaced in the 2026-05-09 GitHub-issue triage. Both are footguns that bite when codeguide is used in real workflows on external repos:

- **#203** — On a repo that uses sibling-mode codeguide (the codeguide files live in a parallel repo, not inline), the agent has no obvious way to find the codeguide root. The resolver script (`${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py`) does exist and every `codeguide-*` SKILL.md does reference it, but the reference is buried mid-list (Step 1 in three skills, Step 3 in `codeguide-setup`). When the agent enters one of these skills it tends to start grepping the source tree first instead of running the resolver. On inline-mode repos this accidentally works; on sibling-mode repos there is nothing to grep for and the skill walks away.

- **#210** — `/codeguide-update` no-arg invocation defaults to "files in the current git diff (staged + unstaged)". That default is correct for the in-`git-commit` case (where it runs as part of staging). It is wrong for the post-commit / pre-PR case mill-go produces: the per-card commit pipeline lands every change as its own commit, so by the time the user runs `/codeguide-update` at end-of-task to refresh docs before opening a PR, the working tree is clean and the diff is empty. Source files were updated and committed several commits ago; the skill sees nothing in scope and silently does nothing.

Why now: both bugs were reported against real external repos using mill+codeguide as plugins, on the same triage round (2026-05-08 / 2026-05-09). They block the "mill task → PR" pipeline for any repo that uses sibling-mode codeguide or expects end-of-task doc updates.

## Scope

**In:**

- Add a prominent "Resolution" callout at the top of every `codeguide-*` SKILL.md (`codeguide-generate`, `codeguide-update`, `codeguide-maintain`, `codeguide-setup`) that names `resolve.py` as the very first step before any other work. The existing buried Step 1 (or Step 3 in `codeguide-setup`) is replaced or simplified to point at the callout — duplication between the callout and the per-step instructions must be removed.
- Update `plugins/mill/skills/git-commit/SKILL.md`'s "Codeguide sync" step to detect codeguide via `resolve.py --json`'s `found` field instead of the current hardcoded "look for `_codeguide/Overview.md` or sibling repo at `<container>/<repo>.codeguide/`" prose.
- Add a new helper script `plugins/codeguide/scripts/resolve_scope.py` that, given the `$ARGUMENTS` string, prints a deduped, newline-separated list of source-file paths that are in scope. The helper encapsulates parent-branch detection and the union of `<parent>..HEAD` with the current diff.
- Update `codeguide-update` SKILL.md to call `resolve_scope.py` as the new Step 1 (file enumeration), feeding its output into the existing per-file `resolve.py` grouping.
- Unit tests for `resolve_scope.py` only — synthetic git fixtures via `tempfile`+`git init`, hand-built commit graphs covering the documented cases.

**Out:**

- The "missing-doc flagging" follow-up the proposal mentions (flagging source files that have no doc) — that depends on this fix and is a separate task once we have empirical data on the gaps.
- Any change to `codeguide-generate`, `codeguide-maintain`, or `codeguide-setup` beyond the callout edit at the top of each. Their internal logic is unchanged.
- A "context preamble" mechanism that pre-resolves codeguide and injects the result before any skill runs. SKILL.md files are static templates, no templating layer exists, and adding one is out of scope for a bug-fix batch.
- Reading `task/status.md` or `.millhouse/config.yaml` from inside the codeguide plugin to find the parent branch. Codeguide must stay independent of mill.
- `_codeguide/` doc generation, structure, or content rules. This task only changes which files are picked up; what gets done with them is unchanged.
- Any change to `codeguide-update`'s commit/staging behavior (`codeguide_commit.py --mode {inline,sibling}`). Mode detection still flows through per-file `resolve.py`.
- Behavior on `main` / `master` (or whatever `origin/HEAD` resolves to) is unchanged: no-arg = current diff only. Widening only kicks in on a non-base branch.

## Decisions

### resolve-callout-shape

- **Decision:** Each `codeguide-*` SKILL.md grows a fenced callout block titled `## Resolution` immediately after the YAML frontmatter and the one-paragraph description, before any `## Steps`/`## Modes`/`## Scope` heading. The callout is two lines: a one-sentence directive ("Before doing anything else, run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json`") and the JSON shape it returns (`{mode, cg_root, sibling_anchor, found}`). Where the existing Step 1 already says the same thing, that step is replaced with a one-line back-reference (`See ## Resolution above.`) so the callout is the single source of truth.
- **Rationale:** SKILL.md files are concatenated as instructions; what comes earlier carries more weight. Promoting the resolver to a top-of-file callout — and removing the duplicate buried-step instruction — makes it the first concrete action the agent sees and removes the divergence risk between two copies of the same instruction. This matches the issue text's first-listed fix ("skills should all start by stating…") and avoids the "pre-resolve and inject into prompt context" alternative which would need a templating mechanism that does not exist.
- **Rejected:** (a) Editing only the `description:` frontmatter — too subtle, agents don't always reread descriptions before acting. (b) Building a context-preamble mechanism that runs `resolve.py` automatically before the skill body — needs Claude Code infrastructure changes outside this plugin. (c) A separate `codeguide-resolve` skill the agent is supposed to invoke first — adds an extra hop and is easy to skip.

### git-commit-uses-resolve

- **Decision:** `plugins/mill/skills/git-commit/SKILL.md`'s "Codeguide sync" step is rewritten to invoke `resolve.py --json` and branch on the `found` field. The existing inline-vs-sibling prose is replaced by: "If `found == false`, skip codeguide-update. Otherwise invoke `@codeguide:codeguide-update`, which will re-resolve per file and handle inline/sibling itself." No new logic in `git-commit` — the entire detection collapses into one resolver call.
- **Rationale:** The current prose hardcodes the layout convention (`<container>/<repo>.codeguide/` or `<container>/codeguide/`). Sibling anchor resolution lives in `_sibling.py` and is the single source of truth — git-commit shouldn't reimplement it. Routing the detection through `resolve.py` also means git-commit benefits automatically from any future resolver change (e.g. a new `.codeguide-root` override semantic).
- **Rejected:** Leaving git-commit untouched — would leave a second hardcoded codeguide-detection path in the codebase, which is a slow-burn version of #203.

### scope-helper-as-script

- **Decision:** Add `plugins/codeguide/scripts/resolve_scope.py`. CLI: `python resolve_scope.py [<args>]` where `<args>` is the same string `$ARGUMENTS` carries today (`""`, `1h`, `3d`, `HEAD~3`, or explicit paths). Output: one absolute path per line on stdout, plus a JSON-line summary on stderr (last line) with `{mode, parent, base_branch, included_committed: int, included_diff: int}` for traceability. Exit 0 on success (even when the result is empty). The helper is invoked by `codeguide-update`'s Step 1; SKILL.md no longer carries the "translate `$ARGUMENTS` into a list of files" responsibility.
- **Rationale:** Parent detection has multiple fallback steps (`origin/HEAD` → `main` → `master`) and the union logic with the current diff is non-trivial. Putting it in prose makes it easy for the agent to misread. A script can be unit-tested against synthetic git fixtures and the SKILL.md just calls it. This parallels how `resolve.py` already encapsulates path resolution.
- **Rejected:** (a) Writing the logic inline in SKILL.md as procedural git steps — fails Q5's testability and "single source of truth" properties. (b) Putting the logic in `codeguide_commit.py` — that script is about staging/committing, not enumeration; mixing concerns.

### git-native-parent-detection

- **Decision:** `resolve_scope.py`'s parent-branch detection is purely git-native: `git symbolic-ref --short refs/remotes/origin/HEAD` first; if that fails, probe `git rev-parse --verify origin/main`; if that fails, probe `git rev-parse --verify origin/master`; if that also fails, treat the current branch as base (no widening, today's behavior, with a stderr note). No reading of `task/status.md`, no reading of `.millhouse/config.yaml`. The user can always pass an explicit parent via the existing `$ARGUMENTS` (e.g. `develop..HEAD`).
- **Rationale:** The codeguide plugin is shipped to repos that have no mill clone. Reading mill-owned files would couple the plugins and break codeguide-only deployments. `origin/HEAD` is git-native and works on any GitHub-style repo. The `main`/`master` fallback covers repos where `origin/HEAD` is not set (it's not always present after a fresh clone). The "no widening when no base can be found" case is a graceful degradation — same as today.
- **Rejected:** (a) Reading `task/status.md` `parent:` row — couples codeguide to mill's file format. (b) Reading `.millhouse/config.yaml`'s `git.parent-branch` — same coupling, plus that key is mill-specific and not guaranteed to exist on a repo using only codeguide. (c) Asking the user interactively — `codeguide-update` is meant to be unattended-friendly inside `git-commit`'s pipeline.

### scope-union

- **Decision:** When on a non-base branch with no arg, scope = (files changed in `<parent>..HEAD`) ∪ (files in current diff, staged + unstaged). On a base branch with no arg, scope = (files in current diff). Explicit args (`1h`, `HEAD~3`, paths) are unchanged from today.
- **Rationale:** The post-commit case has a clean tree and committed work; the in-progress case has uncommitted edits; the "switching back to a task with both" case has both. Union covers all three with one rule and matches the proposal's option 1. Auto-widen-only-when-empty is harder to predict and surprises users with different behavior depending on whether they happened to save before invoking. Always-`<parent>..HEAD`-no-diff misses uncommitted edits.
- **Rejected:** (a) Auto-widen only when current diff is empty — unpredictable. (b) Always `<parent>..HEAD` only, no diff — misses uncommitted edits.

### base-branch-behavior-unchanged

- **Decision:** When on the resolved base branch (i.e. current branch == whatever `origin/HEAD`/`main`/`master` resolves to), `resolve_scope.py` returns today's behavior verbatim: files in the current diff (staged + unstaged), no widening. This includes the case where the user commits straight to main with `--onmain`.
- **Rationale:** On main, "recent commits" is unbounded and there is no obvious cutoff. The existing relative-time args (`1h`, `3d`) already cover the case where someone wants to look back. Defaulting to current-diff-only matches the in-`git-commit` flow that mill repos rely on.
- **Rejected:** Looking back N days/commits on main as a default — picks an arbitrary cutoff and changes behavior for an existing-and-working case.

### tests-helper-only

- **Decision:** Unit tests cover `resolve_scope.py` only. Synthetic git fixture: `tempfile.TemporaryDirectory()` + `git init` + scripted commits + scripted file edits. No tests for the SKILL.md callout edits — those are documentation. No integration test that drives `/codeguide-update` end-to-end.
- **Rationale:** SKILL.md edits are reviewed as docs (mill-review-plan + code review handle them). The non-trivial logic — parent detection and the union — is what needs coverage, and that's all in `resolve_scope.py`. Mirrors how `resolve.py` is tested today (helper-level unit tests, no per-skill integration tests).
- **Rejected:** Integration test that drives `codeguide-update` — too much fixture overhead (real `_codeguide/` tree, real source files) for marginal additional coverage when the only changing piece is the file-enumeration step.

## Technical context

**Codeguide plugin layout** ([plugins/codeguide/](plugins/codeguide/)):

- [scripts/resolve.py](plugins/codeguide/scripts/resolve.py) — existing path resolver. Resolve chain: inline walk → `.codeguide-root` override → sibling default via `_sibling.resolve_path` → sibling walk. Public API used by SKILL.md: `python resolve.py --json` prints `{mode, cg_root, sibling_anchor, found}`. Routing files (Overview.md, modules/) resolve from cwd; metadata files (config.yaml, local-rules.md) follow the chain. The new `resolve_scope.py` is a sibling helper, not a wrapper around this one — different responsibility (file-list enumeration vs path resolution).
- [scripts/_sibling.py](plugins/codeguide/scripts/_sibling.py) — sibling-anchor computation. Identical-twin with the mill copy.
- [scripts/codeguide_commit.py](plugins/codeguide/scripts/codeguide_commit.py) — stages (inline) or stages-and-commits (sibling) doc files. Caller passes `--mode` and (for sibling) `--sibling-anchor`. Untouched by this task.
- [skills/codeguide-update/SKILL.md](plugins/codeguide/skills/codeguide-update/SKILL.md) — current scope handling: agent translates `$ARGUMENTS` into a file list inline. Step 1 (per-file resolve via `resolve.py`) becomes Step 2 after this task; new Step 1 invokes `resolve_scope.py`.
- [skills/codeguide-generate/SKILL.md](plugins/codeguide/skills/codeguide-generate/SKILL.md), [skills/codeguide-maintain/SKILL.md](plugins/codeguide/skills/codeguide-maintain/SKILL.md), [skills/codeguide-setup/SKILL.md](plugins/codeguide/skills/codeguide-setup/SKILL.md) — get the same top-of-file Resolution callout. Existing Step 1 (`codeguide-setup`'s Step 3) collapses to a back-reference.

**Mill skill that needs editing** ([plugins/mill/skills/git-commit/SKILL.md](plugins/mill/skills/git-commit/SKILL.md)):

- The "Codeguide sync" step (lines 17–22 today) currently checks for inline-mode by looking for `_codeguide/Overview.md` and for sibling-mode by checking `<container>/<repo>.codeguide/` or `<container>/codeguide/`. Replace with a single `resolve.py --json` call.

**Existing patterns to mirror:**

- Resolver-script CLI shape: `python resolve.py --json` already prints a one-line JSON object. `resolve_scope.py` should follow the same convention — newline-separated paths on stdout, one-line JSON summary on stderr.
- Unit-test fixture pattern: `tempfile.TemporaryDirectory()` + scripted `git init`/commits is already used elsewhere in mill's `unit_tests/` (see `plugins/mill/unit_tests/`). codeguide doesn't currently have a `unit_tests/` folder; this task creates one.

**Gotchas:**

- `git symbolic-ref --short refs/remotes/origin/HEAD` returns `origin/main` (with the `origin/` prefix) — strip it before comparing to `git branch --show-current` output.
- `git diff --name-only` (unstaged) and `git diff --cached --name-only` (staged) both need to be called and unioned for the "current diff" half. There's no single `git diff` invocation that covers both.
- `git diff --name-only <parent>..HEAD` uses the merge-base; that's correct here. Don't use `<parent>...HEAD` (three dots) — that diffs against the merge-base from each side and would miss the case where the parent moved.
- Files deleted in the range are valid to include — the SKILL.md's existing "If source was deleted" branch handles them. Don't filter by file existence in `resolve_scope.py`.
- A clean-tree post-commit-only case must still emit deleted files from `<parent>..HEAD` so the SKILL's orphan-doc flagging triggers.
- `${CLAUDE_PLUGIN_ROOT}` may be empty in some Bash subshells (per CLAUDE.md). Don't add new dependencies on it inside `resolve_scope.py`'s body — the script resolves its own path with `__file__`.
- The existing per-file grouping (Step 2 in codeguide-update SKILL.md) needs each file's directory to call `resolve.py` from. `resolve_scope.py` returns absolute paths so the caller can do `Path(p).parent` without further resolution.

**Repo conventions to follow** (from CLAUDE.md):

- All new scripts under `plugins/codeguide/scripts/` follow the existing flat-Python pattern (no submodules; no `_*.py` smoke-test blocks).
- New tests under `plugins/codeguide/unit_tests/` (created by this task), one `test-<name>.py` per helper. Run via a yet-to-be-created `run-all.py`, or just `python -m unittest discover` if simpler — to be decided in the plan.

## Constraints

No `CONSTRAINTS.md` at the hub root.

Discovered constraints from the codebase:

- **Codeguide plugin must remain independent of mill.** Codeguide is shipped to repos that may have no mill clone. No imports from `plugins/mill/`, no reading of `task/status.md` or `.millhouse/config.yaml` from inside the codeguide plugin.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths in SKILL.md prose.** Hardcoded `plugins/codeguide/...` is banned in instructions executed on user machines.
- **SKILL.md edits preserve `description:` frontmatter** — the description is indexed by Claude Code's skill loader and changes there have side effects beyond this task.
- **No backwards-compat shims.** If the new callout makes a buried Step 1 redundant, delete the duplicate; do not leave it with a "kept for compat" comment.
- **No new dependencies.** `resolve_scope.py` uses only the stdlib (`subprocess`, `pathlib`, `argparse`, `sys`).

## Testing

**`resolve_scope.py` — unit tests** (TDD candidate, since the logic is pure git-graph reasoning):

Synthetic git fixture per test: `tempfile.TemporaryDirectory()` + `git init -b main` + scripted commits via `subprocess.run(['git', '-C', tmp, ...])`. No real network, no LLM, no real codeguide tree (the helper is purely about file enumeration; cg-root resolution happens later in the SKILL).

Scenarios that must be covered:

1. **No-arg, on base branch (`main`), clean tree** → empty output, exit 0, summary `parent: null`, `base_branch: main`.
2. **No-arg, on base branch, dirty tree** → output = files in current diff (staged + unstaged), no widening.
3. **No-arg, on task branch, clean tree (post-commit case — the bug)** → output = files in `main..HEAD`, summary `parent: main`.
4. **No-arg, on task branch, dirty tree** → output = union of `main..HEAD` ∪ current diff, deduped.
5. **No-arg, on task branch, `origin/HEAD` unset, fallback to `main`** → output uses `main` as parent.
6. **No-arg, on task branch, `origin/HEAD` unset, no `main`, has `master`** → output uses `master` as parent.
7. **No-arg, on task branch, no `origin/HEAD`, no `main`, no `master`** → empty output (graceful degradation), summary `parent: null`, stderr note about no base detected.
8. **Arg = `HEAD~3`** → today's behavior, no parent-detection involvement.
9. **Arg = `1h` / `3d` / `2w`** → today's behavior, time-based filter.
10. **Arg = explicit file paths** → today's behavior, paths echoed back.
11. **Files deleted in `parent..HEAD`** → still appear in output (SKILL.md handles orphan-doc flagging).
12. **Branch == base branch where base is `master` (no `main`)** → on-base behavior (current diff only, no widening).
13. **Files modified in both `parent..HEAD` and current diff** → appear once (dedup).

**SKILL.md edits — no tests.** They are documentation. Verified by mill-review-plan + code review.

**`git-commit` SKILL.md edit — no test.** Same reason; the only behavior change is which command produces the inline-vs-sibling decision, and the resulting decision is the same as today's hardcoded check on the standard layouts.

## Q&A log

- **Q:** Where does the agent actually fail on #203 — outside codeguide skills, inside them, or in `git-commit`'s detection? **A:** Inside `/codeguide-*` invocations (the buried Step 1 isn't prominent enough). Folded the `git-commit` hardcoded-detection cleanup into the same task because it's the same root cause.
- **Q:** Should we build a "context preamble" mechanism that pre-resolves codeguide before any skill runs? **A:** No — out of scope. SKILL.md files are static; templating doesn't exist. A prominent callout is enough.
- **Q:** Where does parent-branch detection live for #210 — read mill's `task/status.md`, `.millhouse/config.yaml`, or git-native? **A:** Pure git-native. Codeguide plugin must stay independent of mill.
- **Q:** Should the no-arg default on a task branch be `<parent>..HEAD`, current diff, or both? **A:** Both, unioned. Covers post-commit, in-progress, and mixed cases with one rule.
- **Q:** Where does the scope logic live — Python helper or SKILL.md prose? **A:** Helper script `resolve_scope.py`. Testable, single source of truth, parallels `resolve.py`.
- **Q:** Behavior on `main`/`master`? **A:** Unchanged — current diff only, no widening.
- **Q:** Tests for SKILL.md edits? **A:** No. SKILL.md edits are docs; only the helper script gets unit tests.
- **Q:** Missing-doc flagging in the same task? **A:** Out of scope per the proposal — separate follow-up after this fix lands.
