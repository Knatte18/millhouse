# Discussion: Skill doc/table accuracy gaps across mill-groom, mill-start/mill-plan, and implementer-brief

```yaml
task: Skill doc/table accuracy gaps across mill-groom, mill-start/mill-plan, and implementer-brief
slug: mill-skill-docs-and-tooling-accuracy
status: discussing
parent: hanf/linux-port-more
```

## Problem

Four independent doc/tooling accuracy gaps accumulated in mill's skill files, each filed as a GitHub issue and consolidated into this one wiki task. None share a root cause — they are unrelated small corrections, bundled for a single discussion/plan/implement pass rather than four separate tasks:

1. `mill-groom/SKILL.md`'s Entry checks verify a wiki junction path (`.millhouse/wiki/`) that stopped being created by `mill-setup` weeks ago; the current convention is `.wiki`. The check currently always reports MISSING and is dead weight — `_paths.resolve_wiki_path()` already resolves correctly regardless.
2. `mill-start/SKILL.md`'s Agent-mode dispatch text for the discussion-review finalize call never names the `--agent-output` flag that `millpy-review-discussion.py --stage finalize` requires unconditionally (confirmed in the script's own argparse — it exits 1 with `"ERROR: --agent-output required for finalize stage"` otherwise). An orchestrator following the skill text literally hits this error and has to discover the flag from the CLI's own error message.
3. During a real mill-go batch, an implementer accidentally ran `uv add --dev ruff` (a project-mutating command) while doing an ad-hoc lint check, instead of an ephemeral `uvx ruff check`. It self-corrected before anything landed, but the guidance that would have prevented the near-miss doesn't exist anywhere in the docs.
4. `mill-start/SKILL.md` step 4b (the post-APPROVE-with-NOTEs fix round) leaves `status.md` at `phase: discussion-fix-rN` until Phase: Handoff runs and appends `discussed`. On the happy path this works today (confirmed via `git blame` — Handoff's unconditional `discussed` append has existed since 2026-06-19). The gap is a **resume-safety** one: if the mill-start session is interrupted between step 4b's commit and Phase: Handoff's commit, `status.md` is left at `discussion-fix-rN`, which `mill-plan`'s entry table (`mill-plan/SKILL.md` line ~34-37) does not recognize — it falls into the catch-all "any other phase... halt" row, leaving the task stuck with no recognized entry point even though the discussion itself is fully reviewed and approved.

**Why now:** all four were independently reported via `mill:millhouse-issue` / self-report during real task runs, then folded into a single backlog task by `mill-ghissues-to-tasks` (see the four `gh issue view` comments: "Consolidated into wiki task: mill-skill-docs-and-tooling-accuracy"). This discussion session batches them for one plan/implement pass.

## Scope

**In:**
- `plugins/mill/skills/mill-groom/SKILL.md` — Entry checks step 1/2: drop the hardcoded `.millhouse/wiki/` junction existence check; rely on `_paths.resolve_wiki_path()` succeeding or raising, reporting the same "Run `/mill-setup` first" message on failure.
- `plugins/mill/skills/mill-start/SKILL.md` — two Agent-mode dispatch finalize-invocation sentences (Phase: Discussion Review step 2, and the Step 3.5 ERROR-only-aggregate-retry subsection): add explicit `--agent-output <output_path>` (sourced from the prepare envelope's `output_path` field) alongside the existing `--round <round>` threading language.
- `plugins/mill/skills/mill-start/SKILL.md` — step 4b (interactive path, ~line 220): append `discussed` via a second `_status.append_phase` call in the same commit as `discussion-fix-r{N}`, so an interruption after this single commit still leaves `status.md` in a phase `mill-plan`'s entry table recognizes. The `--auto` mode subsection's separate restatement of this same sequence (~line 37, "append `discussion-fix-r{N}` to the status timeline, single commit...") is trimmed to delegate to the interactive step 4b text in full (including its status-append and commit sequence) rather than re-enumerating the steps — this is the second of two edit sites and closes the duplication that let this exact gap occur.
- `CLAUDE.md` (repo root) — `## Conventions` section: add a line steering ad-hoc Python lint checks toward `uvx ruff check .` (ephemeral, no project mutation) and explicitly warning against `uv add`/`uv sync` for a one-off lint tool install, mirroring the existing dotnet ad-hoc-invocation convention already in that section.

**Out:**
- No change to `python-build/SKILL.md` (the plugin skill stays generic — it also serves poetry/pipenv/plain-venv Python projects via its existing "Test discovery" section, so hardcoding `uvx` there would be wrong for non-`uv` consumers).
- No change to `mill-plan/SKILL.md`'s entry table (rejected alternative for issue #697 — see Decisions below).
- No change to `implementer-brief.md` (issue #671's guidance lands in CLAUDE.md instead, which implementer sessions already read at session start; no separate brief edit needed).
- No broader audit of other skill files for similar staleness/omission bugs — this task is scoped to exactly the four consolidated issues, not a general accuracy sweep.
- No change to `millpy-review-discussion.py` itself (issue #678 is a docs-only fix; the CLI's `--agent-output` requirement is correct as-is, only the skill text describing how to call it was incomplete).

## Decisions

### mill-groom-junction-check

- Decision: Replace the two-step Entry checks (hardcoded `.millhouse/wiki/` existence test, then a separate `_paths.resolve_wiki_path()` call) with a single step that calls `_paths.resolve_wiki_path(_paths.resolve_git_root())` directly and catches failure (exception or non-zero exit) to report exactly: "wiki path could not be resolved. Run `/mill-setup` first." (replacing the current junction-referencing message verbatim — the new message names no junction path, since none is checked anymore). Store the successful result as `<WIKI_PATH>` as before.
- Rationale: CLAUDE.md's hard constraint "All path resolution through `_paths.py`... Never pass `.wiki`, `.active`, or any junction to a Python helper" already establishes that junction paths are IDE/terminal convenience only, never a doc-level check target. A second hardcoded literal (whether `.millhouse/wiki/` or `.wiki`) reintroduces the exact staleness risk that caused this bug — the next junction convention change would silently break the check again.
- Rejected: Swapping the hardcoded string to `.wiki` and keeping the two-step structure — fixes today's symptom but not the underlying pattern; the issue's own text calls out this option as inferior ("or drop the hardcoded path and just rely on `_paths.resolve_wiki_path` succeeding/raising").

### mill-start-agent-output-flag

- Decision: At both of mill-start/SKILL.md's "Thread `--round <round>` from the prepare envelope into the finalize invocation unchanged" sentences (Phase: Discussion Review step 2, and the Step 3.5 ERROR-only-aggregate-retry subsection), extend the sentence to also name `--agent-output <output_path>`, explicitly noting the value comes from the prepare envelope's `output_path` field (per the general Agent-mode dispatch pattern's step 2 extraction, already documented in `mill-go/SKILL.md`).
- Rationale: Locality — the orchestrator reads and acts on the sentence immediately before making the finalize call; repeating the flag at the point of use is more robust against exactly the failure mode that produced this bug (a reader inferring "unchanged" meant "no other args needed").
- Rejected: A single pointer sentence near the top of the phase referring back to mill-go's step 6 instead of repeating locally — adds an indirection hop that the original bug report shows readers don't reliably follow.

### uv-ephemeral-lint-convention

- Decision: Add a line to this repo's root `CLAUDE.md` `## Conventions` section: ad-hoc Python lint/format checks (when a project-specific python-build override isn't in place) should use `uvx ruff check .` — an ephemeral, non-mutating invocation — never `uv add`/`uv sync` to install a lint tool for a one-off check.
- Rationale: `python-build/SKILL.md` is a shared, cross-project plugin skill also used by poetry/pipenv/plain-venv Python projects (its own "Test discovery" step explicitly branches on `[tool.poetry]` / `Pipfile`). Mill-repo-specific ad-hoc tooling conventions already live in CLAUDE.md — see the existing "Ad-hoc `dotnet build`/`dotnet test`... pass `--nologo -clp:ErrorsOnly`" convention, which is the direct precedent for this fix's placement.
- Rejected: Hardcoding `uvx ruff check .` into `python-build/SKILL.md`'s Defaults — would incorrectly apply `uvx` semantics to non-`uv`-managed consumer projects using the same shared plugin.

### mill-start-discussion-fix-handoff-gap

- Decision: This fix has **two edit sites** in mill-start/SKILL.md, both describing the same 4b sequence:
  1. **Interactive step 4b** (~line 220): immediately after `_status.append_phase(status_path, f"discussion-fix-r{N}", _timestamp.now_utc_iso())`, add a second call `_status.append_phase(status_path, "discussed", _timestamp.now_utc_iso())` — both calls land before the single commit step 4b already makes.
  2. **`--auto` mode subsection's restatement** (~line 37): currently re-enumerates the same sequence independently ("append `discussion-fix-r{N}` to the status timeline, single commit covering..."). Trim this to delegate fully to interactive step 4b's text (its status-append calls and commit sequence, unchanged) instead of re-listing the steps — e.g. "take the interactive 4b path verbatim, in full, including its status-append and commit sequence." A second independent enumeration is exactly what let this gap slip through undetected on the auto path; removing the duplication prevents the two texts from drifting apart again.

  Phase: Handoff's own unconditional `_status.append_phase(status_path, "discussed", timestamp)` is left unchanged (it still runs on the non-interrupted path, producing a harmless duplicate `discussed` timeline row — the append-only timeline already tolerates this shape, e.g. `discussion-fix-rN` itself doesn't advance any round counter but still adds a timeline entry).
- Rationale: Closes the actual interruption window — status.md's `phase:` YAML key reaches `discussed` inside the same git commit that records `discussion-fix-r{N}`, so an interruption immediately after step 4b's single commit+push (before Phase: Handoff ever runs) still leaves the task in a state `mill-plan`'s entry table recognizes (`phase: discussed`, no `plan_dir` → Phase: Plan).
- Rejected: Teaching `mill-plan`'s entry table a new row for `discussion-fix-r*` phases with latest-review-APPROVE verification — this would require `mill-plan` to re-open and re-parse the discussion-review's review file to confirm the verdict, duplicating verification `mill-start` already performed and adding a second place that can drift from the review-file schema. Folding the phase-append into mill-start's existing commit is strictly simpler and keeps `discussed` as the single source of truth for "ready to plan."

## Technical context

- `_status.append_phase(status_path, phase, timestamp)` — updates the `phase:` YAML key in `_mill/status.md`'s frontmatter and appends a row to the `## Timeline` section. Confirmed via the live `_mill/status.md` in this worktree (`phase: discussing` / `## Timeline` `discussing '...'` row) and via mill-start/mill-plan's existing call sites. Calling it twice in quick succession (as decision `mill-start-discussion-fix-handoff-gap` does) is not a new pattern — every phase transition in mill-start/mill-plan already works this way, one call per phase.
- `_paths.resolve_wiki_path(git_toplevel: Path) -> Path` — the only sanctioned way to resolve the wiki path; raises/halts if unresolvable. Already used correctly in mill-groom Step 1 (`## Step 1 — Read config` at line ~32) and everywhere else in the codebase; only the Entry checks section (lines 17-25) still has the stale duplicate hardcoded check.
- `millpy-review-discussion.py --stage finalize` argparse (lines ~50, ~145-147): `--agent-output` is validated as required with a literal error string `"--agent-output required for finalize stage"` when absent — this is the CLI contract mill-start's doc text must match.
- `mill-go/SKILL.md`'s "## Agent-mode dispatch" section (line 105 onward), step 6 (line 153), is the single source of truth mill-start's dispatch text refers back to by name ("follow the Agent-mode dispatch pattern... in mill-go/SKILL.md") — it already documents `--agent-output <path>` correctly for the general case (`output_path` from the prepare envelope for review CLIs). No change needed there; only mill-start's own two local sentences (which restate `--round` threading without also restating `--agent-output`) are wrong.
- `mill-plan/SKILL.md`'s entry table (lines ~30-37) is the exact table that rejects an unrecognized `phase:` value — any phase not matching `discussed` / `planning`|`plan-review-*`|`plan-fix-*` / `approved: true` falls into the catch-all halt row.
- CLAUDE.md's existing `## Conventions` section already contains the precedent line to model the new convention on: "Ad-hoc `dotnet build`/`dotnet test` (when `csharp-build` isn't loaded): pass `--nologo -clp:ErrorsOnly`... For non-Python projects... use the native test runner directly without the prefix."
- `plugins/mill/pyproject.toml` and `plugins/mill/uv.lock` are the specific files at risk from an accidental `uv add` during ad-hoc lint checks in this repo (per the original #671 incident report) — confirms this repo is itself `uv`-managed, which is why the CLAUDE.md convention (repo-scoped) is the right fix location rather than the shared `python-build` plugin skill (multi-repo-scoped).

## Constraints

_No `CONSTRAINTS.md` present at the hub root — none discovered during discussion beyond what's captured under Decisions/Scope above._

## Testing

This task is a pure documentation/markdown change — no application code paths are touched, so there is nothing to unit-test. Verification is manual/inspection-based per changed file:

- **mill-groom/SKILL.md:** re-read the merged Entry checks step to confirm it no longer references `.millhouse/wiki/` anywhere, and that the single `_paths.resolve_wiki_path()` call's failure path still produces the "Run `/mill-setup` first" message.
- **mill-start/SKILL.md (agent-output):** grep the file for `--agent-output` and confirm both of the two "Thread `--round`..." sentences (Phase: Discussion Review step 2, and Step 3.5) now include it; cross-check the wording against `mill-go/SKILL.md`'s step 6 phrasing for consistency (same "from the prepare envelope's `output_path` field" language).
- **mill-start/SKILL.md (discussion-fix-rN):** re-read interactive step 4b to confirm both `_status.append_phase` calls (`discussion-fix-r{N}` then `discussed`) appear before the single commit line, and that the commit/push text is otherwise unchanged (still one commit, same four pathspecs, same commit message). Separately re-read the `--auto` mode subsection's restatement (~line 37) to confirm it no longer independently enumerates the status-append/commit sequence and instead delegates to interactive step 4b in full — grep for `discussion-fix-r{N}` in that subsection should show it deferring to 4b's text, not repeating it.
- **CLAUDE.md:** re-read the `## Conventions` section to confirm the new `uvx` line reads consistently with the existing dotnet convention's style (same "Ad-hoc ... (when X isn't Y): ..." phrasing pattern) and doesn't contradict `python-build/SKILL.md`'s own generic guidance.
- No `verify:` command is meaningful for a plan batch here — mill-plan should set `verify: null` (or the repo's markdown-lint-only equivalent, if one exists) for these batches, since there's no test suite covering skill-doc prose.

## Q&A log

- **Q:** mill-groom stale junction check fix approach? **A:** [auto-pick] Drop hardcoded check, rely on `_paths.resolve_wiki_path()` success/failure. **Why:** matches CLAUDE.md's hard constraint "All path resolution through `_paths.py`" — a second hardcoded literal is exactly what caused this staleness bug and will recur the next time the junction convention changes.
- **Q:** mill-start `--agent-output` fix approach? **A:** [auto-pick] Name `--agent-output <output_path>` explicitly at both finalize-invocation sites. **Why:** locality — the orchestrator reads the sentence right before making the call; a separate pointer sentence is one more hop to miss, which is exactly how this bug happened the first time.
- **Q:** uvx ephemeral-lint fix location? **A:** [auto-pick] CLAUDE.md `## Conventions`, not `python-build/SKILL.md`. **Why:** `python-build` is a shared cross-project plugin skill (also serves poetry/pipenv/plain-venv projects per its own Test discovery section); mill-repo-specific tooling conventions already live in CLAUDE.md (see the existing dotnet `--nologo -clp:ErrorsOnly` precedent).
- **Q:** mill-start interruption-gap fix approach? **A:** [auto-pick] Fold `discussed` append into step 4b's commit. **Why:** closes the actual interruption window at the source; teaching mill-plan to re-parse review verdicts for a phase-prefix match duplicates verification mill-start already did and adds fragility for no benefit.
- **Q:** [review r1 GAP] step 4b's discussed-append fix has two edit sites (interactive line ~220, `--auto` restatement ~line 37) — should the `--auto` restatement independently gain the same append, or delegate to interactive 4b? **A:** [auto-pick] Trim the `--auto` restatement to delegate to interactive step 4b in full (status-append + commit sequence), rather than re-enumerating the steps. **Why:** a second independent enumeration of the same procedure is exactly what let this gap go undetected on the auto path in the first place; removing the duplication prevents the two texts from drifting apart again.
