# Discussion: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability

```yaml
task: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability
slug: mill-start-and-baseline-tooling-gaps
status: discussing
parent: main
```

## Problem

Six independent reliability gaps were reported from live mill-go/mill-start runs (issues #618, #613, #615, #620, #622, #614). They share no architecture — each is a correctness or context-hygiene defect in a mill skill, a language plugin skill, or a mill script. Grouping them into one task is a convenience of scale, not a coupling. The concrete manifestations were observed across three repos (loomyard, NORCE Models, this repo), but every fix lands in **this** millhouse monorepo because it owns all of `plugins/mill`, `plugins/csharp`, and `plugins/golang`.

**Why now:** each gap silently degrades autonomous runs today. Two (#618 crash, #613 lost NOTEs) break the mill-start/mill-plan entry and review loops on literal reading; two (#615/#620) silently disable the module-wide verify baseline gate on any deep-path Windows repo; one (#622) burns ~15–20% of a Builder thread's context on chronic MSBuild noise; one (#614) risks unformatted Go imports slipping into commits when a tool is absent.

The six gaps and their exact fix sites (all verified during exploration):

| # | Gap | Fix site | Current state |
|---|-----|----------|---------------|
| #618 | Entry step 2 calls `slug_from_branch(..., cfg)` before step 3 loads `cfg` → `AttributeError` at `_marker.py:79` (`cfg.get("spawn", {})`) | `mill-start/SKILL.md:50-51`, `mill-plan/SKILL.md:17-18` | **Broken** — both still read slug before load |
| #613 | GAPS_FOUND branch (interactive step 5) enumerates only `[GAP]`; `[NOTE]`s in the same round can silently vanish | `mill-start/SKILL.md:213` | **Broken** — step 5 silent on NOTEs |
| #615 / #620 | `git worktree add` for the verify baseline fails "Filename too long" on deep-path Windows repos; baseline silently falls back to strict | `_verify_baseline.py:152-153` (`compute_baseline`) | **Broken** — no `core.longpaths` |
| #622 | Unfiltered `dotnet build`/`dotnet test` floods agent context with whole-solution warnings | `csharp-build/SKILL.md:16-19` | **Broken** — bare `dotnet build`/`dotnet test` |
| #614 | goimports step silently skipped when tool missing | `golang-build/SKILL.md:36-48`, `git-commit/SKILL.md:13-15` | **Largely satisfied** — golang-build already halts with actionable message; residual is git-commit wiring note |

## Scope

**In:**
- `plugins/mill/skills/mill-start/SKILL.md` — reorder Entry (config before slug); add `[NOTE]` handling to GAPS_FOUND step 5.
- `plugins/mill/skills/mill-plan/SKILL.md` — reorder Entry (config before slug).
- `plugins/mill/scripts/_verify_baseline.py` — add `-c core.longpaths=true` to the transient `git worktree add` **only**. The teardown is left unchanged: `_worktree.remove_safe` already falls back to `_safe_rmtree.safe_rmtree` when `git worktree remove` fails with "Filename too long" (`_worktree.py:237-261`), so long-path deletion is already covered; and `remove_safe` is a shared helper (cleanup/merge/spawn) whose blast radius does not justify an edit for this task.
- `plugins/mill/unit_tests/` — new test asserting the baseline `git worktree add` argv carries `-c core.longpaths=true`.
- `plugins/csharp/skills/csharp-build/SKILL.md` — make `--nologo -clp:ErrorsOnly` the default on `dotnet build`/`dotnet test`; add the exit-code-preservation rule (never pipe the gating invocation to `grep`) and the "never `tail`" rule.
- Root `CLAUDE.md` (the mill-v2 project conventions file, always in context at session start) — one-line backstop rule for ad-hoc dotnet invocations where the `csharp-build` skill isn't loaded. The `cli`/SKILL.md is deliberately **not** the target: it loads only when invoked, so it cannot backstop the skill-not-loaded case; `CLAUDE.md` is the single canonical edit site for this backstop.
- `plugins/golang/skills/golang-build/SKILL.md` — confirm the existing halt-on-missing-tool behavior stands (verification, likely no edit).
- `plugins/mill/skills/git-commit/SKILL.md` — one-line note in step 1 that the delegated `{lang}-build` tool-availability halt applies to the pre-commit lint step.

**Out:**
- No behavior change to `golang-build`'s halt semantics (rejected switching to warn-and-continue — see Decisions). No change to any other `{lang}-comments`/`{lang}-testing` skill except where noted.
- `csharp-testing/SKILL.md` is **not** touched: it holds test-authoring conventions only and shells no `dotnet` command; #622's title names it but the actual invocations live in `csharp-build`.
- `plugins/mill/scripts/_worktree.py` is **not** touched — the removal-side long-path case is already handled by `remove_safe`'s existing `safe_rmtree` fallback; editing a shared helper is out of scope.
- No change to the module-wide verify baseline's retry/control-check logic, its `.scratch/` anchoring, or the junction dependency-reuse mechanism — only the long-path flag on `git worktree add` is added.
- No re-anchoring of the temp verify worktree to system temp or a shorter path (rejected — see Decisions).
- No change to the wiki, task index, or any cross-repo external copy (loomyard/NORCE); those repos re-sync the plugin independently.

## Decisions

### plan-structure — batch by shared file

- Decision: One plan. Batch by shared file so disjoint gaps parallelize, but **#618 and #613 must share a batch** because both edit `mill-start/SKILL.md`. Suggested batching (mill-plan finalizes): (A) mill-start + mill-plan SKILL edits [#618 + #613]; (B) `_verify_baseline.py` + test [#615/#620]; (C) `csharp-build` + cli/CLAUDE backstop [#622]; (D) `golang-build` verify + `git-commit` note [#614].
- Rationale: The four batches touch disjoint file sets, so they can run in parallel; only the mill-start file forces a co-batch.
- Rejected: One-batch-per-issue (6 batches) — would put two writers on `mill-start/SKILL.md` concurrently, risking a merge conflict on the same file.

### 618-fix — reorder Entry, load config first

- Decision: In both `mill-start` and `mill-plan` Entry, move the config-load step ahead of the slug-read step, renumber, and audit the section for any "step 2"/"step 3" cross-references that must be updated. The `slug_from_branch(git_root, wiki_path, cfg)` signature is unchanged — `cfg` genuinely is a required arg (it reads `cfg.get("spawn", {})`). **The reorder must also make the slug call's other two inputs literal-execution-safe:** today Entry step 1 resolves the wiki path inline (`_paths.resolve_wiki_path(_paths.resolve_git_root())`) without binding `git_root` or `wiki_path` as named variables — those names are first assigned later in Path Setup. The reordered step 1 must therefore bind `git_root = _paths.resolve_git_root()` and `wiki_path = _paths.resolve_wiki_path(git_root)` (or the relevant Path Setup lines must be pulled above the slug read) so that step 2's `slug_from_branch(git_root, wiki_path, cfg)` references only already-bound names. mill-plan's Entry has the same inline-resolution shape and needs the same binding.
- Rationale: The call needs `cfg`; the ordering defect crashes on literal reading, and the unbound `git_root`/`wiki_path` names would be the next literal-execution failure after the cfg reorder. Reordering plus binding is the minimal, literal-reading-safe fix.
- Rejected: Keeping the order and adding a caveat — leaves a literal-execution trap that already crashed once live; a caveat is weaker than correct ordering.

### 613-fix — NOTE handling in GAPS_FOUND

- Decision: Extend interactive step 5 (the GAPS_FOUND branch) so that after enumerating `[GAP]` findings, any `[NOTE]` findings present in the same review round are applied via the `mill-receiving-review` fix-everything default, folded into the **same** `discussion-gap-fix` commit (no separate commit, no separate report — the review file is the audit trail). This mirrors the auto-mode rule already documented (every gap AND every NOTE treated as FIX) and the APPROVE-branch NOTE handling (4a/4b).
- Rationale: Without this, a NOTE arriving alongside gaps has no instruction and vanishes if the next round's reviewer doesn't repeat it (observed live, internal-burler). The workaround already used in the field is exactly this behavior; pin it.
- Rejected: Documenting that NOTEs "carry forward" — relies on the reviewer re-emitting them, which is the exact fragility being reported.

### 615-620-fix — core.longpaths on the transient worktree

- Decision: Pass `-c core.longpaths=true` to the `git worktree add` invocation in `_verify_baseline.compute_baseline` (line ~152-153) **only**, positioned before the `worktree` subcommand: `["git", "-C", str(git_root), "-c", "core.longpaths=true", "worktree", "add", str(tmp_path), parent_sha]`. Add a unit test asserting the flag is present in the captured argv in that position. **The teardown is deliberately left unchanged:** `_worktree.remove_safe` already shells `git worktree remove` (`_worktree.py:228`) and falls back to `_safe_rmtree.safe_rmtree` when that fails with "Filename too long" (`_worktree.py:237-261`), so long-path deletion is already handled; and `remove_safe` is a shared helper used by cleanup/merge/spawn, so threading a flag through it (or editing it in place) has a blast radius unjustified by this task.
- Rationale: `git worktree add` performs the checkout in-process, so `-c core.longpaths=true` governs that checkout and lets Git-for-Windows use its internal `\\?\` long-path handling. This is the exact fix the issue reporter proposed, is per-invocation (never mutates global/user config), and leaves every other part of the baseline mechanism — including teardown, which is already long-path-safe — untouched.
- Rejected: (a) Re-anchoring the temp worktree under system temp or a shorter root — violates the "`.scratch/` only, never system temp" convention and breaks the junction dependency-reuse, which junctions gitignored dep dirs **from `project_root`** into the temp checkout. A shorter path would also still be relative to `project_root`, which is itself already deep. (b) Adding the flag to the removal git call as well — redundant (the `safe_rmtree` fallback already covers it) and would require touching the shared `remove_safe` helper.

### 622-fix — filtered dotnet is the default

- Decision: In `csharp-build/SKILL.md`, change the Build Commands block to `dotnet build --nologo -clp:ErrorsOnly` and `dotnet test --nologo -clp:ErrorsOnly` — **both unpiped**. `-clp:ErrorsOnly` (a ConsoleLoggerParameters setting) suppresses the MSBuild **build-phase** warning noise (`CS8618`, `MSB3246`, `RZ10012`, etc.) while leaving VSTest's own result output — failing test names, `Error Message:` blocks, and the `Passed!`/`Failed!`/`Total tests` summary — fully intact, because VSTest failure reporting is not an MSBuild console-logger message. Add two explicit rules: (1) **the gating invocation must NOT be piped** — `cmd | grep` returns grep's exit status, not dotnet's, so a failing suite would exit 0 and silently pass mill-go verify / git-commit lint (the exact silent-failure class this task targets). The unpiped form preserves dotnet's authoritative exit code. If a human-readable summary-only view is ever wanted for display (never for gating), it must be guarded with `set -o pipefail` so the pipeline still reflects dotnet's exit code. (2) **Never `tail -N` a dotnet build/test** — warnings can evict the summary from the tail window, forcing a re-run. Add a one-line backstop to the root `CLAUDE.md` — the single canonical target, always in context at session start (unlike the `cli` skill, which loads only when invoked and so cannot backstop the skill-not-loaded case) — for ad-hoc invocations.
- Rationale: `csharp-build` is the chokepoint `workflow`'s language detection routes all dotnet through (`git-commit` lint, mill-go verify, ad-hoc), so centralizing there covers the whole pipeline. The observed waste was ~15–20% of a thread's context from re-dumped whole-solution warnings. The unpiped `-clp:ErrorsOnly` form drops that noise while keeping both the failure signal and the correct exit code — strictly better than the grep-to-summary form, which dropped per-test detail (`  Failed <TestName>` / `Error Message:` lines have no `!`) and masked the exit code.
- Rejected: (a) Duplicating flags into `csharp-testing` — that skill runs no `dotnet` command; duplication would drift. (b) `dotnet test ... | grep -E "Passed!|Failed!|Total tests"` (the raw form suggested in #622) — masks the exit code and drops per-test failure detail; used only as an optional display view under `set -o pipefail`, never for gating.

### 614-fix — keep halt, wire the note

- Decision: `golang-build` already documents (lines 44-48) "Missing goimports: Report ... and stop. Do not silently skip these steps." Keep that halt behavior. Add a single sentence to `git-commit/SKILL.md` step 1 making explicit that the delegated `{lang}-build` lint/format step's tool-availability halt (actionable "install X" message) applies to the pre-commit lint — so an agent following git-commit inherits the stop rather than silently skipping.
- Rationale: In this repo the issue is substantially already fixed (the field report was against loomyard's lagging copy). Halt is the safe direction — it prevents unformatted imports from entering a commit. The only residual gap is that git-commit's terse "run the lint/format step" delegation doesn't surface the halt contract, which is what the reporter's manual workaround compensated for.
- Rejected: (2) Switching golang-build to warn-and-continue — reintroduces the "unformatted code slips through" risk the halt prevents; the reporter's own workaround was to format by hand, i.e. they did NOT want the step skipped. (3) Pure no-op — leaves git-commit's delegation silent on the contract.

## Technical context

- **Language plugins are separate plugins in this monorepo:** `@csharp:csharp-build`, `@golang:golang-build`, invoked via the `@{lang}:{lang}-*` routing table in `plugins/mill/skills/workflow/SKILL.md:46-53`. All live under `plugins/` here, so all fixes are in-repo.
- **`slug_from_branch` cfg dependency:** `_marker.slug_from_branch(git_root, wiki_path, cfg)` reads `cfg.get("spawn", {})` (`_marker.py:79`). `cfg` is required and non-optional — the fix is ordering only, never a signature change.
- **Baseline flow:** `millpy-implement.py:_run_baseline_stage` (line 78) → `_verify_baseline.compute_baseline` (line 70). The failing `git worktree add` is at `_verify_baseline.py:152-153`. `compute_baseline` raises on infrastructure failure; `_run_baseline_stage` catches and emits `{"result": "error"}` (non-blocking), which is why the failure was silent — the baseline is simply never cached and the gate falls back to strict. The verify subprocess itself and junction creation are OS-level (not git), so only the `worktree add` checkout needs the long-path flag.
- **`_verify_baseline` uses `_subprocess_util.run`** for git calls and `subprocess.run` (via `_run_verify_in`) for the verify command. A unit test can monkeypatch/capture `_subprocess_util.run` to assert the argv.
- **csharp-build current commands:** bare `dotnet build` / `dotnet test` (`csharp-build/SKILL.md:16-19`); it already carries a "formatters run on changed files only" convention (line 21) but ships no formatter and no noise filtering.
- **golang-build already halts** on missing `goimports`/`golangci-lint` (`golang-build/SKILL.md:44-48`); `git-commit/SKILL.md:13-15` delegates the pre-commit lint to `{lang}-build` on changed files only.
- **ASCII-only output** for any Python `print()`/`_log()` (Windows cp1252); the baseline test and any new strings must obey this.

## Constraints

- No `CONSTRAINTS.md` at the hub root was found during exploration.
- **Verify command shape:** any plan `verify:` for the Python batch (baseline fix + test) must start with `PYTHONPATH=` (literal empty value) per project convention, so the test subprocess loads worktree code, not the V2 cache. Unit tests run via `run-all.py` (or `uv run --project plugins/mill`).
- **SKILL edits are documentation, not code:** their "verify" is the skill-content lint / manual review, not a test runner. `test-language-skills-directive.py`, `test-skills-index.py`, and `test-skill-helper-drift.py` exist and may assert structural invariants — the SKILL edits must not break them.
- **`-c core.longpaths=true` is per-invocation only** — never write it to global/user/system git config.
- **Never `git add -A`/`git add .`** — stage files individually per git-commit rules.

## Testing

- **#615/#620 (baseline long-path) — TDD candidate.** New unit test (e.g. `plugins/mill/unit_tests/test-verify-baseline.py`) that monkeypatches `_subprocess_util.run` to capture argv and asserts the `git worktree add` call includes `-c core.longpaths=true` in the correct position (immediately after `-C <git_root>`, before the `worktree` subcommand). The teardown is out of scope (unchanged), so no removal-side assertion is needed. Use in-memory/monkeypatch fixtures — no real git.
- **#618, #613, #622, #614 (SKILL edits) — no runtime test.** Verified by: (a) the existing skill-content tests still pass (`run-all.py`); (b) manual read-through confirming the reordered Entry reads config before slug **and binds `git_root`/`wiki_path` before the slug call**, step 5 names `[NOTE]` handling, `csharp-build` shows the unpiped `--nologo -clp:ErrorsOnly` commands plus the "gating invocation is never piped" and "never tail" rules, and `git-commit` step 1 names the halt contract. Add an assertion to `test-language-skills-directive.py` only if it already asserts on `csharp-build`/`golang-build` command content and the new flags would otherwise drift undetected (mill-plan to confirm during planning).
- **Regression guard:** run the full `run-all.py` suite after the baseline change to confirm no existing `test-millpy-implement.py` / `test-worktree.py` expectations break on the added git flag.

## Q&A log

- **Q:** How should the six gaps be structured into a plan? **A:** [auto-pick] One plan, batched by shared file so disjoint gaps parallelize (#618 and #613 co-batch on mill-start/SKILL.md). **Why:** the four batches touch disjoint file sets except mill-start, which two issues share; one-batch-per-issue would put two concurrent writers on the same file.
- **Q:** How to fix #618 (cfg used before load)? **A:** [auto-pick] Reorder Entry to load config before reading the slug in both mill-start and mill-plan; renumber and audit step cross-references. **Why:** `slug_from_branch` genuinely needs `cfg`; the only defect is ordering, so reordering is the minimal literal-safe fix.
- **Q:** How to fix #613 (NOTEs in GAPS_FOUND)? **A:** [auto-pick] Add NOTE handling to interactive step 5 — apply NOTEs via mill-receiving-review default in the same discussion-gap-fix commit, mirroring auto-mode. **Why:** without an instruction, a NOTE alongside gaps silently vanishes if the next reviewer doesn't repeat it (observed live); this pins the field workaround.
- **Q:** How to fix #615/#620 (Windows long-path baseline)? **A:** [auto-pick] Add `-c core.longpaths=true` to the transient `git worktree add` (and removal), plus a unit test. **Why:** worktree add does the checkout in-process so the flag governs it; per-invocation, never mutates global config; leaves the rest of the baseline mechanism intact.
- **Q:** How to fix #622 (dotnet noise)? **A:** [auto-pick] Make `--nologo -clp:ErrorsOnly` the default on build/test in csharp-build, add a "grep the summary, never tail" rule, and a cli/CLAUDE backstop; leave csharp-testing untouched. **Why:** csharp-build is the chokepoint all dotnet routes through; csharp-testing runs no dotnet command.
- **Q:** How to fix #614 (missing goimports)? **A:** [auto-pick] Keep golang-build's existing halt-with-actionable-message; add a one-line note to git-commit step 1 that the delegated tool-availability halt applies. **Why:** golang-build already halts (safe direction, prevents unformatted imports); the only residual gap is git-commit's delegation being silent on that contract. Warn-and-continue was rejected as reintroducing the skip risk the reporter did not want.
- **Q:** Are these gaps already partly fixed in this repo? **A:** [auto-pick, informational] Yes — #614 is largely satisfied by golang-build's existing Tool Installation section (added at the go→golang rename), so its residual is a git-commit wiring note only; the other five are unfixed at the cited lines. **Why:** exploration confirmed exact current-state per the Problem table.
- **Q:** [discussion-review r1 GAP] Does `dotnet test ... | grep` mask the test exit code? **A:** [auto-resolved] Yes — resolved by making the gating `dotnet test --nologo -clp:ErrorsOnly` invocation **unpiped** so dotnet's exit code is authoritative; any summary-only display pipe must use `set -o pipefail`. **Why:** `cmd | grep` returns grep's status; a failing suite would exit 0 and silently pass verify/lint.
- **Q:** [discussion-review r1 GAP] Should the long-path flag also be applied to the worktree teardown? **A:** [auto-resolved] No — teardown left unchanged; `remove_safe` already falls back to `safe_rmtree` on "Filename too long" (`_worktree.py:237-261`), and it is a shared helper with unjustified blast radius. **Why:** removal-side long-path deletion is already covered; scope stays on `_verify_baseline.py`'s add only.
- **Q:** [discussion-review r1 NOTE] Does the summary grep drop per-test failure detail? **A:** [auto-resolved] Moot under the unpiped `-clp:ErrorsOnly` decision — that form keeps VSTest failure names + `Error Message:` blocks (they are not MSBuild console-logger output). The inaccurate "grep keeps Failed! lines" claim was removed. **Why:** `-clp:ErrorsOnly` strips only build-phase warnings, not VSTest results.
- **Q:** [discussion-review r1 NOTE] Does the Entry reorder leave `git_root`/`wiki_path` unbound? **A:** [auto-resolved] Yes — the reordered step 1 must bind `git_root = _paths.resolve_git_root()` and `wiki_path = _paths.resolve_wiki_path(git_root)` (currently resolved inline) before the slug call, in both mill-start and mill-plan. **Why:** those names are otherwise first assigned in Path Setup, after the slug read.
