# Discussion: Track _mill/briefs/ instead of gitignoring them

```yaml
task: Track _mill/briefs/ instead of gitignoring them
slug: track-task-briefs
status: discussing
parent: main
```

## Problem

In agent-dispatch mode the `--stage prepare` step of the dispatch CLIs renders a
**brief** — the exact prompt sent to an implementer/reviewer/fixer/merge sub-agent —
to `_mill/briefs/<role>-<scope>-r<round>.md`, and the orchestrator writes the agent's
response next to it. These briefs + responses are the full audit trail of what each
sub-agent saw and said. Every other piece of task state under `_mill/`
(`status.md`, `plan/`, `reviews/`) is committed on the task branch and preserved under
the `archive/<slug>` tag after merge — briefs are the odd exception: they are never
committed, show up only as `?? _mill/briefs/` in `git status`, and are silently
discarded when `/mill-cleanup` removes the worktree. The user wants briefs preserved
like reviews are.

**Why now:** surfaced while finalizing `revise-ghissues-to-tasks`, the first
agent-dispatch mill-go run on this machine. The task was later widened (proposal
"Scope addition 2026-06-08") because the *reason* briefs were never tracked was their
size: review briefs were ~100 KB each because the bulk reviewer mode inlines all
reviewed source into the prompt. Now that dispatch is Claude Code Agent-tool mode, a
reviewer can use Read/Grep/Glob to fetch exactly the source it needs, so bulking is no
longer necessary. Removing bulking shrinks briefs enough to track unconditionally — so
the two halves are one task.

**Correction to the proposal's stale premise:** the proposal states briefs are *today*
gitignored at `.gitignore:40`. That is **no longer true** on this branch. The
working-tree and `main` `.gitignore` contain no briefs rule (only `**/_mill/*.active`),
`_gitignore.GLOB_ENTRIES` never listed briefs, and a freshly written brief shows as
`?? _mill/briefs/` (untracked, **not** ignored; `git check-ignore` exits 1). So the
"remove the gitignore line" step is already done — the remaining Part-A work is purely
to *commit* the briefs.

## Scope

**In:**

- **Commit briefs + responses on the task branch.** Every orchestrator that dispatches
  an agent and writes a brief adds `_mill/briefs/` to the pathspec of the `_mill/`
  state commit it already makes, so briefs become tracked task state. Orchestrators:
  mill-start (discussion-review), mill-plan (plan-review), mill-go
  (implement / code-review / fix), mill-merge-in (merge-conflict).
- **Rename the agent response file** from `<brief>.md.out` to `<role>-<scope>-r<N>.out.md`
  so it is a valid, editor-renderable Markdown file. Single source of truth:
  mill-go/SKILL.md `## Agent-mode dispatch` (steps 4 and 5).
- **Flip the reviewer naming convention across the *entire* `mill-agents.yaml`
  catalogue:** unsuffixed name = tool-use (default, explicit `tooluse: true`);
  `<name>_bulk` = bulk (`tooluse: false`). Delete every `_tool` suffix (fold into the
  unsuffixed name). Provide a `_bulk` twin for every model/effort so the scheme is
  fully symmetric — no mixed naming formats.
- **Point all reviewer roles at tool-use names** in `mill-config.yaml` (template + hub).
  No role uses bulk.
- **Demote (not delete) the bulk code path.** Keep `_read_for_bulk`, `run_bulk`, the
  bulk artefact-assembly, and the large-prompt `tooluse` override; they remain reachable
  only via `_bulk` agents.
- **Update tests** that reference renamed reviewers (`_test_registry.py` ×2,
  integration tests ×3); add the two regression tests named under Testing.

**Out:**

- Removing/deleting the bulk code (`_read_for_bulk` / `run_bulk` / bulk assembly) — it
  is retained as the `_bulk` opt-in.
- Touching `.gitignore` / `_gitignore.GLOB_ENTRIES` — briefs are already un-ignored.
- The pre-merge cleanup logic — mill-merge's `git -C <worktree> rm -r _mill/`
  (mill-merge/SKILL.md:89) already sweeps *all* tracked `_mill/` content into the squash
  diff and the archive tag; tracked briefs are handled by it automatically with no
  change.
- `bulk_timeout` / `max_implementer_prompt_chars` config keys — retained for the bulk
  opt-in.
