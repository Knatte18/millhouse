# Backlog

```yaml
source: extracted from the wiki task index (Someday section)
```

Speculative, not-yet-scoped ideas.
Not tracked as active mill tasks — pulled out of the wiki so the task index only holds real, actionable work.
Revive by turning one of these into a wiki task when someone actually wants to pick it up.

---

## mill-orchestrator: Autonomous orchestrator pipeline

### Problem

The current mill pipeline conflates roles:

- **Thread A (mill-start)** runs the user discussion, but also kicks off discussion review inline — mixing interactive and autonomous work in the same thread.
- **mill-go** is an orchestrator, but reads files directly (briefs, plan, discussion.md), bloating its context over a long task.
- **Planning** is done by the Builder thread, which must hold enough context to both plan and later coordinate implementation.
- **User approval** is required at discussion-review and plan-review stages even though the reviewer's findings and fix suggestions are almost always correct.

### Proposed architecture

#### Thread A — Discussion (Opus)

Runs mill-start as today, but with one change: produces a **richer `task/discussion.md`** and exits.
No review is triggered from Thread A.

**Richer discussion.md format** (new fields required):

```yaml
files_affected:
  - path/to/file.py  # reason: ...
files_not_affected:
  - path/to/other.py  # reason: explicitly out of scope
constraints:
  - backwards compat: public API must not change
  - performance: no new O(n²) paths in hot loop
ambiguities:
  - "Config key X not documented — Planner should default to Y"
```

The file-scope section is the key addition: it reduces Planner guesswork and keeps reviewer/fixer subagents focused on the right files.

**Model:** Opus — this is where requirements are shaped;
quality matters most here.

---

#### Thread B — Orchestrator (Sonnet)

Fully autonomous after Thread A exits.
Pure coordinator: **never reads source files**.
Reads only:

- `task/status.md` — own resume state
- Short JSON verdict reports from subagents

Spawns all subagents;
each is single-purpose and short-lived.
B's context stays small throughout — ~100–300 tokens per subagent verdict, ~20 verdicts over a full task.

**State persistence:** B writes the current phase to `task/status.md` after each phase completes, enabling clean resume after a crash or auto-compact.

---

#### Phase 1 — Discussion review loop

```
B spawns Reviewer(discussion) → writes task/reviews/discussion-<round>.md
B reads verdict JSON (APPROVE / GAPS_FOUND + file list)
  APPROVE → advance to Phase 2
  GAPS_FOUND →
    B spawns Fixer(discussion) → reads review file + named files only → patches discussion.md
    repeat up to review.discussion.rounds
  Still blocked → Phase 1 blocked handler
```

Reviewer and Fixer are separate subagents.
Fixer receives the review file (which contains detailed fix suggestions per finding) and the specific files named in findings — nothing else.
Context is minimal and targeted.

---

#### Phase 2 — Planning (Opus)

```
B spawns Planner(Opus) → reads discussion.md + files_affected list
  Planner writes task/plan/ (as today)
  Planner never asks questions — guesses if ambiguous, logs guesses in task/plan/assumptions.md
  Returns JSON: {status: "done", assumptions: [...]}
B reads verdict JSON
```

**Model:** Opus — highest reasoning quality for the plan that drives all subsequent implementation.

Planner scope is bounded by `files_affected` from discussion.md, reducing exploratory file reads.

---

#### Phase 3 — Plan review loop

```
B spawns Reviewer(plan) → writes task/reviews/plan-<round>.md
B reads verdict JSON
  APPROVE → advance to Phase 4
  REQUEST_CHANGES →
    B spawns Fixer(plan) → reads review + named plan sections → patches task/plan/
    repeat up to review.plan.rounds
  Still blocked → Phase 3 blocked handler
```

Same pattern as Phase 1.

---

#### Phase 4 — Implementation

As current mill-go: batched implementers, holistic code review, self-fix rounds.
No change to this phase's internal logic.

---

#### Self-reporting in this architecture

mill-self-report is auto-fired from `mill-plan` (after plan approval) and the orchestrator (Thread B, at end of Phase 4 / Handoff). mill-merge does not self-report — only the orchestrator does.
Cross-thread merges are not auto-reflected.

What self-report reads (all on disk, all written by sub-agents):

- `task/discussion.md` — Thread A's output.
- `task/plan/` — Planner output, including `task/plan/assumptions.md` (where Planner logs guesses for ambiguities).
- `task/reviews/*.md` — Reviewer and Fixer output for every round.
- `task/status.md` — phase timeline + batch states.

