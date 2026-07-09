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
- `plugins/mill/scripts/_verify_baseline.py` — add `-c core.longpaths=true` to the transient `git worktree add` (and, for symmetry on removal, the `worktree remove` path via `_worktree.remove_safe` if it shells `git worktree remove`).
- `plugins/mill/unit_tests/` — new test asserting the baseline `git worktree add` argv carries `-c core.longpaths=true`.
- `plugins/csharp/skills/csharp-build/SKILL.md` — make `--nologo -clp:ErrorsOnly` the default on `dotnet build`/`dotnet test`; add the "grep the summary line, never `tail`" rule.
- `plugins/mill/skills/cli/SKILL.md` and/or root `CLAUDE.md` — one-line backstop rule for ad-hoc dotnet invocations where the skill isn't loaded.
- `plugins/golang/skills/golang-build/SKILL.md` — confirm the existing halt-on-missing-tool behavior stands (verification, likely no edit).
- `plugins/mill/skills/git-commit/SKILL.md` — one-line note in step 1 that the delegated `{lang}-build` tool-availability halt applies to the pre-commit lint step.

**Out:**
- No behavior change to `golang-build`'s halt semantics (rejected switching to warn-and-continue — see Decisions). No change to any other `{lang}-comments`/`{lang}-testing` skill except where noted.
- `csharp-testing/SKILL.md` is **not** touched: it holds test-authoring conventions only and shells no `dotnet` command; #622's title names it but the actual invocations live in `csharp-build`.
- No change to the module-wide verify baseline's retry/control-check logic, its `.scratch/` anchoring, or the junction dependency-reuse mechanism — only the long-path flag is added.
- No re-anchoring of the temp verify worktree to system temp or a shorter path (rejected — see Decisions).
- No change to the wiki, task index, or any cross-repo external copy (loomyard/NORCE); those repos re-sync the plugin independently.

## Decisions

### plan-structure — batch by shared file

- Decision: One plan. Batch by shared file so disjoint gaps parallelize, but **#618 and #613 must share a batch** because both edit `mill-start/SKILL.md`. Suggested batching (mill-plan finalizes): (A) mill-start + mill-plan SKILL edits [#618 + #613]; (B) `_verify_baseline.py` + test [#615/#620]; (C) `csharp-build` + cli/CLAUDE backstop [#622]; (D) `golang-build` verify + `git-commit` note [#614].
- Rationale: The four batches touch disjoint file sets, so they can run in parallel; only the mill-start file forces a co-batch.
- Rejected: One-batch-per-issue (6 batches) — would put two writers on `mill-start/SKILL.md` concurrently, risking a merge conflict on the same file.

### 618-fix — reorder Entry, load config first

- Decision: In both `mill-start` and `mill-plan` Entry, move the config-load step ahead of the slug-read step, renumber, and audit the section for any "step 2"/"step 3" cross-references that must be updated. The `slug_from_branch(git_root, wiki_path, cfg)` signature is unchanged — `cfg` genuinely is a required arg (it reads `cfg.get("spawn", {})`).
- Rationale: The call needs `cfg`; the only defect is ordering. Reordering is the minimal, literal-reading-safe fix.
- Rejected: Keeping the order and adding a caveat — leaves a literal-execution trap that already crashed once live; a caveat is weaker than correct ordering.

### 613-fix — NOTE handling in GAPS_FOUND

- Decision: Extend interactive step 5 (the GAPS_FOUND branch) so that after enumerating `[GAP]` findings, any `[NOTE]` findings present in the same review round are applied via the `mill-receiving-review` fix-everything default, folded into the **same** `discussion-gap-fix` commit (no separate commit, no separate report — the review file is the audit trail). This mirrors the auto-mode rule already documented (every gap AND every NOTE treated as FIX) and the APPROVE-branch NOTE handling (4a/4b).
- Rationale: Without this, a NOTE arriving alongside gaps has no instruction and vanishes if the next round's reviewer doesn't repeat it (observed live, internal-burler). The workaround already used in the field is exactly this behavior; pin it.
- Rejected: Documenting that NOTEs "carry forward" — relies on the reviewer re-emitting them, which is the exact fragility being reported.

### 615-620-fix — core.longpaths on the transient worktree

