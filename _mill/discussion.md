# Discussion: Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis

```yaml
task: Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis
slug: mill-ghissues-source-adapter
status: discussing
parent: main
```

## Problem

`mill-ghissues-to-tasks` (the skill that groups open GitHub issues into a small number of Home.md tasks, with operator approval and close-with-pointer on consumed issues) is entirely welded to `gh issue list` for fetching and `gh issue close` for consuming. The "group related items → compare against existing wiki tasks → consolidated proposal → operator approval → upsert grouped tasks" logic inside it is useful for any source of raw items, not just GitHub issues.

**Why now:** LoomYard's sandbox suite (`tools/sandbox`, repo `Knatte18/loomyard`) produces internal QA verdicts that need exactly this same triage-into-tasks treatment, but the source is a local `sandbox-report.json` file, not GitHub issues — there's nothing to `gh issue close`. Filing those QA findings as GitHub issues just to triage them back out (what issues #35–#41 were) is a category error this task removes. Tracked upstream as GitHub issue #586 (closed, consolidated into this wiki task); the LoomYard-side emitter work is tracked separately as wiki task `sandbox-report-json`.

## Scope

**In:**
- A new shared skill, **`mill-triage-to-tasks`**, holding the source-agnostic analysis: read the input contract, read current wiki tasks, group into a small number of new tasks (soft target 2–3) plus fold-ins plus skips, present one consolidated proposal, on approval write the wiki (new tasks + fold-ins via `_client`), and write a results file listing which items were consumed by which route. This skill never references `gh`.
- A new entry skill, **`mill-report-to-tasks <path-to-json>`**, that reads a local JSON file on the "triage report" contract, validates it, hands off to `mill-triage-to-tasks`, and — because there's no GitHub issue to close — does nothing after the shared skill finishes.
- `mill-ghissues-to-tasks` keeps its current entry behavior (fetch via `gh issue list`, propose, approve, upsert, close-with-pointer) but becomes a thin wrapper: fetch issues, map to the triage-report contract via a new `_gh_issues.to_contract()` function, hand off to `mill-triage-to-tasks`, then loop over the shared skill's results to close each consumed issue on GitHub exactly as today.
- New Python module `_sandbox_report.py` (alongside the existing `_gh_issues.py`) that reads and validates a local JSON file against the contract.
- New `_gh_issues.to_contract(issues, repo) -> dict` function mapping `fetch()`'s existing return shape into the contract shape.
- New schema doc `plugins/mill/templates/triage-report.schema.md` documenting the contract (mirrors the existing `review-output.schema.md` convention).
- Unit tests for `_gh_issues.to_contract()` (extending `test-gh-issues.py`) and a new `test-sandbox-report.py` for `_sandbox_report.py`.
- SKILLS.md regenerated via `/mill-skills-index` to add rows for both new skills.

**Out:**
- Any change to `_gh_issues.fetch()` or `fetch_one()`'s existing return shape — `mill-fold` depends on `fetch_one()` as-is and is untouched by this task.
- The LoomYard-side `sandbox-report.json` emitter itself — that's wiki task `sandbox-report-json`, tracked in the loomyard repo, out of scope here.
- Any change to `mill-fold`'s GH-issue fold path or its close-comment behavior.
- End-to-end behavior change for `mill-ghissues-to-tasks` — acceptance requires it to behave identically to today (fetch → group → proposal → approve → upsert + close issues with pointer).

## Decisions

### Shared analysis lives in a new library skill, not duplicated text

- Decision: Extract Steps 2–5a (read wiki tasks, group, propose, write wiki) of the current `mill-ghissues-to-tasks` into a new skill, `mill-triage-to-tasks`, that is loaded/followed by both `mill-ghissues-to-tasks` and the new `mill-report-to-tasks`, the same way `mill-receiving-review` is a non-entry-point "library" skill loaded by other skills (see `plugins/mill/skills/mill-receiving-review/SKILL.md`). It still gets an `SKILLS.md` row despite not being directly user-invoked, matching `mill-receiving-review`'s precedent.
- Rationale: The acceptance criteria require the analysis half to never reference `gh`, and require `mill-ghissues-to-tasks`'s end-to-end behavior to stay unchanged. A single shared file is the only way to avoid drift between the two entry skills as either evolves.
- Rejected: Duplicating the analysis steps in both skill files — simpler short-term but the two copies will silently diverge over time. Keeping `mill-ghissues-to-tasks` as the literal shared file and having the new skill invoke it — rejected because the issue explicitly requires the analysis half to have zero `gh` references, which `mill-ghissues-to-tasks` as written today does not satisfy.

### Close-with-pointer stays out of the shared skill entirely

- Decision: `mill-triage-to-tasks` only writes the wiki (new tasks + fold-ins) and writes a results file (`.scratch/triage-result.json`) listing consumed items by route (new-task slug / fold-in slug / skipped) — it does not generate or carry any close-comment string, since that's GitHub-specific wording. It performs no closing of any kind. Each entry skill is responsible for any post-write consume step: `mill-ghissues-to-tasks` reads the results file and, for each consumed issue, maps its route to the existing comment string itself — `new_task` → `Consolidated into wiki task: <slug>`, `fold_in` → `Folded into wiki task: <slug>` — then loops `_gh_issues.close_with_comment()` over them exactly as today; `mill-report-to-tasks` reads the same file shape and does nothing further (no GitHub issue exists to close for sandbox-report items).
- Rationale: Keeps the "must not reference gh at all" requirement literally true for the shared skill — there's no `if source == "ghissues"` branch anywhere inside it.
- Rejected: Branching inside the shared skill on `contract.source` to decide whether to close — works mechanically but puts a GitHub-specific code path inside the file the issue explicitly says must stay source-agnostic.

### The triage-report contract carries ref-display fields, not just {source, meta, items}

- Decision: Beyond the issue's proposed `{source, meta, items[{ref,title,body}]}` shape, the contract carries three more top-level fields set once per adapter: `ref_prefix` (a string prepended to `ref` when writing the Sources bullet — `"#"` for ghissues, `""` for sandbox-report), `detail_hint` (a string template with a `{ref}` placeholder for a "how to see full detail" line appended to grouped-task bodies — `"Run \`gh issue view {ref}\` for full detail."` for ghissues, `null` for sandbox-report, since the sandbox item's `body` already is the full content), and `embed_body` (a bool controlling whether each source item's `body` text is written into the task body under its Sources bullet — `false` for ghissues, `true` for sandbox-report).
- Rationale: `mill-triage-to-tasks` needs to write `- Sources: <ref> — <title>` lines, an optional detail-hint line, and (per-adapter) the item's body text into task bodies without knowing it's talking to GitHub. Carrying these three values on the contract keeps that knowledge entirely inside each adapter. `embed_body` exists because the two adapters have genuinely opposite needs: ghissues has `gh issue view #N` as a standing fallback for full detail, so embedding the body would just bloat task bodies with text that's one command away; sandbox-report's `detail_hint` is `null` because there is no external fallback — the local JSON file may be deleted by the operator after the run, so the QA verdict's `body` must land in the task body or the detail is lost permanently.
- Rejected: Baking the prefix directly into each item's `ref` (e.g. `ref="#586"`) and dropping the detail-hint line for both sources — simpler contract shape, but changes `mill-ghissues-to-tasks`'s current task-body output (loses the "run gh issue view" pointer), which the acceptance criteria require to stay unchanged. Always embedding `body` for every source — uniform rule, but regresses `mill-ghissues-to-tasks`'s current minimal-manifest output by inlining full issue text into every grouped task. Never embedding `body` for any source — keeps ghissues unchanged but permanently loses sandbox-report QA detail once the source JSON file is gone, since `detail_hint` has nothing to point back to.

### `_gh_issues.to_contract()` is a new function; `fetch()`/`fetch_one()` are untouched

- Decision: Add `to_contract(issues: list[dict], repo: str) -> dict` to `_gh_issues.py`. It maps each issue's `number → ref` (as `str(number)`), `title → title`, `body → body`, sets `meta={"repo": repo}`, `ref_prefix="#"`, `detail_hint="Run \`gh issue view #{ref}\` for full detail."`, and `source="ghissues"`. `fetch()` and `fetch_one()` keep their current return shapes unchanged.
- Rationale: `mill-fold` depends on `fetch_one()`'s existing shape (`number, title, body, state, labels, createdAt`) for an unrelated purpose; changing it would be an unrelated breaking change. A new function is small, isolated, and unit-testable, matching the project's flat-script convention.
- Rejected: Doing the mapping inline in `mill-ghissues-to-tasks`'s Step 1 `python -c` block (no new public API) — avoids growing `_gh_issues.py`'s surface, but the mapping (plus the ref_prefix/detail_hint constants) is exactly the kind of logic the project already unit-tests for this module (`test-gh-issues.py` exists), so it's better as a tested function than untested inline shell text.

### `_sandbox_report.py` validates strictly and rejects duplicate refs

- Decision: New module `_sandbox_report.py` with a `read(path: Path) -> dict` function. It parses the JSON file, requires `source == "sandbox-report"` (mismatch is treated as "wrong file passed," fails loudly rather than coercing), requires `items` to be a non-... list where every entry has non-empty `ref`, `title`, `body`, and rejects the file if any `ref` repeats within it. On success it returns the contract dict with `ref_prefix=""` and `detail_hint=None` set.
- Rationale: A sandbox-report.json with a wrong/missing `source` field, or a malformed item, is much more likely to be an emitter bug or operator mistake than something to recover from silently. Duplicate refs would corrupt the decision table and the consumed-items tracking inside `mill-triage-to-tasks`, so they're rejected outright rather than silently passing through.
- Rejected: Validating shape only and stamping `source="sandbox-report"` regardless of file content — more permissive, but would silently accept a file that was never meant for this pipeline.

### Handoff between skills uses three fixed scratch files

- Decision: The entry skill writes `.scratch/triage-contract.json` (the full contract) before loading `mill-triage-to-tasks`. `mill-triage-to-tasks` owns and writes `.scratch/triage-proposal.md` (the consolidated proposal presented for operator approval — decisions table, grouped new tasks, fold-ins, skips; same content shape as today's `.scratch/ghissues-to-tasks-proposal.md`, just source-agnostic) and, on approval, `.scratch/triage-result.json` listing, per consumed item, its `ref` and the route it took (`new_task: <slug>` / `fold_in: <slug>` / `skipped`). The entry skill reads `triage-result.json` back to drive its own post-processing (close, for ghissues only).
- Rationale: Matches the existing pattern (`mill-ghissues-to-tasks` already uses `.scratch/issues.json`, `.scratch/wiki-tasks.json`, and `.scratch/ghissues-to-tasks-proposal.md` as informal interchange/presentation files between its own steps); three fixed-name files keep the handoff and the operator-facing proposal explicit and inspectable mid-flow, same as today's scratch artifacts. Naming the proposal file explicitly (rather than leaving it implicit) avoids the two entry skills inventing different proposal filenames/locations.
- Rejected: A single file that `mill-triage-to-tasks` mutates in place — works, but conflates "what was asked for" with "what happened," making it harder to debug a failed run by diffing input vs. output. Leaving the proposal file unowned/unnamed — ambiguous about whether the entry skill or the shared skill writes it.

### `mill-report-to-tasks` takes a required positional path arg and validates it as an entry check

- Decision: Invocation is `/mill-report-to-tasks <path-to-json>`, no default-path fallback. Before doing anything else, the skill checks the file exists, parses as JSON, and that `_sandbox_report.read()` accepts it — mirroring `mill-ghissues-to-tasks`'s `gh auth status` entry check. A `sandbox-report.json` with an empty `items` array (or where every item ends up skipped) reports "nothing to do" and exits cleanly with no proposal file and no wiki writes.
- Rationale: Explicit args match the project's existing skill-invocation style (e.g. `/millhouse-issue "message"`); failing fast on a bad path/shape avoids partial wiki state from a malformed run.
- Rejected: A conventional default path (e.g. `.scratch/sandbox-report.json`) — adds an implicit convention with no current precedent in this project's skills.

## Technical context

- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` — current implementation to split. Steps 1 (fetch) and most of Step 5/6 (close, report) stay in this skill; Steps 2–4 and the wiki-write part of Step 5 move to `mill-triage-to-tasks`.
- `plugins/mill/scripts/_gh_issues.py` — existing `fetch()`, `fetch_one()`, `close_with_comment()`, `detect_repo()` stay as-is; add `to_contract()`.
- `plugins/mill/scripts/_sandbox_report.py` — new module, same style as `_gh_issues.py` (thin, `_paths`-aware, raises a dedicated error class — e.g. `SandboxReportError`, mirroring `GhError`).
- `wiki/_client.py` — `upsert_task`, `upsert_tasks_batch`, `get_task` are the wiki-write primitives both the new shared skill and existing skill already use; no changes needed there.
- `plugins/mill/skills/mill-fold/SKILL.md` and `plugins/mill/scripts/millpy-fold.py` — reference only, for the unclaimed-only guard pattern (`status is None and not deferred`) and the exact fold-in close-comment string (`Folded into wiki task: <slug>`), both of which `mill-triage-to-tasks` must replicate for fold-ins to stay consistent with `/mill-fold`'s output.
- `plugins/mill/skills/mill-receiving-review/SKILL.md` — structural precedent for a non-entry-point "library" skill that other skills load and follow, and that still gets an `SKILLS.md` row.
- `plugins/mill/templates/review-output.schema.md` — naming/format precedent for the new `plugins/mill/templates/triage-report.schema.md`.
- `plugins/mill/unit_tests/test-gh-issues.py` — existing tests to extend for `to_contract()`.
- `plugins/mill/unit_tests/run-all.py` — test runner; new `test-sandbox-report.py` picks up automatically by naming convention.
- `mill:mill-skills-index` skill — regenerates `SKILLS.md`; run after both new skills exist to add their rows.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

- `print()` / `_log()` output in any new Python (`_sandbox_report.py`) must stay ASCII-only per project convention (Windows cp1252 stdout).
- Operational script invocations from skill text must use the `${CLAUDE_PLUGIN_ROOT}` cache form, not `plugins/mill/scripts/` directly (except unit tests, which use `uv run --project plugins/mill`).
- `_client` mutations (new tasks, fold-in body updates) must go through `_client.upsert_task` / `_client.upsert_tasks_batch` / `_client.get_task` — never direct wiki file writes.

## Testing

- `test-gh-issues.py` (extend): unit tests for `to_contract()` — maps a list of `fetch()`-shaped issue dicts into the contract shape; covers `ref` is `str(number)`, `meta.repo` carries the passed repo, `ref_prefix="#"`, `detail_hint` contains the `{ref}` placeholder, `source="ghissues"`. In-memory dicts, no real `gh` calls (matches existing `test-gh-issues.py` fixture style — check its current mocking approach before adding cases).
- `test-sandbox-report.py` (new): unit tests for `_sandbox_report.read()` using tempfile JSON fixtures — covers: valid file parses correctly with `ref_prefix=""` and `detail_hint=None`; missing/empty `items` is accepted (empty list, not an error — the "nothing to do" path is the entry skill's job, not the reader's); item missing `ref`/`title`/`body` raises; `source != "sandbox-report"` raises; duplicate `ref` across two items raises; malformed JSON raises.
- No unit tests planned for the markdown-orchestrated skill steps themselves (`mill-triage-to-tasks`, `mill-report-to-tasks`, the trimmed `mill-ghissues-to-tasks`) — consistent with current practice, where `mill-ghissues-to-tasks` has no existing test coverage of its orchestration. Manual end-to-end verification: run `/mill-ghissues-to-tasks` against this repo's live open issues to confirm unchanged behavior, and run `/mill-report-to-tasks` against a hand-crafted `sandbox-report.json` fixture to confirm the new path.

## Q&A log

- **Q:** Where should the source-agnostic analysis live, structurally? **A:** New shared library skill (mirrors `mill-receiving-review`'s precedent), not duplicated text in both entry skills.
- **Q:** What should the new entry skill be named? **A:** `mill-report-to-tasks`.
- **Q:** Where should the GitHub-only close-with-pointer step live, given the analysis half must not reference `gh`? **A:** In each entry/adapter skill, after the shared skill finishes — not branched inside the shared skill.
- **Q:** How should the ghissues adapter map issues into the contract shape? **A:** New testable `_gh_issues.to_contract()` function, not inline mapping text in the skill.
- **Q:** How strictly should `_sandbox_report.py` validate its input? **A:** Validate shape and require `source == "sandbox-report"` exactly; mismatch fails loudly.
- **Q:** How should the Sources-bullet ref-prefix and "view full detail" hint differ per source without GitHub-specific logic in the shared skill? **A:** Two adapter-supplied contract fields, `ref_prefix` and `detail_hint`.
- **Q:** Should fold-in be supported for the sandbox-report path? **A:** Yes — fold-in is pure wiki logic with no `gh` dependency either way, so the shared skill handles it identically for both sources; only the close-after-fold step (ghissues-only) is adapter-side.
- **Q:** Where should the contract be documented? **A:** New `plugins/mill/templates/triage-report.schema.md`, mirroring `review-output.schema.md`.
- **Q:** What test coverage should this task add? **A:** Unit tests for the two new/changed Python functions (`to_contract()`, `_sandbox_report.read()`) only; no new tests for the markdown orchestration, consistent with current practice.
- **Q:** What should the shared library skill be named? **A:** Not anything with "core" in it (explicit operator pushback on the first suggestion, `mill-issues-to-tasks-core`) — named after the contract format itself once that was named.
- **Q:** What should the new skill's invocation form be? **A:** Required positional arg, `/mill-report-to-tasks <path-to-json>`, no default-path fallback.
- **Q:** What should happen on an empty/all-skipped `items` array? **A:** Report "nothing to do" and exit cleanly — no proposal file, no wiki writes.
- **Q:** What should the triage-report JSON format itself be called? **A:** "triage report" — matches the actual workflow verb (group → propose → approve is triage). Schema doc: `triage-report.schema.md`. Shared skill: `mill-triage-to-tasks`.
- **Q:** How should the skill instructions communicate ref-prefix/detail-hint behavior without implying a code templating system? **A:** Plain contract fields (`ref_prefix`, `detail_hint`) that the assistant follows as instructions when writing task-body text — not a rendering engine.
- **Q:** Should both new skills get `SKILLS.md` rows, and how? **A:** Yes, via `/mill-skills-index` regeneration rather than hand-editing rows.
- **Q:** Should `_sandbox_report.py` reject duplicate `ref` values within one file? **A:** Yes — duplicate refs would corrupt the decision table / consumed-items tracking; fail fast naming the duplicate.
- **Q:** Should `mill-triage-to-tasks` embed each item's `body` into the wiki task body it writes, and should that differ by adapter? (discussion-review r1 gap) **A:** New per-adapter contract field `embed_body: bool` — `false` for ghissues (preserves today's minimal-manifest output; `gh issue view` remains the fallback), `true` for sandbox-report (no external fallback exists once the local JSON file is gone, so the QA detail must land in the task body).
