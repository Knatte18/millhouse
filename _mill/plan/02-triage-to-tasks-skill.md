# Batch: triage-to-tasks-skill

```yaml
task: "Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis"
batch: triage-to-tasks-skill
number: 2
cards: 1
verify: null
depends-on: [1]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

This batch writes `mill-triage-to-tasks`, the new non-entry-point "library" skill that holds the entire source-agnostic analysis: read the contract, read current wiki tasks, group into new tasks / fold-ins / skips, present one consolidated proposal, and on approval write the wiki and a results file. It is its own batch because it is the single shared seam both entry skills (batches 3 and 4) depend on — neither of those batches can be written correctly without this skill's exact scratch-file contract (input: `.scratch/triage-contract.json`; output: `.scratch/triage-proposal.md` and, on approval, `.scratch/triage-result.json`) already fixed. This skill never invokes `gh` and never branches on `contract["source"]` — see `## Shared Decisions` "Decision: close-with-pointer is adapter-only, never in the shared skill" in the overview. It is invoked the same way `mill-receiving-review` is invoked elsewhere in this project: via the Skill tool (`mill:mill-triage-to-tasks`), not as a CLI script.

No batch-local decisions beyond `## Shared Decisions` in the overview.

## Cards

### Card 4: `mill-triage-to-tasks` shared analysis skill

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
  - `plugins/mill/skills/mill-fold/SKILL.md`
  - `plugins/mill/scripts/millpy-fold.py`
  - `plugins/mill/templates/triage-report.schema.md`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/mill-triage-to-tasks/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - **Frontmatter:** `name: mill-triage-to-tasks`, `description:` one line stating it is the source-agnostic triage-report analysis (group → compare-vs-wiki → propose → approve → upsert), loaded by entry skills after they write `.scratch/triage-contract.json`, and that it never references `gh`. Match the YAML frontmatter format used by `mill-receiving-review/SKILL.md` and `mill-ghissues-to-tasks/SKILL.md` (`---` frontmatter is correct here — SKILL.md is the documented exception to the project's "no `---`" convention).
  - **Opening section:** state plainly that this skill is not invoked directly by an operator — it is invoked via the Skill tool by `mill-ghissues-to-tasks` and `mill-report-to-tasks` after they write `.scratch/triage-contract.json`. Mirror the framing `mill-receiving-review/SKILL.md` uses for "this must be loaded by other skills."
  - **Step 1 — Read the contract.** Read and parse `.scratch/triage-contract.json` from the current worktree (the calling entry skill is responsible for having written it before invoking this skill). Halt with a clear message if the file is missing or fails to parse as the expected envelope shape (`source`, `meta`, `items`, `ref_prefix`, `detail_hint`, `embed_body` — same field names as `plugins/mill/templates/triage-report.schema.md`).
  - **Step 2 — Read the current task list.** Port `mill-ghissues-to-tasks/SKILL.md` Step 2 verbatim in spirit: resolve `wiki_path` via `_paths.resolve_wiki_path(_paths.resolve_git_root())`, call `wiki._client.list_tasks_brief(wiki_path)`, store the result for the grouping step. Each task dict has keys `{id, slug, title, layer, brief, status, has_proposal}`.
  - **Step 3 — Analyse and group.** Port `mill-ghissues-to-tasks/SKILL.md` Step 3, generalized to `items` instead of `issues`: using judgment, group the contract's `items` into a small number of **new** tasks (soft target 2–3, natural grouping by theme, no hard cap, do not force unrelated items together or over-split tightly related ones), plus fold-in candidates, plus skips. For each new task: draft a slug (validate `[a-z][a-z0-9-]*`; must not collide with an existing slug from Step 2), a title, and a one–two sentence brief theme statement. For each fold-in candidate, apply the **unchanged** unclaimed-only guard from `millpy-fold.py`'s `unclaimed-only-allowlist` decision: from the already-loaded task list, find the task with matching slug and inspect `status`/`deferred`; a fold target must have `status is None and not deferred`; any other state routes the item to a new task or skip instead. There is NO per-item decision menu and NO per-item prompting — all grouping decisions are made at once and presented together in Step 4.
  - **Step 3.5 — All-items-skipped short-circuit.** If, after grouping, there are zero new tasks AND zero fold-ins (every item routed to skip), do NOT write `.scratch/triage-proposal.md` and do NOT write anything to the wiki. Print a one-line "nothing to do — N item(s), all skipped" status message to chat, then stop (return control to the calling entry skill without writing `.scratch/triage-result.json` either — the entry skill must treat "no results file written" as "nothing was consumed").
  - **Step 4 — Propose.** Write the consolidated proposal to `.scratch/triage-proposal.md` (note: NOT `.scratch/ghissues-to-tasks-proposal.md` — that filename is retired by this skill). Same content shape as `mill-ghissues-to-tasks/SKILL.md` Step 4 generalized to be source-agnostic: (1) a decisions table listing every item (by `ref`, using `contract["ref_prefix"] + ref` for display) and its routing (New task / Fold-in / Skip); (2) a "New tasks (grouped)" section listing each drafted slug/title/brief with source items grouped under each; (3) a "Fold-ins" section listing each target slug and its source items; (4) a "Skipped" section listing skipped items and skip reasons. Unlike the original skill, do NOT include any close-comment string in the proposal — this skill never writes GitHub-specific text. Print a one-line summary to chat plus the file path. The operator replies `approve` or gives feedback; on feedback, revise the grouping and re-present the full proposal, looping until `approve` or an explicit abort. **Nothing is written to the wiki until `approve`.**
  - **Step 5 — Apply (on approve).** For each grouped new task, build its body from the per-item Sources bullets: for each source item, write `- Sources: {contract["ref_prefix"]}{item["ref"]} — {item["title"]}`; immediately after that bullet, when `contract["detail_hint"]` is non-null, write the hint line with `{ref}` substituted from that same item's `ref`; immediately after that, when `contract["embed_body"]` is true, write the item's `body` text. Concatenate every source item's block (in grouping order) to form the full task body. Call `wiki._client.upsert_task(wiki_path, slug, title=title, brief=brief, body=body)` per new task (or `upsert_tasks_batch` for all of them in one commit — match the "optionally batch" framing in `mill-ghissues-to-tasks/SKILL.md` Step 5). For each fold-in: `wiki._client.get_task(wiki_path, target_slug)`; if `None`, record an error and continue; re-check the unclaimed-only guard (status could have changed since Step 3) and record an error + continue if it now fails; otherwise build the same per-item bullet block (Sources bullet + optional detail-hint + optional body) for the single folded-in item and append it to `task["body"] or ""`, then call `upsert_task(wiki_path, target_slug, body=new_body)`.
  - **Step 6 — Write results.** After all wiki writes succeed, write `.scratch/triage-result.json` as a JSON array, one entry per consumed item (new-task and fold-in items only — skipped items are NOT listed): `{"ref": <item ref>, "route": "new_task", "slug": <slug>}` or `{"ref": <item ref>, "route": "fold_in", "slug": <target_slug>}`. This is the only file the calling entry skill reads back to learn what happened.
  - **Step 7 — Report.** Print a one-line summary: counts of new tasks created, fold-ins appended, skipped items, and any fold-in errors from Step 5 (target not found / guard re-check failed).
  - **Rules section** (mirror `mill-ghissues-to-tasks/SKILL.md`'s `## Rules` section): one-shot model — no resumable state, the proposal file is the only intermediate artefact, feedback loops by revising and re-presenting; skipped items are untouched (no wiki write, nothing to undo); writes only happen after explicit `approve`; unclaimed-only guard is non-negotiable; this skill never imports or shells out to `gh` and never branches on `contract["source"]` anywhere in its logic — that is the one invariant the whole task exists to enforce.
- **Commit:** `feat(mill-triage-to-tasks): add source-agnostic triage analysis skill`

## Batch Tests

`verify: null` — pure skill/markdown batch with no runnable surface, consistent with `_mill/discussion.md` Testing: "No unit tests planned for the markdown-orchestrated skill steps." Manual end-to-end verification happens once batches 3 and 4 (the entry skills that actually invoke this one) exist — see those batches' `## Batch Tests`.
