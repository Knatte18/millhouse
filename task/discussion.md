# Discussion: 16 (A) — Autonomous bug-fix pipeline (mill-autofix)

```yaml
task: "16 (A) — Autonomous bug-fix pipeline (mill-autofix)"
slug: mill-autofix-bugs
status: discussing
parent: main
```

## Problem

Mill now has multiple mechanisms for filing bugs to GitHub (mill-self-report, mill-issue, manual `gh issue create`). The backlog grows faster than manual fix throughput. Each bug currently requires seven manual steps: read the issue list, triage into the wiki, spawn a worktree, run mill-start (discussion), run mill-plan, run mill-go, run mill-merge. For most bugs the fix is mechanical and obvious from the issue body — forcing a full interactive triage and plan loop is wasteful.

The goal is a single skill invocation in a fresh thread that drains the `label:bug` queue autonomously: fetches open bugs, adds each to the wiki, and runs the full mill pipeline (claim → discussion.md synthesis → mill-plan → mill-go → mill-merge) per bug without human input. Stuck tasks are left as `[active]` for manual continuation. A summary report is written at the end.

## Scope

**In:**
- New `mill-autofix` skill at `plugins/mill/skills/mill-autofix/SKILL.md`
- `_gh_issues.py`: add `label_filter: list[str] | None = None` parameter to `fetch()`; filter in Python post-fetch
- `wiki/config.yaml`: add `pipeline.autonomous_mode: false` key with documentation
- `mill-plan` SKILL.md: handle `pipeline.autonomous_mode: true` — auto-block at max-rounds escape and non-progress halt instead of prompting the user
- `mill-go` SKILL.md: handle `pipeline.autonomous_mode: true` — auto-block at stuck-batch escalation and holistic-review-exhaustion prompts
- `plugins/mill/unit_tests/test-gh-issues.py`: add `label_filter` tests
- New `plugins/mill/unit_tests/test-autofix.py`: slug derivation tests
- Root-level `SKILLS.md`: regenerate via `millpy-skills-index.py`

**Out:**
- mill-start changes — mill-autofix bypasses mill-start entirely; discussion.md is synthesized inline by the mill-autofix session
- `millpy-autofix.py` standalone CLI script — all orchestration lives in SKILL.md
- Parallel or concurrent bug processing — sequential by design; one bug at a time
- `--group` flag for cross-bug clustering — one task per bug, always
- Enhancement or unlabeled issues — only `label:bug` issues are processed
- `millpy-discussion-from-issue.py` dedicated CLI — synthesis done inline by the skill session (no sub-LLM call)

## Decisions

### execution-model

- Decision: Mill-autofix is a single CC skill session that invokes `/mill-plan`, `/mill-go`, and `/mill-merge` as sub-skills via the Skill tool within the same session. No separate `claude -p` sub-sessions are spawned for lifecycle orchestration.
- Rationale: Mill-go already delegates heavy implementation work to external sub-sessions via `millpy-implement.py`. The mill-autofix session stays lean by handling lifecycle coordination only (claim, synthesize discussion.md, invoke sub-skills, read status, handle cleanup). Spawning additional sub-sessions per bug adds complexity with no isolation benefit given the sequential design.
- Rejected: spawning one `_llm_claude.run_implementer()` sub-session per bug — over-engineering for a sequential workload.

### discussion-md-synthesis

- Decision: Mill-autofix's own CC session reads the issue body (title + description + comments already merged by `_gh_issues.fetch`) and writes a fully structured `task/discussion.md` directly, exploring the codebase as needed. No sub-LLM call.
- Rationale: The mill-autofix session already has LLM capabilities and codebase access. For bug fixes, the scope is narrow enough that the session can explore the relevant code paths and produce a complete discussion.md in one pass. A sub-call would add latency and cost for no isolation benefit.
- Discussion.md must fill all template sections: Problem (from issue body), Scope (narrow: fix the reported behavior), Decisions (design choices for the fix), Technical context (requires Glob/Grep/Read codebase exploration per bug), Constraints (from `_constraints.read_if_exists()`), Testing (unit tests for affected module), Q&A log.
- Rejected: mill-start `--from-proposal` path (adds complexity to mill-start); direct verbatim copy of issue body (produces poor mill-plan input).

### autonomous-mode-flag

