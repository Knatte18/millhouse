# Legacy millhouse — navigation index

```yaml
status: draft
source-path: C:\Code\millhouse-legacy\
purpose: navigation aid so CC doesn't have to scan the whole v1 repo
```

## How to use this document

Instead of grepping `C:\Code\millhouse-legacy\` for "junction" or "stream parsing", read this index. It lists every v1 component relevant to v2 with **exact file paths and line ranges**.

When you need to lift or reference something:
1. Look it up here
2. Read just that file (or that slice)
3. Do NOT do general-purpose exploration of legacy

If you find yourself grepping the legacy repo, stop. Add what you found to this index and continue.

---

## Module map

All paths below are relative to `C:\Code\millhouse-legacy\plugins\mill\scripts\millpy\`.

### `core/` — low-level primitives

| File | Purpose | Key exports | Reuse for |
|---|---|---|---|
| `core/paths.py` | Path resolution helpers | `repo_root`, `project_root`, `project_dir`, `slug_from_branch`, `wiki_clone_path`, `mill_junction_path`, `active_dir`, `local_config_path`, `slug_file_path`, `active_junction_path` | Reference. Don't copy structure; replicate specific functions inline in each v2 script. |
| `core/junction.py` | Windows junction + POSIX symlink | `create(target, link_path)`, `remove(link_path)` | **Carry as-is** to `scripts/_junction.py`. Drop `_MODULE` and log imports. |
| `core/subprocess_util.py` | Subprocess runner with logging | `run(argv, cwd=None, timeout=None)` | **Carry as-is** to `scripts/_subprocess_util.py`. |
| `core/log_util.py` | Simple stderr logger | `log(module, msg)` | **Do NOT carry.** Replace with `print(f"[{module}] {msg}", file=sys.stderr)`. |
| `core/config.py` | YAML-ish config loader + validators | `load()`, `load_merged()`, `_parse_yaml_mapping()`, `ConfigError`, `resolve_reviewer_name()` | Reference only. Use PyYAML in v2 unless avoiding the dep matters. |
| `core/verdict.py` | Verdict extraction (3 formats) | `extract_verdict_from_text()` | Lift the YAML-frontmatter branch only (~10 LOC). Drop JSON-last-line and legacy-`VERDICT:` branches. |
| `core/plan_io.py` | Plan file resolver (v1/v2/v3) | `resolve_plan_path()`, file readers | **Do NOT carry.** v2 has one plan format at one path. |
| `core/plan_validator.py` | Plan structure checker | `validate(plan_path)` | Reference. Simplify to v2's single-card-list format. |
| `core/bulk_payload.py` | Construct multi-file prompts | `build_bulk_payload()` | Reference if v2 ensemble script needs it. Not for v2.0 core. |
| `core/git_ops.py` | Git command wrappers | `git()`, `worktree_list()` | Reference. Most v2 scripts can call `subprocess.run(["git", ...])` directly. |

### `tasks/` — wiki/task I/O

| File | Purpose | Key exports | Reuse for |
|---|---|---|---|
| `tasks/wiki.py` | Wiki clone operations + lock | `acquire_lock()`, `release_lock()`, `write_commit_push()`, `sync_pull()` | **Carry** to `scripts/_wiki.py`. The lock retry logic (~80 LOC) is the valuable part. |
| `tasks/tasks_md.py` | Parse/write Home.md | `parse()`, `resolve_path()`, `write_commit_push()` | Reference. Extract the `## <slug>` heading parser (~30 LOC) inline into v2's `mill-list.py`/`mill-add.py`. |
| `tasks/status_md.py` | status.md parser + wiki commit | `append_phase()`, parsers | Reference only. v2 rewrites the wiki-path detection (v1 was the file with the silent-skip bug). |

### `backends/` — provider implementations

