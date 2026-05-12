# Discussion: Add /mill-fold skill with active-task guard

```yaml
task: (A) — Add /mill-fold skill with active-task guard
slug: mill-fold
status: discussing
parent: main
```

## Problem

The wiki backlog grows by two routes: (a) `mill-add` creates fresh entries from a discussion, and (b) `mill-ghissues-to-tasks` drains the GitHub issue queue, where each issue is either turned into a new task or **folded into** an existing backlog entry. Folding works well during the bulk-triage flow, but there is no single-shot equivalent — when an operator notices a stray issue or a scope addition between triage runs, the only options are to wait for the next `mill-ghissues-to-tasks` cycle or to edit Home.md by hand.

A second gap is more dangerous: both flows currently let the operator fold work into a task that is **already locked**. A task marked `[active]`, `[ready-to-merge]`, or `[pr-pending]` has a worktree, a committed `task/discussion.md`, and — once `mill-plan` has run — a frozen plan DAG. Adding scope after the spawn invalidates the plan silently; the implementer will not see the new requirement, code review will not reference it, and the merge will land short of the operator's intent. The merge will succeed without anyone noticing.

**Why now:** the merge-freeze for the codeguide migration ships next sprint; we want every scope-add against locked work to fail loudly so nothing leaks past the boundary.

## Scope

**In:**

- New skill `mill-fold` at `plugins/mill/skills/mill-fold/SKILL.md`.
- New script `plugins/mill/scripts/millpy-fold.py`.
- New helper `_tasks_md.append_to_body(text, slug, line) -> str`.
- New unit-test file `plugins/mill/unit_tests/test-fold.py` (covers locked-phase guard, missing-slug error, body append).
- Retrofit `mill-ghissues-to-tasks` Step 3 so the "Fold into existing" branch refuses locked-phase targets and re-presents the menu.
- One-line cross-referencing mention in project `CLAUDE.md` under a "Backlog editing invariants" subsection.

**Out:**

- Editing the **title** or **summary** of an existing task entry — that stays a manual edit or a future `mill-groom` extension.
- Removing fold-in lines (un-folding) — out of scope.
- GitHub label management — folds against issues use the existing `_gh_issues.close_with_comment` flow only.
- A `--force` escape hatch for the locked-phase guard — hard refuse, no soft path.
- Multi-issue batch input (`/mill-fold #1 #2 #3 <slug>`) — single source per invocation; rerun for more.
- Personal-memory entries for the rule — the rule lives in skill bodies + `CLAUDE.md`, per the task heading.

## Decisions

### fold-target-mutation

- Decision: Folding appends one new bullet line to the **body** of the target Home.md entry. Title is never edited. For GH-issue folds the appended line is `- Sources: #<N> — <one-line summary>`. For scope-item folds it is `- Folded in: <one-line summary>`. The bullet is inserted as the last non-blank line of the target entry's body, immediately above the trailing blank that separates it from the next `##` heading.
- Rationale: Mirrors the existing Home.md convention used in `subprocess-fixes` (`Sources: #269, #270, #271.`) and `mill-misc-fixes-7` (`Sources: #273, #274, #276.`). Append-only is easier to review in the wiki commit history than in-place merging.
- Rejected: Merging into a single comma-separated `Sources: #N, #M` line (lossy — loses the per-issue one-liner). Free-form paragraph append (heavier; encourages drift from the conventional bullet shape). Title-edit (changes the heading users have memorised and breaks bookmarks).

### invocation-shape

- Decision: Two explicit forms.
  - `/mill-fold #<N> <target-slug>` — GH-issue fold. The script fetches issue text via `_gh_issues.fetch(...)`-style logic (single-issue path; see [[input-form-details]]), asks the operator to confirm a generated one-line summary, then writes the bullet, commits/pushes the wiki, and **only after the wiki commit succeeds** closes the issue with comment `Folded into wiki task: <target-slug>`. This is the canonical close-comment string for the v2 fold subsystem; the `mill-ghissues-to-tasks` bulk-path retrofit replaces its existing `Consolidated into wiki task: <slug>` string with the same `Folded into wiki task: <slug>` string for fold-ins (new-task creation in the bulk path keeps its own wording — `Consolidated into` is still accurate there because multiple issues may collapse into one new task; fold-in is a single-source operation and `Folded into` is the precise verb).
  - `/mill-fold --scope "<text>" <target-slug>` — scope-item fold. The `<text>` becomes the one-line summary verbatim; no GH side-effect.
