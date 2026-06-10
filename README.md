# Millhouse

Millhouse (MH) is a task orchestration system for [Claude Code](https://claude.ai/code). It manages the full lifecycle of coding tasks — from triaging GitHub issues to merging finished code — using AI subagents for design, planning, implementation, and review.

Each task runs in its own isolated git worktree. A separate wiki repository holds the task index. Claude subagents do the heavy lifting; the operator approves at key checkpoints.

## Inspiration

Millhouse builds on ideas from three projects:

- **[claude-code-plugins](https://github.com/motlin/claude-code-plugins)** by Craig Motlin — task tracking and skill plugins for Claude Code
- **[autoboard](https://github.com/willietran/autoboard)** by Willie Tran — autonomous agent orchestration patterns
- **[skills](https://github.com/mattpocock/skills)** by Matt Pocock — Claude Code skill conventions

## General flow

```
GitHub issues
      │
      ▼
  mill-ghissues-to-tasks        Triage open issues into grouped wiki tasks
      │
      ▼
  mill-spawn                    Claim a task, create a git worktree + branch
      │
      ▼
  mill-start                    Discuss the problem; produce discussion.md
      │
      ▼
  mill-plan                     Autonomous plan-writing: batched DAG of cards
      │
      ▼
  mill-go                       Build loop: implementer + reviewer per batch
      │                         Self-fix rounds, holistic review after all batches
      ▼
  mill-finalize / mill-merge    Squash-merge to main (direct or via PR)
      │
      ▼
  mill-cleanup                  Remove worktree, branch, and portal
```

### Worktree isolation

Every task lives on its own branch in its own worktree under `wts/<slug>/`. A junction-based portal (`portals/<slug>/`) gives skills a stable path to the task's `_mill/` state directory (status, plan, reviews, briefs) without hard-coding worktree paths.

### AI subagents

`mill-go` is a lean orchestrator — it reads only `status.md` and plan metadata. The actual work is done by two subagent types:

- **Implementer** (`mill:mill-implementer`) — reads a batch of cards, writes code, runs the verify command, commits.
- **Reviewer** (`mill:mill-reviewer`) — reviews diffs, returns a structured verdict (APPROVE / REQUEST_CHANGES with BLOCKING / NIT findings).

The Builder loops until all batches approve, then optionally runs a holistic review across the full diff.

### Wiki

The task index lives in a sibling git clone (`../wiki/`). Skills never write directly to the wiki directory — all mutations go through the wiki daemon client (`wiki/_client.py`), which holds a write lock and commits atomically.

## Configuration

`mill-config.yaml` in the hub root controls reviewer models, batch sizes, dispatch mode, and pipeline behaviour. A local override at `.millhouse/config.local.yaml` is gitignored.

Key settings:

```yaml
llm:
  claude:
    dispatch: agent          # agent | psmux
pipeline:
  auto_merge: true           # merge automatically after mill-go
  auto_report: true          # file self-report after each run
roles:
  implementer:
    model: haiku             # fast/cheap model for implementation
  code-review:
    holistic:
      reviewer: sonnethigh   # holistic reviewer model
```

## Requirements

- [Claude Code](https://claude.ai/code) with the mill plugin installed (`claude plugin add <path>`)
- Python 3.11+ (managed by the plugin's virtual environment)
- `gh` CLI authenticated (`gh auth login`)
- Git 2.35+ (for `git worktree`)
