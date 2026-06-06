# Discussion: Revise mill-ghissues-to-tasks to present all at once

```yaml
task: Revise mill-ghissues-to-tasks to present all at once
slug: revise-ghissues-to-tasks
status: discussing
parent: main
```

## Problem

`/mill-ghissues-to-tasks` currently drains the open GitHub issue queue **one
issue at a time**: for every open issue it shows the issue, presents a
new/fold/skip menu, and waits for the operator to decide before moving to the
next. For a queue of more than a handful of issues this is tedious, and it
biases toward a 1:1 issue → task explosion that fragments naturally-related
work into many tiny backlog entries.

The operator wants the skill to instead analyse the **whole** open-issue set,
propose a natural grouping into a **small number of tasks (typically 2-3,
regardless of issue count)**, present that as a single proposal, and apply it
on **one combined approval**. Each created task must record its source issue
numbers in the task body so that a later implementer thread can pull full
context with `gh issue view #N` rather than having the issue text duplicated
into the wiki. **Why now:** the per-issue interaction is the live friction the
operator is removing; this task rewrites the skill spec to the batch model.

## Scope

**In:**

- Rewrite `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` to the
  all-at-once model: fetch all issues, assistant proposes a grouping
  (new grouped tasks + fold-ins + skips), one combined approval, then apply.
- Update that skill's frontmatter `description:` to describe the new model
  (it currently says "Proposes a task per issue").
- Keep the SKILLS.md index row in sync with the new frontmatter description
  (root `SKILLS.md`, line 45). It is a generated file (`/mill-skills-index`),
  but the row must match the new description so the index is not stale.
- Replace the per-issue interactive Step 3 with a grouping-analysis step.
- Rewrite Step 4 (proposal artifact) so a single `.scratch/` proposal lists
  all grouped tasks, fold-ins, and skips for one approval.
- Rewrite Step 5 (apply) to create the grouped tasks (each with a Sources
  manifest body), perform fold-ins, and close all consumed issues.
- Rewrite Step 6 (report) and the Rules section to match the batch model.

**Out:**

- No changes to `plugins/mill/scripts/_gh_issues.py` — `fetch`,
  `close_with_comment`, and `detect_repo` already provide everything
  (`fetch` returns all open issues with `{number, title, body, labels,
  createdAt}`, body already includes rendered comments).
- No changes to the wiki client (`wiki/_client.py`) or render
  (`wiki/_render.py`) — `upsert_task`/`upsert_tasks_batch`/`get_task`/
  `list_tasks_brief` already support multi-task creation and multi-`Sources`
  bodies.
- No changes to `/mill-fold`, `/mill-add`, `/mill-groom`, or `/mill-autofix`.
- The close-comment strings and the locked-phase fold guard are **not**
  redesigned — they are preserved verbatim (see Decisions).
- No new resumable/intermediate state — the skill stays one-shot.
- No automated GitHub label scheme — skipped issues remain untouched.

## Decisions

### all-at-once grouping (the core change)

- Decision: After fetching every open issue, the assistant analyses the full
  set and proposes a grouping of related issues into a small number of tasks,
  presented as a single proposal. The operator no longer decides issue by
  issue.
- Rationale: This is the explicit ask. Grouping related issues into a coherent
  task is the work the operator wants the assistant to do up front.
- Rejected: Per-issue menu (the current behaviour) — the thing being removed.

### action set: new + fold + skip (one proposal)

- Decision: The single proposal may, per issue, route it into a **new grouped
  task**, **fold it into an existing backlog task**, or **skip** it. All three
  appear in one proposal approved in one go. Fold targets still obey the
  locked-phase guard (below).
- Rationale: Folding into existing backlog work and skipping non-actionable
  issues are both still valuable; collapsing them into the same one-shot
  approval keeps the batch model coherent.
- Rejected: new+skip only, or new-only — both drop useful routing the current
  skill already supports.

### task-count guidance: soft 2-3, natural grouping

