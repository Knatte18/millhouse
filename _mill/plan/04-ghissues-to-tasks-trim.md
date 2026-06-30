# Batch: ghissues-to-tasks-trim

```yaml
task: "Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis"
batch: ghissues-to-tasks-trim
number: 4
cards: 1
verify: null
depends-on: [1, 2]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

This batch rewrites `mill-ghissues-to-tasks/SKILL.md` into a thin wrapper around `mill-triage-to-tasks`: fetch issues, map to the contract via `_gh_issues.to_contract()`, hand off, then close consumed issues on GitHub using the results file. It depends on batch 1 (`to_contract()` must exist) and batch 2 (`mill-triage-to-tasks` must exist to invoke). It can run in parallel with batch 3 — the two entry skills touch entirely different files. Acceptance for this batch is end-to-end behavior parity with today's skill (fetch → group → proposal → approve → upsert + close issues with pointer), with the one explicit exception already recorded in `_mill/discussion.md` Scope/Out: the per-bullet `detail_hint` formatting (now produced inside `mill-triage-to-tasks`, batch 2 — this batch does not touch task-body formatting at all anymore).

No batch-local decisions beyond `## Shared Decisions` in the overview.

## Cards

### Card 6: trim `mill-ghissues-to-tasks` to a thin adapter wrapper

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_gh_issues.py`
  - `plugins/mill/skills/mill-triage-to-tasks/SKILL.md`
  - `plugins/mill/skills/mill-fold/SKILL.md`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - **Keep unchanged:** the `---` frontmatter (`name: mill-ghissues-to-tasks`, `description:` — update the description's wording only if it now mischaracterizes the skill as doing the grouping itself; otherwise leave it), the introductory paragraphs, and the `## Entry checks` section verbatim (both checks: `gh auth status` must succeed; `.millhouse/wiki/` junction must exist).
  - **Step 1 — Fetch and build the contract** (replaces today's Step 1 "Fetch all open issues"): keep the existing `_gh_issues.fetch(limit=100, git_root=...)` call and the `_gh_issues.detect_repo(git_root=...)` repo-detection call. Immediately after fetching, call `_gh_issues.to_contract(issues, repo)` to build the contract dict, then write it to `.scratch/triage-contract.json` (`json.dump`, indent for readability) — this replaces today's `.scratch/issues.json` as the artifact the next step consumes (the implementer may still write `.scratch/issues.json` as an optional debugging aid, but `.scratch/triage-contract.json` is the canonical handoff file `mill-triage-to-tasks` reads).
  - **Remove entirely:** today's Step 2 ("Read the current task list"), Step 3 ("Analyse and group"), and Step 4 ("Propose") — all three are now `mill-triage-to-tasks`'s job (its own Steps 2–4). Also remove the wiki-write portion of today's Step 5 (the `upsert_task` / `upsert_tasks_batch` / fold-in `get_task`+`upsert_task` calls) — `mill-triage-to-tasks`'s Step 5 now performs every wiki write, including the body-formatting logic (Sources bullets, `detail_hint`, `embed_body`) that today's Step 5 hand-wrote inline.
  - **Step 2 — Hand off to the shared analysis skill** (new): invoke `mill-triage-to-tasks` via the Skill tool (same pattern as `mill-report-to-tasks`, batch 3) and let it run its full Steps 1–7 against `.scratch/triage-contract.json` (read contract, read wiki tasks, group, propose, wait for approval, apply wiki writes, write `.scratch/triage-result.json`, report). This skill performs no grouping, proposal-writing, or wiki-write logic of its own anymore.
  - **Step 3 — Close consumed issues** (replaces the close-loop portion of today's Step 5): after `mill-triage-to-tasks` completes, check whether `.scratch/triage-result.json` exists. If it does not exist, zero items were consumed (either the contract had zero items, or the shared skill's all-skipped short-circuit fired) — report zero closes and stop. If it exists, parse the JSON array (`[{"ref": "<issue-number-as-string>", "route": "new_task"|"fold_in", "slug": "<slug>"}, ...]`); for each entry, map `route` to the exact close-comment string — `"new_task"` → `Consolidated into wiki task: <slug>`, `"fold_in"` → `Folded into wiki task: <slug>` (byte-identical to today's two close-comment strings, and the `fold_in` string is byte-identical to `/mill-fold`'s); call `_gh_issues.close_with_comment(int(entry["ref"]), comment, git_root=...)` (cast `ref` back to `int` — `to_contract()` stored it as `str(issue["number"])`). On any individual close failure, log the issue number + error and continue to the next entry — do not abort the loop; collect all failures for the final report. This preserves today's exact close-on-approval-only invariant: `mill-triage-to-tasks` already gated every wiki write behind operator `approve`, so by the time this step runs, every entry in `.scratch/triage-result.json` is already committed to the wiki.
  - **Step 4 — Report** (replaces today's Step 6): print a summary in the same shape as today's Step 6 but scoped to what this skill itself is responsible for — issues closed and any close failures (the new-task/fold-in/skip counts were already reported to the operator by `mill-triage-to-tasks`'s own Step 7 during the handoff, so do not re-derive or re-print them here to avoid two divergent counts in the same conversation):
    ```
    Revision applied.
      <Z> issues closed on GitHub
      <F> failed to close (see stderr)
    ```
  - **`## Rules` section:** remove rules that now live entirely in `mill-triage-to-tasks` (one-shot/no-resumable-state framing beyond this skill's own scope, "skipped issues are untouched," "unclaimed-only guard" — these are inherited behaviors of the shared skill this skill now delegates to). Keep the rules that are genuinely this skill's own responsibility: "close only on approval + actual write" (now phrased as: only close issues listed in `.scratch/triage-result.json`, which `mill-triage-to-tasks` only writes after operator approval and a successful wiki write), and the exact close-comment strings (`Consolidated into wiki task: <slug>` / `Folded into wiki task: <slug>`, byte-identical to `/mill-fold`'s fold-in string).
- **Commit:** `refactor(mill-ghissues-to-tasks): trim to thin wrapper around mill-triage-to-tasks`

## Batch Tests

`verify: null` — pure skill/markdown batch with no runnable surface, consistent with `_mill/discussion.md` Testing. Manual end-to-end verification (already named in `_mill/discussion.md` Testing): run `/mill-ghissues-to-tasks` against this repo's live open issues once this batch and batch 2 are both implemented, to confirm unchanged end-to-end behavior (fetch → group → proposal → approve → upsert + close issues with pointer).