**Free-form observation channel.**
Sub-agents that notice something report-worthy but lack a natural artifact (e.g. Implementer says "the brief was unclear about X", Fixer says "review finding 3 contradicted finding 5") append a one-liner to `task/notes.md`.
Self-report reads `notes.md` alongside the structured artifacts.
Empty/missing notes.md is fine.

The orchestrator (Thread B) does NOT read notes.md — it remains lean.
The file is purely a write-only channel from sub-agents to the eventual self-report invocation.

---

#### Blocked handling

When any phase exhausts its retry budget without APPROVE:

1. B writes `task/blocked.md`:
   ```
   Phase: <1|2|3|4>
   Reason: <last reviewer verdict summary>
   Last review: task/reviews/<file>
   Suggested action: <manual fix / reconsider discussion>
   ```
2. B sends notification via `notify` backend.
3. B exits.

**Resume:** After manual fix, re-run Thread B. It reads `task/status.md`, determines which phase completed, and resumes from the blocked phase.
Completed phases are not re-run.

---

### What B never does

- Read source files (`Read`, `Grep`, `Glob` on repo files)
- Write plan or implementation content itself
- Ask the user questions
- Make implementation decisions

B's only decisions: which subagent to spawn next, and whether to advance or retry based on the verdict JSON.

---

### Model assignment

| Thread / Agent | Model  | Reason |
|---|---|---|
| Thread A (discussion) | Opus | Requirements shaping; highest quality |
| Thread B (orchestrator) | Sonnet | Coordination only; no deep reasoning needed |
| Planner | Opus | Plan quality drives all implementation |
| Reviewer (discussion/plan/code) | Sonnetmax | As today |
| Fixer (discussion/plan) | Sonnet | Targeted edits from explicit review instructions |
| Implementer | Sonnet | As today |

---

### Relationship to existing tasks

- **Task 15 (implementer-self-review):** The warm-context reviewer-in-same-session idea may be less relevant in this architecture — each fixer already has targeted context from the review file.
  Evaluate whether task 15 is still needed after this ships.
- **Task 16 (mill-autofix):** The autonomous bug queue drainer can build on top of this pipeline rather than reimplementing it.
  Revisit scope after this ships.
- **Task 29 (mill-merge-subagent):** Same philosophy (delegate to subagent, return JSON verdict) — consistent with this design.
- **Follow-up: `mill-autorun` (see below):** A thin operator-facing skill that closes the manual gap between Thread A and Thread B. Operator runs `/mill-autorun`;
  the skill spawns Thread A with `/mill-start --auto`, waits for `status.md phase=discussed`, then triggers Thread B. Whole pipeline runs autonomously from claim to merge.

  **Design implication for this task:** Thread B's entry-point must be invokable both interactively (operator runs `/mill-orchestrator` or whatever the skill is named) AND programmatically (mill-autorun spawns it without operator presence).
  That means:
  - Thread B starts from `status.md phase=discussed` without requiring fresh operator input
  - Thread B's halt-paths (Planner stuck, review exhausted, mill-merge blocked) must produce clear status.md state that mill-autorun can detect and surface to the operator
  - No interactive prompts inside Thread B's autonomous loop — every halt must commit a `blocked_reason` to `status.md` and exit cleanly

  If Thread B is designed with these constraints from day one, mill-autorun becomes a ~50-line wrapper.
  If not, retro-fitting autorun later requires reshuffling the orchestrator's interface.

---

### Context-budget evidence (real-world observation, 2026-05-11)

Builder hit ~75/200k tokens in a single mill-go/mill-merge run.
Confirms the "B must never read source files" principle and identifies concrete fix-targets that should land alongside this redesign:

1. **`millpy-implement.py` dumps subprocess output to stdout.**
   Every `[subprocess] spawn argv=…` line lands in Builder context.
   Three implementers × ~50 noise lines each = significant token burn.
   Builder only needs the final JSON report line.
   **Fix:** mirror `millpy-bg.py` — write all subprocess + intermediate output to a log file under `task/.logs/` (or similar), emit only the JSON sentinel line to stdout.
   Builder reads stdout's last non-empty line;
   the log file is for human / self-report consumption.
2. **`millpy-bg.py` polling tail-output.**
   The current poll-and-tail pattern also produces noise.
   Either replace polling with a single blocking wait for the `[mill-bg] EXIT` sentinel and then read only the JSON summary line, or accept polling but ensure poll-output is filtered to the summary line only.
3. **Skill-loading bloat.**
   One mill-go session loaded 8 skills (mill-go, mill-workflow, mill-conversation, mill-receiving-review, mill-merge, mill-merge-in, mill-self-report, millhouse-issue) — each hundreds of tokens.
   The Thread B redesign reduces this: B loads only the orchestrator skill + whatever skills its subagents need (not B itself).
   Each subagent loads only the one skill it executes.