- Per-machine `.millhouse/agents.local.yaml` overlays (gitignored, not a deliverable).
- Any user-code repo impact — scope is millhouse tooling only.

## Decisions

### gitignore-already-removed

- Decision: do **not** modify `.gitignore` or `_gitignore.py`; only commit the briefs.
- Rationale: briefs are already not ignored on this branch (`_gitignore.GLOB_ENTRIES`
  has no briefs entry; `git check-ignore _mill/briefs/x.md` exits 1; a written brief is
  `??` untracked). The proposal's `.gitignore:40` premise is stale.
- Rejected: re-removing a nonexistent line.

### commit-briefs-orchestrator-side

- Decision: each orchestrator folds `_mill/briefs/` into the `git add` pathspec of the
  `_mill/` state commit it already makes (per batch / per round / at handoff). No new
  dedicated commit; no CLI-side commit.
- Rationale: the SKILLs already write the response file and already commit `_mill/`
  state, so this is the least-invasive hook; incremental commits preserve the audit
  trail even if a run dies mid-way.
- Rejected: (a) CLI `--stage finalize` stages+commits itself — spreads git mutation
  into the CLIs, which today only emit JSON envelopes; (b) one sweep commit at handoff —
  loses briefs if the run aborts before handoff.

### track-both-brief-and-response

- Decision: track both the `.md` brief (prompt sent) and the response file.
- Rationale: the audit trail is "what each sub-agent saw *and said*"; both halves
  matter.

### response-filename-out-md

- Decision: the response file is `<role>-<scope>-r<N>.out.md`, not `<brief>.md.out`.
- Rationale: `.md.out` is not a Markdown file and renders as plain text; `.out.md` is a
  valid Markdown file the user can read in an editor.
- Implementation: in mill-go/SKILL.md `## Agent-mode dispatch`, the response path is the
  brief path with the trailing `.md` replaced by `.out.md` (e.g.
  `Path(brief).with_suffix(".out.md")`); the same path is passed to `--agent-output`.
  The CLIs need no change — they receive `--agent-output <path>` as a parameter and do
  not hardcode `.out`.
- Rejected: keeping `.md.out`.

### tool-use-is-the-default-name

- Decision: across the whole `mill-agents.yaml` catalogue, the unsuffixed name is the
  tool-use variant (explicit `tooluse: true`); the `_bulk` suffix marks the bulk variant
  (`tooluse: false`). Every `_tool` suffix is deleted and folded into the unsuffixed
  name. Every model/effort gets a symmetric `<name>` + `<name>_bulk` pair.
- Rationale: tool-use is now the norm and bulk the exception; the naming must reflect
  that uniformly. A partial flip (only `sonnetmax`) would leave a mix of
  `_tool`-suffixed-tool-use and unsuffixed-bulk entries — exactly the inconsistency to
  avoid.
- Rejected: (a) flipping only `sonnetmax` (proposal's original minimal scope) — leaves
  mixed formats; (b) flipping the code default in `_reviewers.py` to `tooluse=True` and
  omitting the flag on base entries — the proposal asks for an explicit `tooluse: true`
  on each tool-use definition, and an explicit flag is self-documenting; keep the code
  default `False` (defensive).

### keep-bulk-as-opt-in

- Decision: retain the bulk code path; it is reachable only through `_bulk` agents,
  none of which any role references today.
- Rationale: cheap escape hatch if a future reviewer needs inlined source; deleting it
  is a large, irreversible diff touching the LLM provider for no present benefit.
- Rejected: deleting `_read_for_bulk` / `run_bulk` / bulk assembly entirely.

### retire-sonnetmax_tool

- Decision: delete `sonnetmax_tool` (and all `*_tool` names); update every in-repo
  reference to the new unsuffixed name. No back-compat alias.
- Rationale: every reference is in-repo (templates, hub config, 3 integration tests,
  2 `_test_registry.py`); no external config needs the old name.

## Technical context

**How tooluse drives bulk vs tool-use.** A reviewer's `tooluse` boolean (from its
`mill-agents.yaml` spec) selects behaviour: `_reviewer_single.py:59` picks
`llm.run_tool_use` when `tooluse` else `llm.run_bulk`. The prepare stage independently
branches on it: `_review_code.py:300` sets `mode = "tool-use" if spec.get("tooluse")
else "bulk"`, and `_build_artefact_section(mode, …)` inlines file bodies via
`bulk_files()` / `bulk_files_with_diff()` (`_review_code.py:165-168`) only in bulk
mode. **Consequence: flipping reviewers to `tooluse: true` stops bulking automatically —
no bulk-removal code change is required;** the bulk assembly simply stops being reached.
`_reviewers.py:385-386` defaults `tooluse` to `False` when absent — keep that default;
make every tool-use entry set `tooluse: true` explicitly.