| File | Purpose | Reuse for v2 Layer 02 |
|---|---|---|
| `backends/base.py` | Backend interface + dataclasses | **Do NOT carry.** Abstract base classes. |
| `backends/claude.py` | Claude CLI wrapper (stream-json + bulk) | Reference. Read the stream-json event parsing. Rewrite against v2's `ReviewResult`. |
| `backends/gemini.py` | Gemini API client (bulk only) | Reference. Lift auth/endpoint URLs. Rewrite for tool-use. |
| `backends/ollama.py` | Ollama local model | Reference. Only if v2 adds Ollama later. |

### `reviewers/` — review orchestration

| File | Purpose | Reuse for v2 |
|---|---|---|
| `reviewers/base.py` | `Worker` + `Cluster` dataclasses + `SingleWorker` class | **Do NOT carry.** Replace with dict-dispatch. |
| `reviewers/workers.py` | WORKERS registry (model definitions) | Reference for the model list. v2 puts this in config YAML, not Python. |
| `reviewers/clusters.py` | CLUSTERS registry (ensemble definitions) | **Do NOT carry for v2.0.** If ensemble ships later, this is the reference. |
| `reviewers/engine.py` | Dispatch engine | **Do NOT carry.** v2's dispatcher is 30 lines. |
| `reviewers/cluster.py` | Ensemble executor | Reference for later ensemble script. |
| `reviewers/handler.py` | Ensemble handler | Reference for later ensemble script. |
| `reviewers/failures.py` | Failure taxonomy | Reference. v2 should have simpler failure categories. |

### `entrypoints/` — CLI entry points

| File | Purpose | Reuse for |
|---|---|---|
| `entrypoints/_bootstrap.py` | sys.path hack | **Do NOT carry.** |
| `entrypoints/spawn_task.py` | Claim task + create worktree | Reference lines 100–330 for worktree setup sequence. Rewrite cleanly in v2's `mill-spawn.py`. |
| `entrypoints/worktree.py` | Generic worktree create/remove | Reference for `git worktree add` flow. |
| `entrypoints/spawn_reviewer.py` | Review dispatch CLI | Reference the arg shape + model resolution. Rewrite against v2 provider contract. |
| `entrypoints/spawn_agent.py` | Implementer dispatch | Reference the brief-loading + subprocess spawn. |
| `entrypoints/open_vscode.py`, `open_terminal.py` | Worktree picker UIs | **Do NOT carry.** Use `mill-status` + user choice. |
| `entrypoints/notify.py` | Desktop notification | Carry if v2 wants notifications. ~30 LOC. |
| `entrypoints/set_worktree_color.py` | VS Code window color | Carry if v2 wants this. |
| `entrypoints/fetch_issues.py` | GitHub issue fetcher for mill-revise-tasks | Carry for Layer 04 if needed. |
| `entrypoints/regenerate_sidebar.py` | Wiki _Sidebar.md generator | Carry for Layer 04 if v2 wants sidebar regen. |
| `entrypoints/status_verify.py` | Consistency check | Reference. v2's validator replaces this concept. |

### `worktree/` — worktree-child tracking

| File | Purpose | Reuse for |
|---|---|---|
| `worktree/children.py` | Parse `.millhouse/children/*.md` registry | **Do NOT carry.** v2 doesn't use child registry; uses git worktree list. |
| `worktree/setup.py` | Worktree setup helpers | Reference. Most logic moves into v2's `mill-spawn.py`. |

### `codeguide/` — docs generation plugin (separate)

Kept as-is. Link via `marketplace.json`, do not touch.

---

## Skills map

Under `plugins/mill/skills/`. Each `SKILL.md` describes a workflow for Claude.