- Decision: Pass `-c core.longpaths=true` to the `git worktree add` invocation in `_verify_baseline.compute_baseline` (line ~152-153): `["git", "-C", str(git_root), "-c", "core.longpaths=true", "worktree", "add", str(tmp_path), parent_sha]`. Apply the same flag to the teardown git call if `_worktree.remove_safe` shells `git worktree remove` (long paths can also block deletion on Windows). Add a unit test asserting the flag is present in the captured argv.
- Rationale: `git worktree add` performs the checkout in-process, so `-c core.longpaths=true` governs that checkout and lets Git-for-Windows use its internal `\\?\` long-path handling. This is the exact fix the issue reporter proposed, is per-invocation (never mutates global/user config), and leaves every other part of the baseline mechanism untouched.
- Rejected: Re-anchoring the temp worktree under system temp or a shorter root — violates the "`.scratch/` only, never system temp" convention and breaks the junction dependency-reuse, which junctions gitignored dep dirs **from `project_root`** into the temp checkout. A shorter path would also still be relative to `project_root`, which is itself already deep.

### 622-fix — filtered dotnet is the default

- Decision: In `csharp-build/SKILL.md`, change the Build Commands block so `dotnet build` becomes `dotnet build --nologo -clp:ErrorsOnly` and the test command becomes a summary-filtered form, e.g. `dotnet test --nologo -clp:ErrorsOnly | grep -E "Passed!|Failed!|Total tests"`. Add an explicit rule: **never `tail -N` a dotnet build/test** (warnings can evict the summary); `grep` for the summary line. Preserve signal (failing test names + assertion messages) — the grep keeps `Failed!` lines; deeper failure detail stays available on re-run or via a logger file, not raw stdout. Add a one-line backstop to `cli`/`CLAUDE.md` for ad-hoc invocations.
- Rationale: `csharp-build` is the chokepoint `workflow`'s language detection routes all dotnet through (`git-commit` lint, mill-go verify, ad-hoc), so centralizing there covers the whole pipeline. The observed waste was ~15–20% of a thread's context from re-dumped whole-solution warnings.
- Rejected: Duplicating flags into `csharp-testing` — that skill runs no `dotnet` command; duplication would drift.

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

- **#615/#620 (baseline long-path) — TDD candidate.** New unit test (e.g. `plugins/mill/unit_tests/test-verify-baseline.py`) that monkeypatches `_subprocess_util.run` to capture argv and asserts the `git worktree add` call includes `-c core.longpaths=true` in the correct position (before the `worktree` subcommand). Cover: (a) the flag is present on the add call; (b) if the teardown path is also patched, the flag is present on `worktree remove`. Use in-memory/monkeypatch fixtures — no real git.
- **#618, #613, #622, #614 (SKILL edits) — no runtime test.** Verified by: (a) the existing skill-content tests still pass (`run-all.py`); (b) manual read-through confirming the reordered Entry reads config before slug, step 5 names `[NOTE]` handling, `csharp-build` shows the filtered commands + the "never tail" rule, and `git-commit` step 1 names the halt contract. Add an assertion to `test-language-skills-directive.py` only if it already asserts on `csharp-build`/`golang-build` command content and the new flags would otherwise drift undetected (mill-plan to confirm during planning).
- **Regression guard:** run the full `run-all.py` suite after the baseline change to confirm no existing `test-millpy-implement.py` / `test-worktree.py` expectations break on the added git flag.

## Q&A log

- **Q:** How should the six gaps be structured into a plan? **A:** [auto-pick] One plan, batched by shared file so disjoint gaps parallelize (#618 and #613 co-batch on mill-start/SKILL.md). **Why:** the four batches touch disjoint file sets except mill-start, which two issues share; one-batch-per-issue would put two concurrent writers on the same file.
- **Q:** How to fix #618 (cfg used before load)? **A:** [auto-pick] Reorder Entry to load config before reading the slug in both mill-start and mill-plan; renumber and audit step cross-references. **Why:** `slug_from_branch` genuinely needs `cfg`; the only defect is ordering, so reordering is the minimal literal-safe fix.
- **Q:** How to fix #613 (NOTEs in GAPS_FOUND)? **A:** [auto-pick] Add NOTE handling to interactive step 5 — apply NOTEs via mill-receiving-review default in the same discussion-gap-fix commit, mirroring auto-mode. **Why:** without an instruction, a NOTE alongside gaps silently vanishes if the next reviewer doesn't repeat it (observed live); this pins the field workaround.
- **Q:** How to fix #615/#620 (Windows long-path baseline)? **A:** [auto-pick] Add `-c core.longpaths=true` to the transient `git worktree add` (and removal), plus a unit test. **Why:** worktree add does the checkout in-process so the flag governs it; per-invocation, never mutates global config; leaves the rest of the baseline mechanism intact.
- **Q:** How to fix #622 (dotnet noise)? **A:** [auto-pick] Make `--nologo -clp:ErrorsOnly` the default on build/test in csharp-build, add a "grep the summary, never tail" rule, and a cli/CLAUDE backstop; leave csharp-testing untouched. **Why:** csharp-build is the chokepoint all dotnet routes through; csharp-testing runs no dotnet command.
- **Q:** How to fix #614 (missing goimports)? **A:** [auto-pick] Keep golang-build's existing halt-with-actionable-message; add a one-line note to git-commit step 1 that the delegated tool-availability halt applies. **Why:** golang-build already halts (safe direction, prevents unformatted imports); the only residual gap is git-commit's delegation being silent on that contract. Warn-and-continue was rejected as reintroducing the skip risk the reporter did not want.
- **Q:** Are these gaps already partly fixed in this repo? **A:** [auto-pick, informational] Yes — #614 is largely satisfied by golang-build's existing Tool Installation section (added at the go→golang rename), so its residual is a git-commit wiring note only; the other five are unfixed at the cited lines. **Why:** exploration confirmed exact current-state per the Problem table.