- Rationale: Argparse-friendly. The two cases differ on whether a GH side-effect runs, so explicit branching is cleaner than magic auto-detection. `#<N>` keeps parity with how operators reference issues in commit messages and Home.md.
- Rejected: Single positional with auto-detect `#42` vs free text (magic; ambiguous when scope text starts with `#`). GH-only mode (forces operators to hand-edit Home.md for scope folds; the original task heading explicitly calls out "or scope item").

### input-form-details

- Decision: For GH-issue folds the script calls a new helper `_gh_issues.fetch_one(number, *, git_root) -> dict` that returns the same shape as one element of `_gh_issues.fetch()` (number, title, body, labels, createdAt) plus a `state` field. The helper invokes `gh issue view <N> --repo <owner/repo> --json number,title,body,state,labels,createdAt,comments` and runs the same `_render_body_with_comments` reduction. `state` is included explicitly because `gh issue view` exits 0 for both open and closed issues — non-zero exit only fires for truly missing issues (404) or auth failure. After a successful exit-0 response, the helper inspects `state`: when it is anything other than `"OPEN"` (i.e. `"CLOSED"`, and any future states `gh` adds) the helper raises `GhError(f"issue #{N} is {state}; only OPEN issues can be folded")`. `millpy-fold.py` lets the `GhError` propagate to `SystemExit(1)` with the error string surfaced. Reasoning: a closed issue was either consolidated into another task (folding it again is a duplicate-provenance bug) or resolved (no work to fold). The auth-failure / 404 path still surfaces `gh`'s stderr verbatim.
  The script generates a draft one-line summary (default: the issue title) and prints it for operator confirmation via a numbered list (`1) Use as-is (Recommended) / 2) Edit / 3) Abort`). If the operator selects option 2 the script reads a single line from stdin. For scope-item folds the `--scope` value is taken verbatim; no confirmation prompt.
- Rationale: `_gh_issues.fetch_one` is missing today (the library only has a batch `fetch`); adding a single-issue path is small and reusable. The state-check is load-bearing — without it a closed issue silently folds. The confirmation prompt keeps Home.md text under operator control without forcing them to type the summary every time. Free-text scope is the operator's responsibility.
- Rejected: Reusing `_gh_issues.fetch(limit=...)` and filtering client-side (wasteful — fetches up to 100 issues when one is needed). No confirmation prompt for GH issues (issue titles are often vague; surfacing them once before commit is cheap insurance). Trusting `gh`'s exit code alone to gate closed issues (factually wrong — `gh issue view` returns data for closed issues with exit 0). Allowing closed-issue folds with a warning (soft path; same anti-pattern the locked-phase guard rejects).

### locked-phase-guard

- Decision: Both `mill-fold` and `mill-ghissues-to-tasks` hard-refuse fold operations whose target is in any of the phases `active`, `ready-to-merge`, `pr-pending`. The set is sourced from `_tasks_md._VALID_PHASES` and the literal tuple `("active", "ready-to-merge", "pr-pending")` is defined as `LOCKED_FOLD_PHASES` in `_tasks_md.py` so both call-sites import it. No `--force` flag, no soft-block. In `mill-fold` the script exits 1 with a message naming the slug, the current phase, and a one-line explanation ("plan is frozen from spawn; scope additions silently invalidate it"). In `mill-ghissues-to-tasks` Step 3, when the operator picks the "Fold into existing" branch the assistant validates the target with `_tasks_md.parse()` before recording the decision; on locked phase it prints the same explanation and re-presents the issue's decision menu (option 2 removed for this issue only).
  Phases `done` and `abandoned` are intentionally **not** in `LOCKED_FOLD_PHASES` — they are permitted fold targets. A `done` task has already shipped; there is no live plan to invalidate, and the operator's intent in folding into a done task is to leave a provenance trail (e.g. "this related issue was resolved by the same change"). An `abandoned` task is a tombstone the operator may consult later; folding there is harmless. Phase `s` (spawn-ready, plan not yet started) is also permitted — by definition no `mill-plan` has run, so there is no frozen plan to invalidate. The full permitted set is therefore `(None, "s", "done", "abandoned")`; the full forbidden set is `LOCKED_FOLD_PHASES = ("active", "ready-to-merge", "pr-pending")`. The guard checks membership in the forbidden set rather than the permitted set so that any future `_VALID_PHASES` addition is treated as permitted by default (fail-open on enumeration drift) — the guard's job is to block live plans, not to enumerate every conceivable phase.