| v1 skill | v2 carry | Notes |
|---|---|---|
| `mill-setup/SKILL.md` | Reference only | v2 setup is simpler (no spawn_wiki-orphan, no orphan-tasks branch) |
| `mill-add/SKILL.md` | Reference | Simple skill, straightforward to port |
| `mill-spawn/SKILL.md` | Reference | Drop the "copy _millhouse" step; v2 uses `.millhouse/` directly |
| `mill-start/SKILL.md` | Reference for discussion workflow | v2 drops the "discussion review" by default |
| `mill-plan/SKILL.md` | Reference | Drop v2-plan-format branching |
| `mill-go/SKILL.md` | Heavy reference | Biggest skill. v2 drops DAG executor, per-card spawn, bulk review |
| `mill-merge/SKILL.md` | Reference for git sequence | PR vs direct-merge branching can simplify |
| `mill-cleanup/SKILL.md` | Reference | Junction teardown logic is useful |
| `mill-abandon/SKILL.md` | Reference | Phase transition |
| `mill-status/SKILL.md` | Reference | Table output format |
| `mill-status-verify/SKILL.md` | Do NOT carry | Replaced by validator |
| `mill-resume/SKILL.md` | Reference | Cross-machine resume flow |
| `mill-inspect/SKILL.md` | Carry if you want inspect mode | Toggle uncommitted-diff view |
| `mill-self-report/SKILL.md` | Optional | Session-end bug reporting |
| `mill-skills-index/SKILL.md` | Carry | Regenerates SKILLS.md from frontmatter |
| `mill-revise-tasks/SKILL.md` | Carry with trim | GitHub issue → tasks.md flow |
| `mill-receiving-review/SKILL.md` | Reference | Decision tree for reviewer findings |
| `mill-merge-in/SKILL.md` | Optional | Sync parent into branch |
| `conversation/SKILL.md` | Carry | Response-style rules |
| `workflow/SKILL.md` | Reference | Skill invocation table |
| `code-quality/SKILL.md` | Carry | Clean-code rules |
| `cli/SKILL.md` | Carry | Shell command guidelines |
| `git-*/SKILL.md` | Carry | Git-related skills, small |
| `testing/SKILL.md` | Carry | Testing principles |
| `linting/SKILL.md` | Carry | Project-specific style |
| `markdown/SKILL.md` | Carry | Markdown formatting rules |
| `codeguide-*/SKILL.md` | Carry | Codeguide plugin skills |
| `review-navigation/SKILL.md` | Optional | Navigation issue reporting |
| `review-handler/SKILL.md` | **Do NOT carry** | Ensemble handler skill |
| `millhouse-issue/SKILL.md` | Carry | GitHub issue filing |

### Skill-file word counts (rough)

If you need to know how big something is before reading it:

- `mill-go/SKILL.md` — ~8000 words (biggest, will need heaviest reference reading)
- `mill-setup/SKILL.md` — ~3500 words
- `mill-plan/SKILL.md` — ~3000 words
- `mill-spawn/SKILL.md` — ~1500 words
- Most others — under 1000 words

---

## Docs map (under `plugins/mill/doc/`)

### `doc/prompts/` — review/brief prompt templates (v1)

| File | Purpose | Reuse for v2 |
|---|---|---|
| `plan-review.md` | v3 holistic plan reviewer prompt (tool-use) | **Reference heavily.** Lift the evaluation criteria. Drop dispatch-mode variants. |
| `plan-review-bulk.md` | v2 per-batch bulk plan reviewer | Reference if ensemble ships later. |
| `plan-review-bulk-holistic.md` | v3 holistic bulk reviewer | Reference. |
| `code-review.md` | Code reviewer prompt | Lift for v2's `review-prompt-code.md`. |
| `code-review-bulk.md` | Bulk code reviewer | Reference. |
| `discussion-review.md` | Discussion reviewer prompt | Lift for v2's `review-prompt-discussion.md`. |
| `implementer-brief.md` | Implementer brief template | Lift for v2's `implementer-brief.md`. |
| `handler.md`, `handler-bulk.md`, `handler-prep.md` | Ensemble handler prompts | Reference only if v2 adds ensemble. |

### `doc/formats/` — format specifications