- Decision: "Typically 2-3 tasks regardless of issue count" is **soft
  guidance**, not a hard cap. The assistant uses judgment: do not force
  unrelated issues into one task, and do not over-split tightly-related ones.
- Rationale: The right number follows the natural theme structure of the
  queue; a hard cap would mis-group on atypical queues.
- Rejected: hard cap at 3 (mis-groups when >3 distinct themes exist);
  no guidance at all (loses the operator's stated default).

### body format: brief theme + Sources manifest + fetch hint

- Decision: For each grouped **new** task:
  - `brief` (the Home.md summary) = a synthesised 1-2 sentence statement of the
    group's theme.
  - `body` = one `- Sources: #N — <issue title>` bullet per source issue (the
    exact line format `/mill-fold` uses), plus a one-line hint instructing the
    implementer to run `gh issue view #N` for full detail.
- Rationale: The operator wants references in the body so the implementer pulls
  live issue content rather than reading a stale copy. The `- Sources: #N — …`
  format matches `/mill-fold` so fold-ins and grouped tasks read identically.
- Rejected: Sources bullets with no theme/fetch hint (less navigable);
  embedding full rendered issue bodies inline (duplicates content that
  `gh issue view` already serves, and goes stale).

### body ⟶ proposal-<slug>.md (render-model reconciliation)

- Decision: The Sources manifest lives in the task `body`. Per
  `wiki/_render.py`, a non-empty `body` renders to `proposal-<slug>.md` and the
  Home.md slug line becomes a link to that file; `brief` is what renders inline
  in Home.md. So every grouped task gets a **minimal** `proposal-<slug>.md`
  whose entire content is the Sources manifest + fetch hint. This is the same
  mechanism `/mill-fold` uses to persist its Sources bullet.
- Rationale: This is the only place issue references can live such that they
  survive into the wiki and are reachable by a spawned implementer. It is
  consistent with the operator's "references in body" requirement.
- Rejected: putting Sources into `brief` (the template reserves `brief` for a
  prose paragraph, and a bullet list of `#N` refs renders badly inline);
  inventing a new wiki field (out of scope — no client/render changes).

### proposal docs: no long-form narrative by default

- Decision: Beyond the minimal Sources-manifest body above, the assistant does
  **not** author a long-form `proposal-<slug>.md` narrative by default. It may
  expand a group's body into a fuller proposal only when the group is large or
  complex, and that expansion is shown in the proposal for approval.
- Rationale: The implementer fetches full detail from the issues themselves via
  `gh issue view`; a hand-written narrative would duplicate and decay.
- Rejected: always write a proposal narrative (redundant with the issues);
  never write any body (impossible — body is how Sources are persisted).

### one combined approval; reject iterates

- Decision: The assistant writes the consolidated proposal to
  `.scratch/ghissues-to-tasks-proposal.md`, prints a one-line summary + path,
  and the operator replies `approve` or gives feedback. The proposal artifact
  must surface, per consumed issue, the **exact** close-comment string that
  will be posted on approval — `Consolidated into wiki task: <slug>` for
  new/grouped-task issues and `Folded into wiki task: <slug>` for fold-ins —
  so the single approval covers the precise GitHub side effects (skipped
  issues show no close comment — untouched). "One-shot" means **no
  per-issue prompting**, not no iteration: on rejection the operator gives
  feedback, the assistant revises the grouping and re-presents the full
  proposal, looping until `approve` or an explicit abort. Nothing is written to
  the wiki and no issue is closed until `approve`.
- Rationale: Batch judgment benefits from a correction round; the invariant
  that matters is "no side effects before approval", which is preserved.
- Rejected: reject = abort the whole run (forces a full re-fetch and
  re-analysis for a small grouping tweak).

### slug/title drafted by assistant, editable at approval

- Decision: The assistant drafts every grouped task's slug, title, and brief in
  the proposal. The operator can amend any of them as part of the single
  approval (e.g. "approve but rename `x` to `y`"). There is no per-task
  slug/title prompt. Slugs must match `[a-z][a-z0-9-]*` and must not collide
  with an existing task slug (re-draft on collision).
- Rationale: Drafting is exactly the assistant judgment the batch model is
  meant to provide; the single approval is the operator's edit point.
- Rejected: prompt per task for slug/title (reintroduces the per-issue cadence
  the task removes).

### preserved invariants (close comments + locked-phase guard)

- Decision: Carry these over **unchanged** from the current skill:
  - New / grouped-task issues close with `Consolidated into wiki task: <slug>`.
  - Fold-in issues close with `Folded into wiki task: <slug>` — this string
    MUST match `/mill-fold`'s comment verbatim.
  - Skipped issues are untouched: no comment, no label, no close.
  - Fold targets in a locked phase are refused. The locked set is
    `{"active", "ready-to-merge", "pr-pending"}` — inline it, never duplicate it
    as a redefinition; it is the source of truth.
  - Close only after the wiki write succeeds; never close before the task is
    committed.
- Rationale: These invariants are correct today and other skills (`/mill-fold`)
  and historical closed-issue comments depend on the exact strings.
- Rejected: changing any string or relaxing the guard — pure regression risk
  for no benefit.

## Technical context

This is a **SKILL.md-only** change. The supporting library and wiki client are
already sufficient; mill-plan should write the plan against the existing APIs
below and must not modify them.

- `_gh_issues.fetch(repo=None, limit=100, label_filter=None, git_root=None)`
  → `list[dict]`, each `{number, title, body, labels, createdAt}`; `body`
  already has rendered comments appended (cap 10). Use it once to get the whole
  queue for grouping analysis.
  (`plugins/mill/scripts/_gh_issues.py`)
- `_gh_issues.detect_repo(git_root=...)` → `owner/repo` for the close step.
- `_gh_issues.close_with_comment(number, comment, git_root=...)` — posts the
  comment then closes; raises `GhError` on failure. Apply step loops over
  consumed issues and continues-on-error, reporting failures at the end.
- `wiki/_client.list_tasks_brief(wiki_path)` → `[{id, slug, title, layer,
  brief, status, has_proposal}]` — used for overlap detection (fold
  candidates) and slug-collision checks.
- `wiki/_client.get_task(wiki_path, id_or_slug)` → full task dict incl. `body`
  and `status`, **or `None` when the slug is unknown**. Fold-in path: call
  `get_task`, and if it returns `None` (stale/typo'd fold target) abort that
  fold-in with a clear error and continue the run rather than dereferencing
  `None["status"]`; otherwise read `body`, append the `- Sources: #N — title`
  bullet, write back; locked-phase guard reads `status`. Fold targets are
  drawn from `list_tasks_brief`, so in normal flow the slug exists — the guard
  is defensive against an operator-edited proposal.
- `wiki/_client.upsert_task(wiki_path, slug, *, title, brief, body, ...)` —
  creates/updates one task; the daemon commits + pushes automatically (one
  commit per call).
- `wiki/_client.upsert_tasks_batch(wiki_path, tasks, *, message=None)` —
  creates/updates multiple tasks in **one** commit. Optional optimisation for
  the apply step so all grouped new tasks land atomically; sequential
  `upsert_task` calls (as the current skill does) are also acceptable. Fold-ins
  still go through `get_task` + `upsert_task` because they read-modify-write an
  existing body.
- **Render model (load-bearing — `wiki/_render.py:166-192`):** a non-empty
  `body` ⟹ `proposal-<slug>.md` is written and the Home.md slug line becomes
  `[<slug>](proposal-<slug>.md)`; `brief` renders inline under the heading. The
  body-format decision depends on this.
- Locked-phase set `{"active", "ready-to-merge", "pr-pending"}` is defined once
  in the current skill/`/mill-fold`; reuse the wording, do not redefine it.
- `.scratch/` is the gitignored scratch dir for the issues dump and the
  proposal artifact (never `/tmp` or `$env:TEMP`).

Downstream interaction: a grouped task later goes through `/mill-spawn` →
`/mill-start`, where the discussion author/implementer reads the
`proposal-<slug>.md` Sources manifest and runs `gh issue view #N` per the fetch
hint to recover full context.

## Constraints

- No `CONSTRAINTS.md` at the hub root governs this change (checked; none
  relevant to skill-spec edits).
- Markdown generation rules apply to the SKILL.md edits (fenced ```` ```yaml ````
  for metadata, not `---` frontmatter — except the SKILL.md `---` frontmatter
  block itself, which is the manifest convention).
- ASCII-only in any example output strings shown in the skill (Windows cp1252):
  use ` -- ` and ` -> `. Note the existing `- Sources: #N — <title>` bullet
  uses an em dash and matches `/mill-fold`; keep that exact glyph for
  cross-skill string parity (it is data written to the wiki, not console
  stdout, so the cp1252 stdout rule does not apply to it).
- `${CLAUDE_PLUGIN_ROOT}` form for every script invocation in the rewritten
  skill (never `plugins/mill/...` literal paths), matching the cache-path
  convention already used in the current skill body.

## Testing

This task changes a SKILL.md (operator-facing prose) plus a one-line frontmatter
description and the matching SKILLS.md row. There is no Python behaviour change,
so there is **no unit/integration test to add** — the supporting library is
untouched and already covered.

Verification is documentation-consistency, not test execution:

- **Frontmatter ↔ index parity:** the new `description:` in the skill
  frontmatter matches the `SKILLS.md` row text exactly (the check
  `/mill-skills-index` would enforce). mill-plan should make verifying this row
  an explicit plan step.
- **Cross-skill string parity:** the fold-in close comment in the rewritten
  skill is byte-identical to `/mill-fold`'s (`Folded into wiki task: <slug>`),
  and the `- Sources: #N — <title>` bullet format matches `/mill-fold`.
- **Self-containment / internal consistency:** the rewritten skill's Steps
  1-6 + Rules describe one coherent flow (no leftover per-issue language), and
  every API call shown matches a real signature in `_gh_issues` / `_client`
  (the signatures enumerated in Technical context).
- **Locked-phase guard wording** present and referencing the canonical set
  without redefining it.

No TDD candidates (no code). The plan's "verify" for each batch is a
read-back/grep of the edited markdown confirming the above, not a test command.

## Q&A log

- **Q:** Which actions may the all-at-once proposal route issues to? **A:** New
  grouped tasks + fold-into-existing + skip, all in one approval (fold keeps the
  locked-phase guard).
- **Q:** How do grouped task bodies carry issue references? **A:** Synthesised
  brief theme + `- Sources: #N — <title>` bullets + a `gh issue view #N` fetch
  hint.
- **Q:** Is "typically 2-3 tasks" a hard cap? **A:** Soft guidance — natural
  grouping, assistant judgment, no hard limit.
- **Q:** Code scope? **A:** SKILL.md only (plus frontmatter description +
  SKILLS.md row); `_gh_issues` and the wiki client already suffice.
- **Q:** Long-form proposal docs per grouped task? **A:** No by default; body is
  the minimal Sources manifest. Assistant may expand for a large/complex group,
  shown in the proposal.
- **Q:** What happens on reject? **A:** Iterate — operator feedback, assistant
  revises and re-presents; loop until approve or abort. No wiki write / issue
  close before approve.
- **Q:** How are slugs/titles decided? **A:** Assistant drafts all in the
  proposal; operator edits any as part of the single approval. No per-task
  prompt.
- **Q:** (resolved during exploration) Doesn't a non-empty `body` create a
  `proposal-<slug>.md`, conflicting with "no proposal docs"? **A:** Yes by the
  render model — and that is intended: the minimal body *is* the Sources
  manifest file (same as `/mill-fold`). "No proposal docs by default" means no
  long-form narrative beyond that manifest.
```