**`<TOOL_RULE>` block** is mode-specific (`_review_common.py:1008-1019`,
`build_tool_rule`): bulk mode tells the reviewer everything is inline; tool-use mode
grants Read/Grep/Glob. Driven by the same `mode`, so it follows the flip for free.

**Large-prompt override** (`_review_common.py:1092-1099`) preserves the original
`tooluse` when swapping to a larger-context override — relevant only to bulk agents now;
no change needed.

**Brief writing.** `_agent_dispatch.write_brief(briefs_dir, role, scope, round_n,
prompt_text)` writes `briefs_dir/<role>-<scope>-r<round_n>.md` (creating
`_mill/briefs/`), returns the path; `_implementer_common.emit_prepare` wraps it and
emits the prepare JSON envelope with `brief_path`. `briefs_dir` is resolved via
`_paths.resolve_task_path(project_root, "_mill/briefs/")` in millpy-implement.py:258,
millpy-fix.py:315, millpy-merge-in-subagent.py:239/284, and the review CLIs.

**Response writing & finalize.** The orchestrator SKILL writes the agent's final
message to the response file (mill-go/SKILL.md:123) and passes it to the CLI
`--stage finalize --agent-output <path>` (mill-go/SKILL.md:125). The CLIs read it via
`_implementer_common` / `agent_output_path.read_text` and do not construct the filename.
mill-plan and mill-start reference mill-go's `## Agent-mode dispatch` pattern rather than
duplicating it, so changing the response filename there is a single-source change.

**Cleanliness is unaffected.** `_cleanliness.py:54-71` (`compute_scope_violations`)
flags untracked files only *outside* `_mill/` (line 66 `if not
path.startswith("_mill/")`). Tracking briefs turns them from untracked into committed —
neither state is a violation. No assumption that `_mill/briefs/` is untracked exists.

**Pre-merge cleanup.** mill-merge's cleanup commit is `git -C <worktree> rm -r _mill/`
(mill-merge/SKILL.md:89; documented :276). Once briefs are tracked, this removes them
from the branch tip before the squash (so they are absent from the squash diff /
`main`) while the `archive/<slug>` tag retains them. This is exactly the desired
preservation behaviour and needs no change — but verify it during implementation.

**Naming-flip blast radius (rename `sonnetmax_tool`→`sonnetmax`, `sonnetmax`→
`sonnetmax_bulk`, and the analogous flip for every model):**

- `plugins/mill/templates/mill-agents.yaml` — the catalogue itself (rewrite to the
  symmetric `<name>` + `<name>_bulk` scheme; add explicit `tooluse: true` to every
  tool-use entry, `tooluse: false` to every `_bulk` entry).
- `plugins/mill/templates/mill-config.yaml` — roles at lines ~134 (`sonnetmax_tool`),
  ~145 (`sonnetmax`), ~157 (`sonnethigh`).
- `mill-config.yaml` (hub) — discussion-review:holistic `sonnetmax_tool` (:33),
  plan-review:holistic `sonnetmax` (:40), code-review:holistic `sonnethigh` (:47),
  `merge.model: sonnethigh` (:20). All reviewer roles → tool-use names.
- `plugins/mill/integration_tests/test-review-code.py` (:65, :69-70),
  `test-review-discussion.py` (:60, :64-65), `test-review-plan.py` (:61, :65-66).
- `plugins/mill/unit_tests/_test_registry.py` and `plugins/mill/scripts/_test_registry.py`
  (:38 `sonnetmax`, :44 `sonnetmax_tool`) — update baseline specs to `sonnetmax`
  (tool-use) + `sonnetmax_bulk` (bulk).

**Current catalogue → target.** Existing entries: `g25flash`/`g25flash_tool`,
`g25pro`/`g25pro_tool`, `g3flash_preview`/`g3flash_preview_tool`, `haiku`, `opushigh`,
`opusmax`, `opusmedium`, `sonnethigh`, `sonnetmax`/`sonnetmax_tool`, `sonnetmedium`.
Target: for each of the 10 distinct model/effort combos, one tool-use base entry
(`tooluse: true`) + one `_bulk` twin (`tooluse: false`); all `_tool` names removed.