- Decision: New `pipeline.autonomous_mode: false` key in `wiki/config.yaml`. Mill-autofix sets `pipeline.autonomous_mode: true` in `.millhouse/config.local.yaml` at startup (saving the original value) and always restores it in a cleanup step (success or failure). Sub-skills read the deep-merged config and see `true` during the run.
- Rationale: Config.local.yaml is gitignored and local to the hub. Writing to it avoids modifying the shared wiki config.yaml mid-run. The always-restore cleanup prevents interactive sessions from seeing unexpected autonomous behavior after a crash (a comment in the written entry identifies mill-autofix as the writer).
- Config.local.yaml absent case: create it with just `pipeline.autonomous_mode: true`; restore by deleting the file.
- Rejected: env-var approach (sub-skills don't check env vars); modifying wiki/config.yaml directly (shared resource, multi-writer risk).

### label-filter-implementation

- Decision: Add `label_filter: list[str] | None = None` to `_gh_issues.fetch()`. Filter in Python post-fetch: keep issues where at least one label's `"name"` field is in `label_filter`. Mill-autofix calls `fetch(label_filter=["bug"])`.
- Rationale: `gh issue list --label` supports only one label and requires exact match. Python-side filtering handles multi-label "any-of" semantics and keeps the `gh` call unchanged.
- Rejected: passing `--label bug` to `gh issue list` directly — limited to one label, can't be generalised.

### slug-derivation

- Decision: Derive slug from issue title with this algorithm: lowercase → replace non-`[a-z0-9]` chars with `-` → collapse consecutive `-` → strip leading/trailing `-` → truncate to 30 chars (at last `-` boundary where possible). If the resulting slug already exists in Home.md: append `-<issue_number>`. Implemented as a helper inline in the skill instructions.
- Rationale: Title-derived slugs are human-readable in the wiki and commit history. Issue-number suffix is a stable fallback for collisions.
- Rejected: always `fix-<issue_number>` — stable but loses title semantics; LLM-derived slug — adds cost per bug.

### stuck-task-cleanup

- Decision: When mill-plan or mill-go sets `phase: blocked` in `task/status.md`, mill-autofix: (1) reads the blocked_reason from status.md, (2) runs `git checkout <parent_branch>` to return to the parent, (3) removes `.millhouse/active.slug.md`, (4) leaves the task branch (`hanf/<slug>`) alive for manual resumption, (5) leaves Home.md at `[active]`, (6) records the block in the report, (7) continues to the next bug.
- Rationale: Leaving the task branch alive lets the user resume with `/mill-go` after inspecting reviews. Home.md stays `[active]` since mill-plan/mill-go don't flip it on block (only the go Handoff flips to `[done]`).
- Rejected: deleting the task branch on stuck — loses implementation progress and review artefacts.

### issue-close-on-success

- Decision: After mill-merge completes, mill-autofix extracts the squash commit SHA via `git log --oneline -1 <parent_branch>` and calls `_gh_issues.close_with_comment(issue_number, f"Autonomously fixed by mill-autofix. Squash commit: {sha}")`.
- Rationale: Leaves no orphaned open issues. Consistent with the pattern already used by mill-ghissues-to-tasks.

### killswitch

- Decision: Mill-autofix checks for `.scratch/autofix-stop` after completing each bug (success or failure). If present, halt after cleanup and report. Do not delete the file — the user removes it manually.

## Technical context

**`plugins/mill/scripts/_gh_issues.py`** — `fetch()` currently at line 87. Add `label_filter` parameter. The `labels` field is already fetched from GitHub (present in each issue dict as `[{"id": ..., "name": "bug", ...}]`). Filter after parsing: `[i for i in issues if label_filter is None or any(l["name"] in label_filter for l in i.get("labels", []))]`.

**`plugins/mill/scripts/millpy-claim.py`** — `--slug <slug>` argument already supported (line 160). Exits 0 on success; exits 1 on failure. Writes `task/status.md`, `.millhouse/active.slug.md`, creates portal junction. The working tree must be clean or the dirty-tree prompt fires — mill-autofix must ensure no uncommitted changes before each claim.

**`plugins/mill/scripts/millpy-add.py`** — exits 1 with "Slug ... already present in Home.md" on collision. Mill-autofix must check the returned exit code and parse stderr to detect this. On collision: parse Home.md to find the existing task's phase marker; if `[active]` or `[done]`, skip; if unmarked, proceed with the claim (the add step was already done previously).

**`plugins/mill/scripts/_status.py`** — `read_full(status_path)` returns `{"yaml": dict, "timeline": list[str]}`. After sub-skill invocations, mill-autofix reads `status_path = Path("task/status.md").resolve()` and checks `status["yaml"]["phase"]`. Expected values: `planned` (mill-plan succeeded), `blocked` (mill-plan or mill-go blocked), `done` (mill-go succeeded), `complete` (not expected in autofix flow).

**`plugins/mill/scripts/_wiki.py`** — `sync_pull(wiki_path, slug="mill-autofix")` for entry.

**`plugins/mill/scripts/_paths.py`** — `resolve_git_root()`, `resolve_wiki_path(git_root)` for entry.

**`plugins/mill/scripts/_active.py`** — `read_slug(mill_dir)` to confirm active.slug.md was written by millpy-claim. Used for phase-gate checks.

**`plugins/mill/scripts/_constraints.py`** — `read_if_exists()` called per-bug before writing discussion.md; result injected into the Constraints section.

**mill-plan SKILL.md — autonomous_mode additions (two locations):**
1. Phase: Plan Review, step 6 (max-rounds escape): prepend "if deep-merged config has `pipeline.autonomous_mode: true`: skip the user prompt; set `_status.append_phase(status_path, 'blocked', ts)`; commit+push on task branch; halt with 'Autonomous mode: plan blocked after {N} rounds, {M} BLOCKINGs remain. Task left as [active].'"
2. Phase: Plan Review, step 5 (non-progress check): prepend "if `pipeline.autonomous_mode: true`: auto-block without user prompt."

**mill-go SKILL.md — autonomous_mode additions (two locations):**
1. Stuck escalation section: add at the top — "if deep-merged config has `pipeline.autonomous_mode: true`, for any `stuck_type` (transient already-retried, verify, logic): auto-choose block without presenting options to the user."
2. Holistic code review, step 7 (rounds exhausted): prepend "if `pipeline.autonomous_mode: true`: auto-choose option 3 (Block) without presenting the prompt."

**Config.local.yaml management pattern** (described in mill-autofix SKILL.md):
```python
# Entry
config_local_path = Path(".millhouse/config.local.yaml")
original_content = config_local_path.read_text(encoding="utf-8") if config_local_path.exists() else None
# Insert/update pipeline.autonomous_mode: true (yaml merge or append)
# ... run loop ...
# Cleanup (always)
if original_content is None:
    config_local_path.unlink(missing_ok=True)
else:
    config_local_path.write_text(original_content, encoding="utf-8")
```
For simplicity, the skill reads and writes config.local.yaml as a YAML document using `yaml.safe_load` / `yaml.dump`. The `pipeline.autonomous_mode` key is set in the `pipeline` sub-dict.

**SKILLS.md regeneration:** After writing SKILL.md, run `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"` from the hub root.

**Mill-autofix skill flow (complete):**

```
## Entry
1. Load mill:conversation, mill:workflow
2. gh auth status — halt if not authenticated
3. Verify .millhouse/wiki junction exists
4. Resolve wiki path, sync pull
5. Parse arguments: --dry-run, --max-bugs N (default: unlimited)
6. Save config.local.yaml original; set pipeline.autonomous_mode: true

## Fetch
7. _gh_issues.fetch(label_filter=["bug"])
8. If --dry-run: print table (issue #, title, derived slug) and exit
9. Apply --max-bugs limit to the list

## Pre-flight
10. Verify current branch == parent branch (main) — halt if already on a task branch
11. Verify no active.slug.md (no active task) — halt if another task is in progress

## Per-bug loop (sequential, for each issue)
  a. Derive slug (kebab title, truncate, collision suffix)
  b. millpy-add.py: add task to wiki with proposal body = issue body
     - On slug-already-present: read Home.md phase; skip if [active]/[done]; continue on unmarked
  c. millpy-claim.py --slug <slug>
  d. Explore codebase for the bug (Glob/Grep/Read)
  e. Write task/discussion.md (all sections populated)
  f. Commit: "mill-autofix: write discussion.md for <slug>"
  g. Push task branch
  h. Invoke /mill-plan
     - Read task/status.md; if phase == blocked: run cleanup, record, continue
  i. Invoke /mill-go
     - Read task/status.md; if phase != done: run cleanup, record, continue
  j. Invoke /mill-merge (in-place mode auto-detected)
     - Extract squash SHA: git log --oneline -1 <parent_branch>
  k. _gh_issues.close_with_comment(issue_number, f"Autonomously fixed by mill-autofix. Squash commit: {sha}")
  l. Check .scratch/autofix-stop — halt if present

## Cleanup (always, try/finally equivalent)
  - Restore config.local.yaml to original content

## Report
  - Write .scratch/autofix-report.md:
      - Date/time, issues fetched, --max-bugs applied
      - Fixed: list of (slug, issue #, title, commit SHA)
      - Stuck: list of (slug, issue #, title, phase-at-block, blocked_reason)
      - Errored: list of (slug, issue #, title, error description)
  - Print one-line summary to chat + path to report
```

**Stuck cleanup helper (shared within the per-bug loop):**
```
blocked_reason = status["yaml"].get("blocked_reason", "unknown")
git checkout <parent_branch>
rm .millhouse/active.slug.md
record in stuck_list: {slug, issue_number, title, phase, blocked_reason}
```

## Constraints

No CONSTRAINTS.md found in this repo. Standard mill constraints apply:
- Junctions are never used as code paths; always resolve real paths via `_paths.py`.
- `${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths in skill instructions.
- Working state (`task/status.md`, `task/discussion.md`, `task/plan/`, `task/reviews/`) stays on the task branch, never in the wiki.
- Scripts invoked via `uv run --project "${CLAUDE_PLUGIN_ROOT}"`.
- Wiki writes go through `_wiki.write_commit_push` under the wiki lock.
- NTFS junction safety: cleanup sequences use `_junction.strip_all_in_worktree` before any recursive deletion.

## Testing

**`test-gh-issues.py` additions** (extend existing file, no LLM):
- `label_filter=None`: result equals the full unfiltered list
- `label_filter=["bug"]`: only issues with label name "bug" returned; issues with no labels or only other labels excluded
- `label_filter=["bug", "enhancement"]`: issues with either label returned (any-of semantics)
- `label_filter=["nonexistent"]`: empty list returned
- Issues with empty `labels: []` array: excluded when label_filter is set

**New `test-autofix.py`** (no LLM):
- Slug derivation: standard title → expected kebab slug
- Special chars (parens, colons, slashes) stripped
- Consecutive hyphens collapsed
- Truncation at 30 chars at word boundary
- Collision detection: slug already in Home.md text → `-<N>` suffix appended

**No integration tests for the full autofix pipeline** — the skill's orchestration is exercised by running it against real bugs. The unit tests cover the new helper logic; the sub-skills (mill-plan, mill-go, mill-merge) are already tested.

## Q&A log

- **Q:** Should autofix skip issues already in the wiki? **A:** Yes. If millpy-add.py returns "slug already present" and the task is `[active]` or `[done]`, skip the issue entirely. If the task is unmarked in Home.md (add was done in a prior crashed run), skip the add step and proceed to claim.
- **Q:** What if two autofix runs start simultaneously? **A:** The wiki lock prevents concurrent Home.md writes. The builder lock prevents parallel mill-go instances. Sequential per-bug design means the second run would claim a different bug. Acceptable.
- **Q:** What if the issue body is empty? **A:** Mill-autofix writes a minimal discussion.md with the available information. Mill-plan will likely block quickly; the task is left as `[active]`.
- **Q:** What if config.local.yaml doesn't exist? **A:** Create it with `pipeline.autonomous_mode: true`; restore by deleting the file (original_content is None case).
- **Q:** Should `--dry-run` touch the wiki or GitHub? **A:** No. Dry run reads only (issues fetch, Home.md parse for collision check) and prints what would happen.
- **Q:** Does mill-autofix push the task branch before mill-merge? **A:** millpy-implement.py pushes the task branch after each batch (per mill-go SKILL.md board discipline). Mill-autofix's own discussion.md commit is pushed in step g of the loop. No additional push needed.
- **Q:** Should the autofix-report include issue numbers and titles? **A:** Yes. Each entry includes issue #, title, slug, outcome, and (for merged bugs) the squash commit SHA.
- **Q:** How does mill-autofix detect that mill-plan auto-blocked in autonomous_mode? **A:** After `/mill-plan` returns, mill-autofix reads `task/status.md` and checks `phase:`. If `blocked`, the auto-block path fired. If `planned`, proceed to mill-go.
- **Q:** If mill-merge fails (e.g., branch protection), what happens? **A:** Mill-merge's PR-path fallback creates a PR and halts at `pr-pending`. Mill-autofix detects `phase != complete` on reading status after merge and records the task as "pending PR" in the report, then continues. User must land the PR manually and re-run `/mill-merge`.