4. **Debug-round amplification.**
   Failed merge-lock writes, Home.md-revert detours (covered by task 46), and ad-hoc Python invocations to debug `sync_pull` slug-argument cost full additional turns each.
   Cleaner gate-failures (task 46's status.md-as-fasit principle) reduce the need for these ad-hoc debug rounds in the steady state.

These four together — log-not-stdout for `millpy-implement.py`, summary-only for `millpy-bg.py`, skill loading scoped to the executing subagent, and the task-46 cleanup — are what make Sonnet a realistic Thread B over a full task lifecycle.
Without them, Thread B's context budget evaporates even though B "never reads source files" on paper.

### Open questions

- Does mill-start need a schema change for the new discussion.md fields, or is it additive (old hubs work, new fields optional)?
- Should Planner run in a new CC thread (Agent spawn) or as a subagent via the SDK?
  Same question for Reviewer/Fixer.
- Phase 2 timeout: Planner on Opus may be slow.
  What is the right `planner_timeout`?

---

## mill-autorun: Autonomous claim-to-merge wrapper

### Why

Even with mill-orchestrator's architecture (Thread A discussion, Thread B autonomous coordinator), operator must still manually trigger Thread B after Thread A commits `discussion.md`.
That manual hand-off is the last barrier to full claim-to-merge autonomy.

`pipeline.auto_merge: true` and `mill-start --auto` already remove operator intervention from *within* a phase. mill-autorun closes the gap *between* phases.

### What

A thin operator-facing skill:

```
/mill-autorun [--slug <slug>]
```

Flow:

1. Invoke `mill-spawn [--slug <slug>]` → claim task, create worktree.
2. Spawn Thread A (Opus) with `/mill-start --auto` → writes discussion.md, commits + pushes, terminates.
   Phase=discussed.
3. Poll `status.md phase` until it transitions to `discussed` (or `blocked`).
4. Spawn Thread B (Sonnet orchestrator from mill-orchestrator) → handles plan + implement + review + merge + self-report autonomously.
5. Return to operator when `Home.md` shows `[done]` (or `[pr-pending]` / blocked).

Implementation is essentially:
- mill-spawn invocation (operator-known)
- Two `Task tool` spawns (Opus for A, Sonnet for B) with explicit prompts
- Phase-poll loop with timeout + halt detection
- Final report

Estimated ~50 lines of Python + a short SKILL.md.

### Dependencies

- **mill-orchestrator** is a hard prerequisite. mill-autorun is a wrapper around Thread B's entry-point.
  If Thread B isn't programmatically invokable (operator-free), autorun can't drive it.
- **home-md-states-teardown-split** preferred but not required — gives autorun cleaner status signals (`[ready-to-merge]` vs `[done]` vs `[pr-pending]`).
- **wiki-flip-in-merge** preferred — without it, schema-coupled tasks halt autorun on the manual wiki migration step.

### Open questions

- Should autorun support batched runs (claim N tasks in sequence) or just one-at-a-time?
- How does autorun handle halt-paths (stuck implementer, review exhausted, PR-pending) — abort entire pipeline, or fire notification + wait?
- Does autorun spawn Thread B as a new Claude Code session, or invoke the orchestrator skill inline in the current thread? (Latter is simpler;
  former isolates context budget.)
- Backoff / retry policy for transient failures (rate-limit, network).
- Cost concern: Opus subagent in Thread A burns tokens — should there be a fallback (`--auto-light` that uses Sonnet for discussion)?

### Not-goals

- Not a daemon. mill-autorun is a one-shot pipeline;
  it does not loop, drain a queue, or watch for new tasks.
- Not a replacement for individual skills. `/mill-spawn`, `/mill-start`, `/mill-go` etc. remain usable standalone for non-autonomous workflows.

---

## cluster-reviewer: Handler/cluster reviewer

### Purpose

Cluster reviewers evaluate the same artefact via N parallel workers, then a handler aggregates their opinions into a single verdict.
Cost wins come from provider-side prompt caching — upload the common bulk once, reference it cheaply from N worker calls + 1 handler call.

### Hard constraint: purely additive

No changes to existing templates, backends, `build_tool_rule`, or `render_prompt`.
The cluster reviewer presents the same `run(prompt_text) -> str` interface as simple reviewers;
cluster mechanics stay inside its module.

### Components to add

- **`_llm_gemini.py`** — Gemini provider with `cachedContent` API integration.
  Upload a context once, reference it in subsequent calls.
  Amortizes across the N workers + 1 handler call in a single review.
- **`_reviewer_cluster_g25flash_handler_sonnet.py`** (or similar naming) — cluster reviewer module.
  Has `MODE = "bulk"` from the backend's perspective.
  Internally: (1) receive fully-rendered `prompt_text`, (2) upload to Gemini cache, (3) spawn N Gemini workers in parallel referencing the cache, (4) render handler prompt from `templates/review-handler.md` with the N outputs injected, (5) call the handler and return its output.
- **`templates/review-handler.md`** — handler/aggregator prompt.
  Lift from v1 `doc/prompts/handler.md` with verbatim-evidence requirement + finding-dedup rules.

### Config wiring

`review.<type>.{reviewer|batch|holistic}: cluster_g25flash_handler_sonnet` — same config slot as simple reviewers. Zero changes to backends or schemas.

---

## implementer-ollama: Add Ollama as a local LLM provider for Mill implementation

### Why

Mill's implementation step is currently locked to Claude (Sonnet via `_implementer_sonnet.py`).
Mill plans are detailed enough that a smaller local model should be able to follow them step by step.
Running on a local GPU (RTX 5090) eliminates API cost, removes latency spikes, and allows the model to run offline.
Multiple machines on the same network can share one inference host.

### What needs to happen

1. **`_llm_ollama.py`** — thin LLM-provider wrapping the Ollama HTTP API (`/api/generate` or `/api/chat`).
   Accepts `model` (e.g. `qwen2.5-coder:32b`) and `base_url` (default `http://localhost:11434`) from config.
   Exposes `run_bulk(prompt_text)` consistent with `_llm_claude.py` and `_llm_gemini.py`.

2. **`_implementer_ollama.py`** — implementer module that calls `_llm_ollama.py`.
   Mirrors the shape of `_implementer_sonnet.py`.
   Reads `implementer.ollama.model` and `implementer.ollama.base_url` from `.millhouse/config.local.yaml` (or wiki `config.yaml` defaults).

3. **Startup utility** — PowerShell script (or Python helper) that ensures `ollama serve` is running and the configured model is pulled/loaded before mill tries to call it.
   Should be callable as a pre-flight check from mill-go or standalone.

4. **Config wiring** — add `implementer.backend: ollama` as a selectable option alongside `sonnet`. `base_url` defaults to `localhost:11434` but is overridable per machine in `config.local.yaml`, so machines without a GPU can point to the RTX-5090 host on the LAN.

### Dependencies / open questions

- Ollama's streaming API vs. blocking — decide which mode `_llm_ollama.py` uses (blocking simpler for v1).
- Model selection: start with `qwen2.5-coder:32b`;
  config-driven so any Ollama model works.
- Does the startup script belong in `millpy-*.py` or as a standalone `.ps1`?
- Context window limits: Ollama models have smaller context than Claude;
  may need to trim plan files passed to the implementer.
  Out of scope for v1 — fail loudly if prompt exceeds limit.

### Related

- `_implementer_sonnet.py` — reference implementation
- `_llm_gemini.py` — example of a second LLM provider
- `wiki/config.yaml` — where `implementer.backend` default should be documented

---

## gemini-subscription-billing: Route Gemini reviews through subscription quota, not API key

### Why

Mill's `_llm_gemini.py` uses a Gemini API key, which bills per token.
The operator already has a Google One AI Premium subscription that includes Gemini Advanced at a flat monthly rate.
The official Gemini CLI (`gemini`) authenticates via OAuth against the Google account and draws from the subscription quota instead of the pay-per-token API.
This means every review call via Mill costs real money even though the subscription is already paid for.

### What needs to happen

Investigate whether `_llm_gemini.py` can be changed to route calls through the subscription quota instead of the API key.
Two candidate approaches:

1. **Gemini CLI as subprocess** — invoke `gemini` CLI and capture output, the way some tools shell out to `claude`.
   Simplest if the CLI has a non-interactive/pipe mode.
2. **OAuth-based API access** — use Google OAuth2 credentials (Application Default Credentials or a service-account-style flow) to call the Gemini REST API under the subscription billing context, if Google exposes that endpoint.

If neither is feasible (Google may not expose subscription quota to third-party API calls at all), document the finding and close the task.

### Dependencies / open questions

- Does Google actually allow subscription quota to be consumed via API/CLI calls, or is it strictly limited to the Gemini web/app interface?
- Does the Gemini CLI support non-interactive stdin/stdout mode suitable for scripting?
- Is the OAuth flow machine-friendly (refresh tokens, headless auth) or does it require a browser on every run?

### Related

- `plugins/mill/scripts/_llm_gemini.py` — current implementation using API key
- `implementer-ollama` task — parallel effort to add a local/free inference backend