**merge.model & implementer/fixer models.** `merge.model: sonnethigh`,
`implementer.model: haiku`, `fixer.model: haiku` reference catalogue names too. After
the flip these names still exist (as tool-use defaults). Verify that the `tooluse`
field is irrelevant to non-reviewer dispatch (implementer/fixer/merge), or harmless if
read — the implementer/fixer are not bulk reviewers.

## Constraints

- ASCII-only `print`/`_log` output (Windows cp1252).
- `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths; template and hub `mill-config.yaml`
  must stay in sync (template seeds new hubs) — applies equally to `mill-agents.yaml`.
- Generated Markdown uses fenced ` ```yaml ` blocks, not `---` frontmatter.
- No `CONSTRAINTS.md` at the hub root.

## Testing

Python project (`uv run --project plugins/mill`; unit tests under
`plugins/mill/unit_tests/`, integration under `plugins/mill/integration_tests/`).
Plan `verify:` commands must start with `PYTHONPATH=` (empty) per CLAUDE.md.

- **Update existing tests** that reference renamed reviewers: both `_test_registry.py`
  baselines and the three integration `test-review-*.py` configs — switch
  `sonnetmax_tool`→`sonnetmax`, `sonnetmax`(bulk)→`sonnetmax_bulk`, and any other
  renamed name. These must pass after the rename.
- **Regression test 1 — no bulked bodies in tool-use briefs:** with a `tooluse: true`
  reviewer spec, assert the prepared brief/artefact section contains no inlined source
  file bodies (only the tool-use `<TOOL_RULE>` and file references). Exercises
  `_review_code.py` prepare + `_build_artefact_section("tool-use", …)` /
  `build_tool_rule("tool-use")`. In-memory/tempfile fixture; no real git/LLM.
- **Regression test 2 — briefs stay un-ignored:** assert `_gitignore.GLOB_ENTRIES`
  contains no `_mill/briefs` entry (locks in the already-correct state so a future
  managed-block regeneration can't silently re-ignore briefs).
- **Bulk path still reachable:** assert a `tooluse: false` (`*_bulk`) spec still selects
  `run_bulk` (`_reviewer_single`) and bulk-mode assembly — proves the demotion didn't
  break the opt-in.
- **Catalogue sanity:** a test asserting every `mill-agents.yaml` entry follows the
  scheme (unsuffixed ⇒ `tooluse: true`; `_bulk` ⇒ `tooluse: false`) would lock the
  convention; include if an existing catalogue-loading test makes it cheap.
- **Briefs-commit behaviour** is orchestrator-SKILL logic (not a Python unit); no new
  Python test for it. The integration test that runs a real mill-go batch and asserts
  `_mill/briefs/*.md` + `*.out.md` are committed is **out of scope** (chosen Q8 option 1
  — unit + targeted regression only).

## Q&A log

- **Q:** Full proposal scope, or just one half? **A:** Full — commit briefs+responses
  *and* the tool-use/bulking/naming flip. Brief size is driven by bulking, so the two
  are one change.
- **Q:** Where to commit briefs? **A:** Orchestrator-side, folded into the `_mill/`
  state commits each SKILL already makes (not CLI-side, not a single handoff sweep).
- **Q:** Track brief, response, or both? **A:** Both — but rename the response from
  `.md.out` to `.out.md` so it is a readable Markdown file.
- **Q:** Any reviewer role keep bulk? **A:** No — all reviewers tool-use; `*_bulk`
  entries exist but are unused.
- **Q:** Retire `sonnetmax_tool` — delete or alias? **A:** Delete; update all ~9 in-repo
  references. No alias.
- **Q:** Keep or delete the bulk code path? **A:** Keep, demoted to the `_bulk` opt-in
  (proposal "demote, don't delete").
- **Q:** How broad is the naming flip? **A:** The *entire* catalogue — Opus, Sonnet,
  Gemini, every model. Tool-use is the unsuffixed default everywhere; bulk is always
  `_bulk`-suffixed. No mixed naming formats.
- **Q:** Testing depth? **A:** Unit + targeted regression: fix renamed-reviewer tests,
  add the no-bulked-bodies test and the `_gitignore` lock test. No real-mill-go
  integration test.
```
