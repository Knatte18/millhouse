# Batch: plan-guardrails-and-anti-pause

```yaml
task: 'mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check'
batch: plan-guardrails-and-anti-pause
number: 2
cards: 4
verify: null
depends-on: [1]
```

## Batch Scope

This batch makes four prose-only edits across two SKILL.md files: mill-plan's Phase: Plan gains a Fork scope guardrail (#741, Card 3); mill-plan's Phase: Plan Review and mill-go's shared Agent-mode dispatch section each gain the same one-line anti-pause rule (#743, Cards 4-5); and mill-plan's Step 1.5 fix table gains the `context-completeness` row (#742, Card 6). All four are grouped in one batch because #741 and #743 both edit `plugins/mill/skills/mill-plan/SKILL.md` — splitting them across non-dependent batches would trip `_check_parallel_modifies_overlap` (see the "Batch ordering and same-file consolidation" Shared Decision in `00-overview.md`). This batch depends on Batch 01 so Card 6 documents Batch 01's actual, already-implemented `_check_context_completeness` behavior.

## Cards

### Card 3: Add "Fork scope guardrail" to mill-plan/SKILL.md Phase: Plan

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-plan/SKILL.md`'s `### Phase: Plan` section, insert a new bolded-paragraph subsection immediately after the paragraph ending "...this is exactly where the planning budget pays off." (line 45) and before the "**Batch sizing.**" paragraph (line 47), matching the existing bold-paragraph-header style used by "**Batch sizing.**", "**Write the files.**", etc. in this same phase.

  The new paragraph, headed "**Fork scope guardrail.**", must state:
  - mill-plan has no fork-dispatch guidance today; prefer a cold, non-fork agent (`Explore`, or `general-purpose` when the research needs a tool beyond Explore's read-only grant) over `Agent(subagent_type: "fork")` whenever the research does not genuinely need the parent's already-in-context reasoning. Cite that `Explore`'s tool grant excludes `Edit`/`Write`/`Bash`-mutation (making unauthorized writes to shared plan/config state structurally impossible), whereas a fork always inherits the parent's full tool access — cite the "Why not fork?" paragraph in `plugins/mill/skills/mill-go/SKILL.md`'s "## Agent-mode dispatch" section (line 199) for that inheritance behavior.
  - Reserve `Agent(subagent_type: "fork")` for research that genuinely depends on the parent's in-flight reasoning to be useful. When a fork IS used under that narrower justification, all of the following apply:
    (a) The fork's prompt must explicitly forbid Edit/Write calls, forbid mutating Bash commands, and forbid touching `plan_dir`, `status_path`, or any `mill-config.yaml`/`config.local.yaml`.
    (b) Immediately BEFORE dispatching the fork, capture a `git status --porcelain` snapshot (scoped to the worktree) as a baseline. This is necessary because Phase: Plan's only commit happens at the very end (cite the "**Commit on the task branch.**" step, line 107), so the orchestrator's own in-progress, not-yet-committed plan files are routinely dirty in the working tree at fork-dispatch time — a bare post-return snapshot cannot distinguish that legitimate dirt from a fork's unauthorized writes.
    (c) Immediately AFTER the fork returns, run `git status --porcelain` again and diff it against the pre-dispatch baseline. Treat only entries that are NEW in the post-return snapshot as a scope violation; the fork's report is not trusted until this diff is empty.
    (d) On a detected violation, revert the unauthorized changes (`git checkout --` / delete untracked files as appropriate) before proceeding, and never silently incorporate a fork's unauthorized writes into the plan.
    (e) When multiple research investigations are needed, dispatch them serially, not in parallel — complete one dispatch and confirm a clean git-status diff before starting the next. Serial dispatch is the only sanctioned path for concurrent research forks in mill-plan; state explicitly that there is no `isolation: "worktree"` fallback for parallel dispatch, since the Agent tool's `isolation` parameter's accepted values and exact semantics are not documented anywhere in this repo (only that the parameter exists).
- **Commit:** `docs(mill-plan): add fork scope guardrail to Phase: Plan (#741)`

### Card 4: Add anti-pause rule to mill-plan/SKILL.md Phase: Plan Review

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-plan/SKILL.md`'s `### Phase: Plan Review` section, step 2 (the line beginning "2. **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`.", line 161), prepend the following as a new bolded lead-in sentence within the same numbered list item, before "**Dispatch mode:**": "**Waiting is never a decision point.** Waiting on this dispatch — either branch — is never a decision point: state in one sentence what you're waiting for, then wait. `AskUserQuestion` (or any equivalent free-text operator prompt) is banned here absent one of this phase's explicitly named escape hatches (the max-rounds prompt in step 6, the non-progress halt in step 5)." Leave the remainder of step 2 (the `_agent_dispatch.resolve_dispatch_mode(cfg)` call and everything after it) unchanged. Do not cite `mill:conversation`'s numbered-options rule here — neither `mill-plan/SKILL.md` nor `mill-go/SKILL.md` loads that skill anywhere (unlike `mill-start/SKILL.md`, which explicitly loads it at Step 0), so a citation to it would not be runtime-binding in this phase; the two named escape hatches already spell out their own numbered-option format inline in their own text.
- **Commit:** `docs(mill-plan): add anti-pause rule to Phase: Plan Review (#743)`

### Card 5: Add anti-pause bullet to mill-go/SKILL.md Agent-mode properties

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-go/SKILL.md`'s "## Agent-mode dispatch" section, "**Agent-mode properties:**" bullet list (lines 173-179), add a new bullet immediately after the last existing bullet (the `incomplete` stuck-errors bullet, line 178): "- Waiting on a dispatch — either branch — is never a decision point: state in one sentence what you're waiting for, then wait. `AskUserQuestion` (or any equivalent free-text operator prompt) is banned here absent an explicitly named escape hatch for the calling phase." Do not add this rule inside the shared dispatch steps (1-7) themselves — only this bullet list — since those steps are reused by non-review Implement/Fix/merge-in dispatch, where each phase's own stuck-escalation rules already govern waiting. Do not cite `mill:conversation` here either, for the same reason given in Card 4.
- **Commit:** `docs(mill-go): add anti-pause rule to Agent-mode properties bullet list (#743)`

### Card 6: Add `context-completeness` fix-table row to mill-plan/SKILL.md Step 1.5

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-plan/SKILL.md`'s Step 1.5 fix table (lines 130-153), insert a new row for the `context-completeness` check (implemented by Batch 01's `_check_context_completeness`) immediately after the `plugin-manifest-context-missing` row (line 145) and before the `verify-not-isolated` row (line 146). The row's mechanical-fix cell must read: "Add the referenced file to the card's `Context:` list (unless the card's own `Edits:`/`Creates:`/`Deletes:`/`Moves:` already covers it, in which case re-verify the check's own-list cross-reference before editing — the 'add to Context:' remedy applies only when the token is absent from all five fields; a token that legitimately belongs to `Deletes:`/`Moves:`-source means the check should not have fired at all)."
- **Commit:** `docs(mill-plan): add context-completeness fix-table row (#742)`

## Batch Tests

`verify: null` — these are prose/skill-text changes with no directly testable runtime behavior in this repo's unit-test suite (`mill-plan` and `mill-go` are interactive orchestration skills, not scripts under `plugins/mill/scripts/`). Verification is a careful read-through during plan review against the `mill-receiving-review` decision tree and the exact wording specified in each card's `Requirements:`.