| File | Content | Reuse |
|---|---|---|
| `plan.md` | v1 plan format spec | Reference; simpler v2 format replaces it |
| `tasksmd.md` | tasks.md format | Reference for Home.md conventions |
| `discussion.md` | discussion.md format | Reference |
| `validation.md` | Generic validation approach | Reference for v2's validator |
| `handoff-brief.md` | Handoff prompt format (abandoned in v1) | Do not carry |

### `doc/architecture/`

| File | Content | Reuse |
|---|---|---|
| `overview.md` | System overview | Reference for context only |
| `directory-layout.md` | `_millhouse/` vs `.mill/` explanation | Do not carry (v2 layout is different) |
| `reviewer-modules.md` | Reviewer architecture | Reference; v2 simplifies heavily |
| `powershell-compat.md` | Windows/PowerShell notes | Reference if hit edge cases |
| `local-llm-backend-lessons.md` | Ollama lessons | Reference when adding Ollama |

### `doc/proposals/`

| File | Content | Reuse |
|---|---|---|
| `04-track-task-state.md` | Task-state proposal (partly implemented) | Reference for the design reasoning |
| `05-plan-format-contract.md` | Plan format v3 proposal | Reference; v2 simplifies |

---

## Templates map (under `plugins/mill/templates/`)

| File | Purpose | Reuse for v2 |
|---|---|---|
| `status-discussing.md` | Initial status.md when spawned | Merge with below into single v2 `status.md` template |
| `status-abandoned.md` | Status when abandoned | Same — v2 has one template, phase is a field |
| `claude-md-sections.md` | CLAUDE.md snippets for mill sections | Reference for v2's CLAUDE.md template |
| `config.yaml` | Shared config template | Reference. v2 simplifies. |
| `millhouse-config.yaml` | Alternative config template | Reference |
| `wrapper.py` | Wrapper-script template for `.millhouse/*.py` | Reference; wrapper form likely stays similar |
| `vscode-settings.json` | Worktree color settings | Carry if v2 uses worktree colors |
| `local-rules.md` | Local-rules CLAUDE.md snippet | Reference |
| `cgexclude.md`, `cgignore.md` | Codeguide exclusion | Reference |
| `codeguide-overview-starter.md` | Codeguide bootstrap | Reference |
| `DocumentationGuide.md` | Docs-guide template | Reference |

---

## Tests map

v1 has ~90 test files totalling 645 passing tests.

**Per the v2 test discipline (overview.md),** we do NOT carry over any v1 tests directly. Write new integration tests that exercise v2 scripts end-to-end.

The one thing worth lifting is the *patterns* from v1's `tests/integration/conftest.py`:
- `flat_project_layout` and `nested_project_layout` fixtures show how to build a temporary test repo with git init + config + fake wiki
- **Do not copy the fixtures.** Read them, understand the setup sequence, replicate it in a PowerShell test if needed.

---

## Configuration files worth reading

Relative to `C:\Code\millhouse-legacy\`:

| File | Reason to read |
|---|---|
| `.claude-plugin/plugin.json` | Plugin structure |
| `marketplace.json` | How plugins link |
| `.gitignore` | What was ignored (most of it applies to v2) |
| `CLAUDE.md` (repo root) | v1 CLAUDE.md — reference for v2's version |

---

## How to extend this index

If during v2 development you find yourself needing to read a v1 file not listed here:

1. Add a row to the relevant section above
2. Include: file path, purpose, line range if narrow, reuse verdict
3. Commit the index update

This keeps the index complete for future work.

## When NOT to consult this index

- When you're sure the v2 answer is fresh code, don't look at v1 at all
- When you're designing a new format not in v1, start from the format-discipline rules, not v1
- When v1's answer is clearly the wrong abstraction for v2 (e.g., the Reviewer Protocol), skip the reference

The rule of thumb: read v1 for primitives (junction, subprocess, parsers) and workflow references (skill flows). Do not read v1 for architecture (package layout, class hierarchies, dispatch engines).