- Rationale: The hard refuse is load-bearing — a soft warn-and-continue is exactly what got us into this bug. The shared `LOCKED_FOLD_PHASES` constant prevents the two call-sites from drifting. Re-presenting the menu in `mill-ghissues-to-tasks` is consistent with that skill's existing "user chooses for every issue" rule. Permitting `done`/`abandoned` folds matches the "leave a provenance trail" workflow that operators already do by hand when an issue clearly belongs against historical work.
- Rejected: `--force` flag (turns the guard into a footgun). Per-skill duplicate phase tuples (drift risk; one skill could be updated while the other lags). Allowing `[pr-pending]` folds (PRs can be amended, but the plan that produced them is frozen — fold belongs against a fresh task). Adding `done`/`abandoned` to `LOCKED_FOLD_PHASES` (no live plan; the guard's purpose is plan-invalidation prevention, not provenance prevention). Fail-closed enumeration (`if phase not in PERMITTED_FOLD_PHASES`) — would break the guard the next time a phase is added to `_VALID_PHASES`.

### body-append-helper

- Decision: Add `_tasks_md.append_to_body(text: str, slug: str, line: str) -> str`. It locates the target heading via the existing `_HEADING_RE`, walks forward to the next `##` heading (or EOF) to find the body region, strips trailing blank lines from that region, appends `line` as a new line (ensuring exactly one newline separates it from the prior body text), then re-emits a single trailing blank before the next heading (or terminates with one newline at EOF). Raises `ValueError("Task with slug X not found in Home.md")` when the slug is absent.
- Rationale: A typed helper in `_tasks_md` keeps the private heading regex private; mill-fold should not parse Home.md by hand. The helper is unit-testable in isolation. Future "annotate-task" skills can reuse it.
- Rejected: Open-coded line arithmetic in `millpy-fold.py` (duplicates body-bounds logic from `_tasks_md`; would need its own regex). Whole-file regex (same drawback). Mutating the `Task` dataclass to carry a body slice (changes the public dataclass shape and breaks `_tasks_md.parse` callers that consume it positionally).

### claude-md-placement

- Decision: Add a short "Backlog editing invariants" subsection to project `CLAUDE.md` (in `c:\Code\millhouse\wts\mill-fold\CLAUDE.md`) under the existing `## Constraints` section. The subsection contains one bullet: "Folding scope into a Home.md task entry — via `mill-fold` or the fold-in branch of `mill-ghissues-to-tasks` — is forbidden when the target's phase marker is `[active]`, `[ready-to-merge]`, or `[pr-pending]`. The plan was committed at spawn time and scope additions silently invalidate it. Phase tuple lives at `_tasks_md.LOCKED_FOLD_PHASES`; both skills import it. Personal memory is **not** a valid place for this rule — it must travel with the repo." The two skill bodies each restate the rule in their own context (skill-level prose, not a re-derivation).
- Rationale: The task heading is explicit — "the rule belongs in the skill body / CLAUDE.md, not personal memory". The `## Constraints` section of `CLAUDE.md` already houses similar invariants (junction-rmtree rule, plugin-root rule). A single bullet keeps `CLAUDE.md` short — full prose stays in the two SKILL.md files.
- Rejected: One-source-of-truth in `CLAUDE.md` only (skill bodies lose context for first-time readers and for sub-agents that don't always re-read `CLAUDE.md`). One-source-of-truth in SKILL.md only (operator may miss the invariant when browsing project rules). Personal-memory entry (explicitly forbidden by the task heading).

### testing-approach

- Decision: Add one new unit-test file `plugins/mill/unit_tests/test-fold.py`. Cases:
  - `test_locked_phase_active_refused` — calls `millpy-fold.main(...)` with an in-memory `tempfile`-backed Home.md whose target is `[active]`; asserts `SystemExit(1)` and no Home.md mutation.
  - `test_locked_phase_ready_to_merge_refused` — same shape, phase `[ready-to-merge]`.
  - `test_locked_phase_pr_pending_refused` — same shape, phase `[pr-pending]`.
  - `test_unmarked_target_accepts_fold` — phase `None`; asserts Home.md gains a new bullet at the end of the target body.
  - `test_spawn_ready_target_accepts_fold` — phase `s`; asserts the bullet is appended.
  - `test_missing_slug_errors` — non-existent slug; asserts `SystemExit(1)` and no mutation.
  - `test_append_to_body_inserts_before_next_heading` — direct unit test on `_tasks_md.append_to_body` with a two-task Home.md fixture; asserts only the target's body grows.
  - `test_append_to_body_eof_target` — target is the last entry in the file; asserts the new line lands above the trailing newline, no `##` follows.
  - `test_append_to_body_missing_slug` — asserts `ValueError`.
  - `test_locked_fold_phases_constant` — asserts `_tasks_md.LOCKED_FOLD_PHASES == ("active", "ready-to-merge", "pr-pending")` (regression guard against silent edits to the tuple).
  - `test_done_phase_accepts_fold` — phase `done`; asserts the bullet is appended (regression guard against accidentally adding `done` to `LOCKED_FOLD_PHASES`).
  - `test_abandoned_phase_accepts_fold` — phase `abandoned`; asserts the bullet is appended.
  - `test_closed_gh_issue_refused` — injected `_gh_issues.fetch_one` returns `{"number": 42, "title": "...", "state": "CLOSED", ...}`; asserts `SystemExit(1)` and no Home.md mutation. (The state-check guard added in `### input-form-details`.)
  - `test_open_gh_issue_accepted` — injected fetch returns `{"state": "OPEN", ...}`; asserts the bullet is appended and the injected `_close_with_comment` was called exactly once with `(42, "Folded into wiki task: <slug>")`.
  All tests use `tempfile` + in-memory text; no real git, no real `gh`, no real wiki. The GH-issue path is exercised by injecting a fake `_gh_issues.fetch_one` callable (the script accepts an injection seam for tests; production wiring stays unchanged).
- Rationale: The active-phase guard is the load-bearing rule; tests cover all three locked phases plus the two accepted phases (`None`, `s`). The `LOCKED_FOLD_PHASES` constant test exists so a future operator cannot silently downgrade the guard without one CI failure.
- Rejected: Integration test against real `gh` (slow, requires auth, redundant with the unit-level injection). No tests (active-phase guard is the entire point of the task; untested = unenforced). Mocking the wiki commit path (the unit tests stop at "Home.md was written correctly"; the commit/push path is shared with `millpy-add.py` and is covered there).

### mill-ghissues-to-tasks-retrofit

- Decision: Modify `mill-ghissues-to-tasks/SKILL.md` Step 3 in two ways.
  1. **Phase guard.** After the operator picks "Fold into existing" and supplies a target slug, the assistant parses Home.md via `_tasks_md.parse()` and checks the target's phase against `_tasks_md.LOCKED_FOLD_PHASES`. On match, the assistant prints:
     ```
     Cannot fold #<N> into <slug>: task is [<phase>]. Plan is frozen — scope additions silently invalidate it. Pick a different action for this issue.
     ```
     and re-presents the issue's decision menu with option 2 omitted ("Fold into existing" struck through and disabled). The operator then picks New task or Skip.
  2. **Bullet alignment.** Step 5's apply-on-approve branch is changed so the fold-in path **always** calls `_tasks_md.append_to_body(home_text, target_slug, f"- Sources: #{N} — {issue_title}")` for each consumed issue. The existing prose "leave existing task text unchanged unless the user asked to append a note" is replaced; the bullet is unconditional. The mill-add-style commit message remains `chore: ghissues-to-tasks — N new, M folded` (proposal SKILL.md uses different wording today; align with `chore:` prefix during the edit).
  3. **Close-comment alignment.** Step 5's per-issue `close_with_comment` call is split into two cases. For **new-task** consumption (issue → fresh slug) the comment stays `Consolidated into wiki task: <slug>` (multiple issues may collapse here; "consolidated" is the precise verb). For **fold-in** consumption (issue → existing slug) the comment becomes `Folded into wiki task: <slug>` to match `/mill-fold`. The current single-string codepath `'Consolidated into wiki task: <slug>'` (`mill-ghissues-to-tasks/SKILL.md` Step 5 #4) is replaced with a per-decision branch.
  The skill body's "Rules" section gains three bullets: "Fold targets must be in an unlocked phase. `_tasks_md.LOCKED_FOLD_PHASES` is the source of truth — never duplicate the tuple.", "Fold-in always appends a `- Sources: #N — <issue title>` bullet to the target body via `_tasks_md.append_to_body`. The Home.md output of a fold-in is identical between this skill and `/mill-fold`.", and "Close-comment strings: new-task → `Consolidated into wiki task: <slug>`; fold-in → `Folded into wiki task: <slug>`. The fold-in string matches `/mill-fold`'s comment verbatim."
- Rationale: Step 3 is the only place where a locked-target fold can sneak in via the bulk path. Re-presenting the menu (rather than re-prompting for a different target slug) matches the skill's existing "one decision per issue" cadence and avoids a slug-correction sub-flow. Aligning the bullet output means a future reader of Home.md cannot tell — and does not need to care — whether a `Sources: #N` line was added by `mill-fold` or by the bulk path; both routes produce identical artefacts.
- Rejected: Auto-converting locked-target folds into "New task" (silently changes operator intent). Re-prompting for a different target slug inline (sub-flow that complicates the existing menu shape). Skipping the retrofit and only enforcing in `mill-fold` (leaves the bulk path as a bypass). Leaving the bulk path's "unchanged unless the user asked to append a note" behaviour as-is (the two skills then produce diverging Home.md outputs for the same operator intent; reviewer #3 caught this). Making the bullet append optional behind a flag (no operator wants to fold without recording provenance; the flag would never be used).

## Technical context

- `plugins/mill/scripts/_tasks_md.py` already houses the Home.md heading regex (`_HEADING_RE`), the `Task` dataclass, `parse`, `set_phase`, `set_phase_at`, `append_entry`, and `remove_entry`. The new `append_to_body` helper and the `LOCKED_FOLD_PHASES` constant live here.
- `plugins/mill/scripts/_gh_issues.py` already has `fetch(...)`, `close_with_comment(...)`, and `detect_repo(...)`. The new `fetch_one(number, *, git_root)` helper goes here. It calls `gh issue view <N> --repo <owner/repo> --json number,title,body,state,labels,createdAt,comments` (note: `state` is **required** in the field list — see `### input-form-details`) and runs the same `_render_body_with_comments` reduction. Returns one `dict` shaped like an element of `fetch()` plus a `state` key (`"OPEN"` / `"CLOSED"`). `gh issue view` exits non-zero only for unknown numbers (404) and auth failures; closed issues exit 0 with `state: "CLOSED"`, so state inspection is required. `fetch_one` raises `GhError` on non-zero exit (404, auth failure) and **also** raises `GhError(f"issue #{N} is {state}; only OPEN issues can be folded")` when `state != "OPEN"`.
- `plugins/mill/scripts/millpy-add.py` is the closest pattern: thin CLI, acquires the wiki lock via `_wiki.wiki_lock`, edits files, regenerates the sidebar via `_sidebar.regenerate`, commits and pushes via `_wiki.write_commit_push`. `millpy-fold.py` mirrors this shape, with one ordering invariant inherited from `mill-ghissues-to-tasks` ("Close only on approval + actual write — never close an issue before the task is committed to Home.md"): **lock → parse → phase-guard → fetch_one (GH path only) → body-append → sidebar regen → commit/push → optional GH close-with-comment (after wiki commit succeeds) → release**. The GH close is the last side-effect; if `_wiki.write_commit_push` raises, the issue is left open so the next run can retry without orphaning provenance.
- The wiki access rules in `CLAUDE.md` `## Wiki access` apply — `millpy-fold.py` never `cd`s to the wiki, all mutations go through `_wiki.write_commit_push` or `git -C <wiki_path>` inside the lock.
- The skill body uses the cache-form invocation from `CLAUDE.md` (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py" ...`), with the PowerShell `/` Bash variants mirrored from `mill-add/SKILL.md`.
- Sidebar regeneration is needed only because the wiki commit also touches `_Sidebar.md`'s task list when a body changes (the `_sidebar` module re-reads Home.md headings; body-only edits do not change the sidebar but the commit-with-sidebar pattern is shared with `mill-add` for consistency).
- For unit tests: `plugins/mill/unit_tests/` already runs flat helper-level Python with `tempfile`; the in-memory test of `millpy-fold.main(...)` follows the same pattern as `test-tasks-md.py`.

## Constraints

- **Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`, never `plugins/mill/...`.** External repos use mill as a plugin with no source checkout; the SKILL.md examples must work against the cache. (CLAUDE.md `## Conventions worth carrying`.)
- **Cache-venv invocation, not `uv run`.** SKILL.md blocks use `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py"`. Source-tree form is reserved for tests.
- **Wiki access via helpers only.** No `cd .wiki/`; mutations through `_wiki.write_commit_push` or `git -C <wiki_path>`; reads via `_wiki.sync_pull` or `read_text(wiki_path / ...)`. The `.wiki` junction is operator convenience, never a code path. (CLAUDE.md `## Path invariants`.)
- **Working state stays on the task branch, never written to the wiki.** No `status.md` / `discussion.md` mirroring required for this task.
- **Slug regex `[a-z][a-z0-9-]*`.** The target-slug positional must match the same pattern that `mill-add` enforces — reuse `_tasks_md._SLUG_RE` (already exposed at module level).
- **Personal memory is forbidden for this rule.** The task heading is explicit; the rule lives in `CLAUDE.md` and the two SKILL.md bodies.

## Testing

- **`_tasks_md.append_to_body`** is TDD-first. Write three tests (`append_to_body_inserts_before_next_heading`, `append_to_body_eof_target`, `append_to_body_missing_slug`) and the helper together; helper bodies are short enough that the tests drive the implementation.
- **`millpy-fold.py` main path** is unit-tested via `tempfile`-backed Home.md + injected `_gh_issues.fetch_one` callable. The script accepts `_fetch_one=...` kwarg as a test seam (default `None` → production `_gh_issues.fetch_one`). Same pattern for `_close_with_comment=...`. No real `gh` invocation in tests.
- **Locked-phase guard** has three positive-refusal tests (one per locked phase) and two acceptance tests (`None` phase, `s` phase). Each refusal test asserts no Home.md mutation occurred (read pre/post text equality).
- **`LOCKED_FOLD_PHASES` constant** is asserted equal to `("active", "ready-to-merge", "pr-pending")` so silent downgrades fail CI.
- **`mill-ghissues-to-tasks` retrofit** is documentation-only and exercised by reviewer eyeballs — the SKILL.md change is a prose update with no script behind it. No automated test.
- **Wiki commit/push path** is shared with `millpy-add.py` and covered by its existing integration coverage; no new wiki-level tests here.

## Q&A log

- **Q:** What does "fold" do to Home.md? **A:** [auto-pick] Append a `- Sources: #N — <summary>` (or `- Folded in: ...`) bullet to the target's body. **Why:** matches the existing convention in `subprocess-fixes` and `mill-misc-fixes-7`; preserves per-source provenance vs lossy merging.
- **Q:** Input forms for `/mill-fold`? **A:** [auto-pick] Two explicit forms — `#<N> <slug>` for GH, `--scope "<text>" <slug>` for scope items. **Why:** the two paths differ on whether a GH close-with-comment runs, so explicit branching is cleaner than magic auto-detection.
- **Q:** Script vs skill-only? **A:** [auto-pick] Thin skill over `millpy-fold.py` mirroring `millpy-add.py`. **Why:** wiki lock + Home.md edit + GH close + sidebar regen + commit/push is too much to do via inline `python -c` blocks reliably; the script is reusable and unit-testable.
- **Q:** Issue lifecycle on the GH path? **A:** [auto-pick] Post `Folded into wiki task: <slug>` comment and close. **Why:** matches `mill-ghissues-to-tasks`'s close-with-pointer-comment model; leaving claimed-but-open issues is a forgetting hazard.
- **Q:** Hard-block behavior on locked phases? **A:** [auto-pick] Hard error, exit 1, no writes, no GH side-effects. **Why:** task heading is explicit; a soft-block path is exactly what allowed this bug to exist.
- **Q:** Retrofit the same guard into `mill-ghissues-to-tasks`? **A:** [auto-pick] Yes — parse target with `_tasks_md.parse` in Step 3, refuse locked phase, re-present the issue's decision menu. **Why:** otherwise the bulk path is a bypass.
- **Q:** Where does the rule live? **A:** [auto-pick] Skill bodies + a one-bullet "Backlog editing invariants" item in project `CLAUDE.md` under `## Constraints`. **Why:** task heading is explicit ("skill body / CLAUDE.md, not personal memory"); `## Constraints` already houses similar invariants.
- **Q:** Validation when target slug missing from Home.md? **A:** [auto-pick] Hard error, exit 1, no writes. **Why:** matches `millpy-add.py`'s duplicate-slug rejection style; interactive re-prompt breaks non-interactive callers.
- **Q:** Unit tests? **A:** [auto-pick] Add `test-fold.py` with locked-phase guard cases, missing-slug, body append, and a `LOCKED_FOLD_PHASES` constant assertion. **Why:** the guard is the entire point of the task; untested = unenforced.
- **Q:** Aggregation when target has prior fold-in lines? **A:** [auto-pick] Append a new bullet per fold. **Why:** mirrors current Home.md convention; in-place merging is lossy and harder to review.
- **Q:** How is the target task's body region detected for the append? **A:** [auto-pick] New typed helper `_tasks_md.append_to_body(text, slug, line)`. **Why:** keeps the private heading regex private; unit-testable; future annotate-task skills can reuse it.
- **Q:** Should closed GH issues be valid fold sources (review r1 GAP)? **A:** [auto-resolve] No — `fetch_one` includes `state` in `--json` and raises `GhError` for any state other than `OPEN`. **Why:** `gh issue view` exits 0 for closed issues, so exit-code-alone is insufficient; a closed issue was either already consolidated (duplicate-provenance bug) or resolved (no work to fold).
- **Q:** Are `done` and `abandoned` phases valid fold targets (review r1 NOTE)? **A:** [auto-resolve] Yes — permitted. The guard checks the forbidden set (`LOCKED_FOLD_PHASES`), not a permitted set, so any phase added to `_VALID_PHASES` in the future defaults to permitted. **Why:** done/abandoned tasks have no live plan to invalidate; folding leaves a provenance trail. Fail-open enumeration prevents future drift.
- **Q:** Should `mill-ghissues-to-tasks` fold-in produce the same Home.md bullet as `/mill-fold` (review r1 NOTE)? **A:** [auto-resolve] Yes — the Step 5 retrofit unconditionally calls `_tasks_md.append_to_body(..., f"- Sources: #{N} — {issue_title}")` per consumed fold-in. **Why:** identical Home.md output regardless of which route added the fold-in; a future reader cannot tell which skill ran, and does not need to care.
- **Q:** Should `fetch_one`'s `--json` field list include `state` (review r2 GAP)? **A:** [auto-resolve] Yes — Technical context now lists `number,title,body,state,labels,createdAt,comments`. **Why:** the round-1 fix to `### input-form-details` required state inspection but Technical context contradicted it by omitting `state` and by claiming closed issues exit non-zero. Aligned.
- **Q:** Where does the GH close-with-comment fall in the millpy-fold sequence (review r2 GAP)? **A:** [auto-resolve] After `_wiki.write_commit_push` succeeds, never before. Full sequence: `lock → parse → phase-guard → fetch_one → body-append → sidebar regen → commit/push → optional GH close → release`. **Why:** mirrors the `mill-ghissues-to-tasks` invariant "Close only on approval + actual write — never close an issue before the task is committed to Home.md". If the wiki commit fails the issue stays open and the next run retries cleanly.
- **Q:** Which close-comment string wins (review r2 NOTE)? **A:** [auto-resolve] Fold-in (single-source) uses `Folded into wiki task: <slug>`; new-task (potentially multi-source) keeps `Consolidated into wiki task: <slug>`. The bulk-path retrofit splits its single string into a per-decision branch. **Why:** "fold-in" semantically matches the new skill name and the Home.md `- Sources:` bullet; "consolidated" remains accurate when N issues collapse into one new task.
