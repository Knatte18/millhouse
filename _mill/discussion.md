# Discussion: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
task: Explore and adopt Claude Code fork-agents in mill orchestration
slug: explore-fork-agent-opportunities
status: discussing
parent: main
```

## Problem

Claude Code has a native "fork" sub-agent (`Agent` tool, `subagent_type: "fork"`) that
continues from the parent's own conversation instead of starting cold. Mill dispatches every
sub-agent cold: it renders a brief file, spawns a fresh `mill:mill-implementer` or
`mill:mill-reviewer`, and relays the result back. The question was whether forking could
replace that pattern, and in particular whether it would fix the orchestrator context-bloat
problem observed in mill-go.

The exploration answered both, and the answer to the second is **no**. Fork does not fix the
bloat, because the bloat is not caused by cold-starting agents — it is caused by mill-go's
agent-mode **output contract**, which forces every sub-agent's entire final message through
the orchestrator's context *twice*. That defect is real and independently confirmed, and it
is what this task fixes. Fork itself fits exactly one place in mill.

**Why now:** a mill-go run was observed burning ~75k/200k tokens of orchestrator context in a
single task. Agent-mode dispatch is the shipped default (`dispatch: agent` in both the hub
config and the plugin template), so every mill task pays this cost on every dispatch.

## Scope

This task was deliberately **narrowed to reviewers** after the design review showed the
implementer half drags in a classifier minefield (the `#574` false-success hazard, the
git-state completeness recount, the warm-`SendMessage` resume, and the clean-mid-work-stop
path). Reviewers are also the *largest* payloads — a code-review findings dump dwarfs an
implementer's JSON status line — so this keeps most of the token win for a fraction of the
risk. Implementers/fixers can follow as a separate task once the pattern is proven.

**In:**

- **A. Fork adoption at one site.** `mill-start`'s Phase: Explore gains SKILL.md guidance
  **introducing** sub-investigation dispatch — today Step 3 (`mill-start/SKILL.md:117-125`)
  tells the orchestrator to explore *directly* with Grep/Glob/git log and dispatches no agent
  at all. The new guidance names `Agent(subagent_type: "fork")` as the default for scoped
  sub-investigations that need the task context already in the orchestrator's head, and a
  cold `Explore` agent for broad mechanical sweeps.
- **B. The reviewer output contract.** For the three **reviewer** dispatch sites
  (discussion review, plan review, code review — batch and holistic), the reviewer writes its
  own `<brief>.out.md`; the orchestrator's `Write` step is deleted for reviewer dispatches;
  and the reviewer's final message shrinks to a one-line ack.
- **C. `mill-reviewer` gains `Write`,** guardrailed to `_mill/briefs/`, and every prompt that
  currently tells the reviewer "your final message *is* your output" is swept — including the
  `<TOOL_RULE>` block, which is injected from **Python**, not from a template.
- **D. `output_path` in the three review prepare envelopes**, with the `.md` → `.out.md` rule
  centralised in one helper.
- **E. Robustness for the two failure modes the change introduces:** a **missing-file guard**
  (an absent `.out.md` currently raises an uncaught `FileNotFoundError`) and **stale-file
  truncation** (nothing in mill ever truncates `.out.md`, and a retried reviewer has no
  backstop).
- **F. Remove the `html.unescape()` calls** at the three review read sites.
- **G. A durable decision note** in `mill-go/SKILL.md`'s "## Agent-mode dispatch" section
  recording why fork is rejected for the scripted dispatch sites.

**Out:**

- **The implementer / fixer / merge-in dispatch sites keep today's contract, unchanged.**
  The orchestrator still captures their notification to `.out.md`; `_implementer_common.py` is
  not touched; its `html.unescape` **stays** (their payload still arrives via the
  HTML-escaped notification). This is the descope, and it is deliberate.
- Forking any scripted dispatch site. Rejected on the merits — see Decisions.
- Forking `mill-self-report`. Considered and rejected — see Decisions.
- Merging with the deferred `mill-orchestrator` task (id 0, Thread A/B split).
- Deleting the `subprocess` / `psmux` paths. They are dead as a *configured* dispatch mode,
  but **`--stage full` is not dead**: it is the reviewer's fallback after two consecutive raw
  API errors (`mill-go/SKILL.md:129`), so its prompt contract must keep working. See
  `output-contract-is-agent-mode-only`.
- Two unrelated bugs found while mapping (file these, don't fix here):
  `millpy-implement.py --stage prepare` never emits `start_sha` even though
  `mill-go/SKILL.md` step 6 says to thread `--start-sha` into finalize; and
  `_agent_dispatch.resolve_dispatch_mode()` defaults to `"subprocess"` while both shipped
  configs set `agent`.

## Decisions

### fork-rejected-for-scripted-dispatch

- **Decision:** Do not use `subagent_type: "fork"` at any of mill's scripted dispatch sites.
- **Rationale:** Fork's only real advantage over a fresh Agent is that the child inherits the
  parent's context and so needs no brief. Its other advertised property — "the child's tool
  output stays out of the parent" — is **not** a differentiator: an ordinary fresh Agent call
  already behaves that way; only the final message returns. Mill pays the brief-writing cost
  deliberately, and the brief is load-bearing for three things fork destroys, each
  independently disqualifying:
  1. **Per-role model tiers.** A fork always runs on the parent's model and **ignores a
     `model` override**. Mill assigns models per role (`roles.fixer.model: haiku`,
     `roles.implementer.model: sonnethigh`, discussion-review `opushigh`). Forking the fixer
     silently promotes a Haiku fixer to whatever the orchestrator runs on.
  2. **The reviewer's read-only invariant.** `mill-reviewer` is granted only
     `Read, Grep, Glob`. A fork inherits the **parent's** tools, so a reviewer forked from
     mill-go would hold `Edit`, `Write`, and `Bash`.
  3. **Crash-safe resume.** The brief is a committed git artifact; `--stage prepare` writes it,
     commits state, and pushes. A fork's "brief" is the parent's in-memory context — not on
     disk, not reconstructible after a crash.
  A fourth reason applies to reviewers specifically: **review independence.** A forked
  reviewer inherits the author's reasoning, including the rationalizations review exists to
  catch. Discussion review and plan review must not be warm-context.
- **Rejected:** A fourth `fork` dispatch mode. It trades away model tiers, the reviewer tool
  grant, and resumability for a saving (brief composition) that mill wants to keep paying.

### fork-adopted-in-mill-start-explore

- **Decision:** Add guidance (not a mandate) to `mill-start`'s Phase: Explore, Step 3
  (`mill-start/SKILL.md:117-125`). This **introduces** sub-investigation dispatch: Step 3
  currently instructs the orchestrator to explore *directly* and names no Agent dispatch, so
  no existing cold-agent practice is being replaced. New text: prefer
  `Agent(subagent_type: "fork")` for scoped sub-investigations that need the task context
  already in the orchestrator's head; use a cold `Explore` agent for broad mechanical sweeps;
  explore inline when the question is small.
- **Rationale:** The one place in mill with no brief, no resume requirement, no per-role model
  tier, and no tool restriction to lose — so none of the three disqualifiers apply. It is also
  fork's documented use case ("use a fork when a named subagent would need too much background
  to be useful").
- **Rejected:** Mandating fork for all Explore sub-agents (a broad mechanical sweep does not
  benefit from the inherited context and pays the parent's prefix on every turn); no change at
  all.

### no-fork-for-mill-self-report

- **Decision:** Leave `mill-self-report` running in the orchestrator's own context.
- **Rationale:** The strongest remaining candidate — its job is literally "scan your session
  memory", so it is the one skill that *cannot* be delegated to a cold agent. But it fires as
  the **last** step of Handoff, so context reclaimed there is nearly worthless, and the parent
  blocks on the fork anyway.
- **Rejected:** Forking it to guard against auto-compact destroying the session memory it
  needs — real but speculative; revisit if observed.

### reviewers-only-scope

- **Decision:** Apply the new output contract to the **three reviewer dispatch sites only**.
  Implementer, fixer, NIT-fixer, holistic fixer, and both merge-in sub-agents keep today's
  contract verbatim.
- **Rationale:** The reviewer path is *pure*: read files, write a report, report a verdict. It
  has no git side effects, so `finalize` needs no reconciliation logic. The implementer path is
  the opposite — its `finalize` infers completion from **git state**, and its recovery paths
  (`mill-go/SKILL.md:131-141`, `:159-165`) are a minefield: the clean-mid-work-stop route, the
  `stuck_type: incomplete` classification, the warm-`SendMessage` resume, and the explicit
  `#574` false-success hazard where a partial batch must never be accepted as done. Changing
  the implementer's output contract means re-deriving all of that, and a mistake there
  **silently accepts a half-finished batch as complete**. The reviewer path carries no such
  risk, and carries the *bigger* payloads. Take the safe 80%.
- **Consequence — the protocol forks by role, and mill-go must say so.** Step 5 ("capture
  output") becomes **reviewer-skipped**: for a reviewer dispatch the orchestrator does not
  write `.out.md`, because the reviewer already did. For implementer/fixer/merge-in dispatches
  step 5 is unchanged. This asymmetry is temporary and intentional; the follow-up task removes
  it.
- **Rejected:** All nine dispatch sites at once (the original plan — it doubles the change and
  concentrates all the risk in the one path where being wrong is expensive); fork-only with no
  contract fix (abandons the actual token win).

### subagent-writes-its-own-out-md

- **Decision:** The **reviewer** writes its own `<brief>.out.md`. The orchestrator's "capture
  output" `Write` step (`mill-go/SKILL.md:149`) is **skipped for reviewer dispatches**.
  `--stage finalize` continues to read `--agent-output <brief>.out.md` exactly as today, so the
  finalize contract is unchanged.
- **Rationale:** This is the context-bloat fix. Today `mill-go/SKILL.md:123` makes the
  orchestrator read the sub-agent's **entire** final message out of the `<task-notification>`,
  and `:149` makes it **write that whole thing back out**. A full reviewer output — thousands
  of lines of findings — lands in the Builder's context *twice*, even though `:376` and `:820`
  explicitly forbid the Builder from acting on findings. The `--stage full` path never did this:
  the worker wrote the review file itself and the Builder grepped one JSON line out of a log.
  **Agent mode regressed relative to it**; this restores parity.
- **Rejected:** Fork (a fork's final message also returns as a tool result, so it fixes
  nothing here).

### one-line-ack-as-final-message

- **Decision:** The reviewer's final message becomes a single-line ack —
  `WROTE <abs path to .out.md>`. The orchestrator needs nothing from it; the verdict reaches
  the Builder via `finalize`'s stdout JSON envelope, as it already does.
- **Rationale:** Deleting the `Write` step alone only halves the bloat — the notification
  payload is the other half, and it lands in the Builder's context whether or not the Builder
  uses it. Shrinking the final message is what reclaims the budget.
- **Affected classifier edits in `mill-go/SKILL.md`** (small, because 4(b) and the
  clean-mid-work-stop path are **implementer-only** and therefore untouched by this descope):
  - **`:123`** — "Read the subagent's final message from the notification payload — that is the
    text used in steps 4 and 5 below". For reviewers, step 5 is gone; reword so the payload
    feeds step 4's classification only.
  - **step 4(a)** (`:129`) — reworded to key **solely on the error marker**, with the ack test
    evaluated **first**. Its current heuristic ("roughly 0 tokens, no `MILL_REVIEW` block and
    no `status` JSON") becomes misleading: a *successful* reviewer payload is now exactly ~0
    tokens with no `MILL_REVIEW` block. Only the error-marker clause still discriminates.
  - **step 4(c)** (`:143`) — the reviewer/fixer stopped-interrupted liveness probe is
    **unchanged** and still runs first.
  - **step 5** (`:149`) — becomes "skip for reviewer dispatches" (see `reviewers-only-scope`).
  - **step 6** (`:151`) — takes `--agent-output` from the envelope's `output_path`.
  - A reviewer notification that is clean, non-error, and **non-ack** (the agent died before
    writing) has no 4(b) branch — 4(b) is implementer-scoped. It falls through to `finalize`,
    which finds no `.out.md` and emits the existing `ERROR` envelope.
- **Rejected:** Returning the one-line JSON verdict as the final message (redundant with
  `finalize`, and it invites the Builder to trust a channel it should ignore); keeping the full
  output as the final message (halves the fix).

### output-contract-is-agent-mode-only

- **Decision:** The write-your-own-`.out.md` contract applies **only to agent-mode dispatch**.
  The `--stage full` LLM-provider path keeps today's behaviour verbatim: the reviewer returns
  its review **as text** and the backend writes the file.
- **Why this must be said out loud:** the `subprocess` path is **not entirely dead**.
  `mill-go/SKILL.md:129` **retains `--stage full` via `millpy-bg` as the reviewer's fallback
  after two consecutive raw API errors**. The five review templates and the `<TOOL_RULE>` block
  are **shared** between both channels, so a naively-global change would tell a `--stage full`
  reviewer to `Write` a file it has no path for and no permission to write
  (`_llm_claude.py:80` grants at most `Read,Grep,Glob`) — breaking the one path that exists to
  rescue a reviewer when the Agent API is failing, i.e. exactly when you least want a second
  failure.
- **How the split is enforced:**
  - The **output-contract footer** (the absolute `.out.md` path + the ack instruction) is
    appended by `write_brief`, which is called **only** from `--stage prepare`. The
    `--stage full` path builds `prompt_text` and hands it straight to the LLM provider without
    calling `write_brief`. So the footer is agent-mode-only **by construction**.
  - The **`<TOOL_RULE>` block is the problem**, because it lives in shared prompt text and
    hardcodes the opposite rule. `build_tool_rule` becomes dispatch-aware: it takes the
    existing `mode` (`bulk` / `tool-use`) **plus** an agent-mode flag **defaulting to `False`**.
    The default is load-bearing: `test-review-common.py` calls `build_tool_rule` **positionally
    with one argument** at seven sites (`:615`, `:652`, `:690`, `:691`, `:695`, `:2828`,
    `:2880`), so a *required* second parameter would `TypeError` in all seven. With the `False`
    default they stay green, because both non-agent cells are byte-identical to today's text.
  - `<TOOL_RULE>` also becomes the **sole owner of the read-only clause**, since the review
    templates' static header surrenders it (see the edit set).
- **All four cells must be defined — `bulk` × agent-mode is the trap.** `mode` derives from the
  reviewer spec's `tooluse` flag, which **defaults to `False`** (`_reviewers.py:386`), and the
  registry ships `*_bulk` variants selectable as any role's `reviewer` — so this cell is
  reachable today. `_TOOL_RULE_BULK` currently opens with *"Do NOT request tool calls."*, which
  under agent-mode would coexist with "You MAY use Write" — a self-contradiction yielding **no
  `.out.md` and an `ERROR` envelope every round**.

  | | `--stage full` (non-agent) | agent-mode |
  |---|---|---|
  | **bulk** | Unchanged: "Do NOT request tool calls. All content is in this prompt. Do NOT use Write. Return review as text." | "Do NOT request tool calls **to gather content** — everything you need is in this prompt. **The single exception:** you MUST use `Write` exactly once, to write your report to the file named in this brief. Do NOT use `Edit`, and do NOT run git or bash." |
  | **tool-use** | Unchanged: "You MAY use Read, Grep, Glob to verify claims. Do NOT use Write, Edit, or run git/bash. Return review as text." | "You MAY use Read, Grep, Glob to verify claims. You MAY use `Write` **only** to write your report to the file named in this brief. Do NOT use `Edit`, and do NOT run git or bash." |

  Both agent-mode cells name the report file **by description, never by a `<TOKEN>`** (see the
  no-token constraint below), and retain the existing "Review-only, findings only" and "Do NOT
  read `reviews/`" clauses verbatim.
- **Who sets the flag (the obvious answer is wrong):** **not** inside `prepare()`.
  `build_tool_rule` is called *from within* `prepare()` in `_review_discussion.py:82` and
  `_review_code.py:335` — and `run()` (the `--stage full` fallback) calls **that same
  `prepare()`**. A default-on flag there would poison the exact path this Decision protects.
  The flag is a **parameter on each backend's `prepare()`, defaulting to `False`**, set `True`
  **only** by the CLIs' `--stage prepare` branches. `_review_plan.py` is asymmetric:
  - `prepare()` (`:401` batch-scope, `:490` holistic-scope) — **both carry the flag.**
    `prepare()` takes `scope: str | None`, so batch-scope is reachable even though the hub
    disables plan batch review today (`rounds: 0`).
  - `run()` (`:836`) and `_review_one_batch` (`:196`) — **both keep the non-agent rule.**
    `_review_one_batch` is not a separate entry point; it is submitted to a `ThreadPoolExecutor`
    from `run()` (`:752`), so it is `--stage full`-only. **Do not thread the flag into it.**

### output-path-in-prepare-envelope

- **Decision:** The three **review** prepare envelopes gain an **additive** `output_path` field
  holding the absolute `.out.md` path. The `.md` → `.out.md` rule lives in exactly one helper in
  `_agent_dispatch.py`.
- **`write_brief` gains an optional `output_contract` flag, default `False`.** Only the three
  review CLIs pass `True`. Consequences that keep this change small:
  - Implementer/fixer/merge-in briefs are rendered **byte-identically to today** (they go
    through `_implementer_common.emit_prepare`, which does not pass the flag).
  - `write_brief`'s **return shape is unchanged** (still the brief `Path`); the `.out.md` path
    comes from a separate `output_path_for(brief_path)` helper. This keeps
    `test-agent-dispatch.py` and `test-agent-mode-dispatch.py` green, including the latter's
    `brief_content == prompt_text` assertion.
- **No `<OUTPUT_FILE>` token anywhere — a hard constraint, not a preference.** `_render.render`
  (`_render.py:35`) matches `<[A-Z][A-Z0-9_]*>` and **raises `KeyError: Unresolved template
  tokens`** for any such token missing from the caller's `values` dict; every review prompt is
  rendered through it (`_review_common.py:1359`). A literal `<OUTPUT_FILE>` in a template would
  hard-fail rendering **before** `write_brief` runs, and is unsuppliable on `--stage full`
  anyway. Agent definitions are static text never passed through `_render`, so a token there
  would reach the model raw. Therefore: **templates and agent definitions name the report file
  by description only**, and the literal absolute path arrives **solely** in `write_brief`'s
  appended footer.
- **Carve-outs — envelopes that write no brief carry no `output_path`.** The invariant is
  "`output_path` is present on every **brief-emitting success** envelope". Excluded: the
  plan-validator failure envelope (`millpy-review-plan.py:142-147` emits
  `{"errors": [...], "summary": ...}` and exits 1 before any brief is rendered), and
  `print_error_envelope` from the three review CLIs' `--stage prepare` branch.
- **Rejected:** Keeping the `.md` → `.out.md` munging rule as SKILL.md prose (it is restated in
  four places today); having the orchestrator substitute a token (impossible — the brief is
  already on disk by then).

### write-brief-truncates-stale-out-md

- **Decision:** `write_brief` **deletes any pre-existing `.out.md`** (`unlink(missing_ok=True)`)
  at brief-write time — unconditionally, for all roles. A dead reviewer therefore always yields
  a genuinely **absent** file, never a stale one.
- **Rationale — this is a hole the change itself opens.** Today the orchestrator rewrites
  `<brief>.out.md` immediately before every `finalize`, so the file is **always fresh by
  construction**. Removing that `Write` for reviewers destroys the invariant, and **nothing
  anywhere in `scripts/` unlinks or truncates `.out.md`** (verified). Step 4(a)'s transient
  retry re-dispatches with the **same role/scope/round**, hence the **same `.out.md` path** — so
  if attempt 1 writes the file and attempt 2 dies before writing, `finalize` reads **attempt 1's
  output as attempt 2's result**. The missing-file guard does not save us: it covers *absent* and
  *empty*, not *stale*.
- **Why this is severe for reviewers specifically:** implementers have a genuine backstop — the
  git-state completeness recount reconciles any bogus report against actual commits.
  **Reviewers have none.** The review CLIs parse the verdict straight out of the file text, so a
  killed-then-retried reviewer that had written `APPROVE` before dying would hand mill-start or
  mill-plan a **green verdict that no live reviewer produced**. Unconditional truncation is
  harmless for implementers (the orchestrator overwrites `.out.md` before their finalize anyway),
  so there is no reason to make it role-conditional.
- **Rejected:** An mtime freshness check (`.out.md` newer than the brief) — works, but is
  clock-dependent and fails silently on coarse filesystem timestamps; deterministic deletion is
  strictly better. Trusting the agent to always overwrite the file — that assumption is exactly
  what fails when the agent dies.

### missing-out-md-yields-error-envelope

- **Decision:** Add a **missing-file guard** at the three review read sites
  (`millpy-review-discussion.py:146`, `millpy-review-plan.py:185`, `millpy-review-code.py:183`):
  read the file defensively, yielding `""` when it does not exist. The empty text then fails
  `parse_verdict`, raising `ReviewError`, which produces the **existing** `verdict: ERROR`
  envelope — already handled by mill-start's and mill-plan's ERROR-only-aggregate retry (their
  step 3.5) and mill-go's reviewer fallback.
- **Rationale:** The guard is **not optional**, and "existing machinery already covers this" is
  false without it. All three sites currently call `Path(agent_output_path).read_text(...)` with
  **no existence guard**, and they wrap the read in `except ReviewError` only — which
  `FileNotFoundError` does **not** satisfy. Today an absent file exits with a traceback and
  prints no envelope at all. An *empty* file already degrades correctly; a *missing* one crashes.
  The guard collapses missing into empty, after which existing behaviour takes over.
- **Rejected:** A synthetic `stuck_type: transient` envelope for reviewers — a new code path
  where the existing `ERROR` envelope already does the job.

### reviewer-write-grant-scoped-to-briefs

- **Decision:** Add `Write` to `mill-reviewer`'s tool list. Restrict it to `_mill/briefs/` by a
  **prompt guardrail** in the agent definition plus the explicit absolute path in `write_brief`'s
  footer. The reviewer writes **only** its own `.out.md`.
- **Rationale:** Narrowest grant that makes the contract work. The reviewer does *not* need to
  write the review file — `finalize` still owns `_mill/reviews/` and renders it from `.out.md`.
- **Honest limitation (do not paper over this):** agent-definition `tools:` frontmatter grants
  capabilities **wholesale, with no path scoping**. Adding `Write` grants it **repo-wide**, and
  "the reviewer cannot touch source code or git" degrades from a *construction-level invariant*
  to a *prompt instruction*. Accepted because the reviewer has no motive, the footer names one
  exact absolute path, and it still holds no `Bash` and no `Edit` — so it cannot commit, run
  commands, or modify existing files; only create/overwrite by full path.
- **Considered, not in scope:** a plugin-shipped `PreToolUse` hook denying `Write` outside
  `_mill/briefs/` for the `mill-reviewer` agent would restore genuine enforcement. The correct
  follow-up if the advisory guardrail proves insufficient.
- **Rejected:** Granting `_mill/reviews/` too and making `finalize` a pure parser — more moving
  parts, wider grant, no benefit.

### remove-html-unescape

- **Decision:** Delete the `html.unescape()` call at the **three review** read sites
  (`millpy-review-code.py:183`, `millpy-review-plan.py:185`, `millpy-review-discussion.py:146`)
  and drop the now-unused `import html` in each. **`_implementer_common.py:892` keeps its
  `html.unescape` unchanged** — implementers still route through the HTML-escaped notification.
- **Rationale:** Those calls exist because the harness HTML-escapes the `<task-notification>`
  payload (fix #605) and the orchestrator wrote that escaped payload to `.out.md`. Once the
  **reviewer** writes the file directly, its content is never escaped — and unescaping it anyway
  **corrupts** any literal `&lt;`, `&gt;`, or `&amp;` appearing inside quoted source code in a
  finding. Leaving them in trades a token bug for a correctness bug. The implementer path is
  unchanged, so its unescape is still correct and must stay.
- **Rejected:** Leaving them as defensive no-ops. They are not no-ops; they are actively
  destructive on legitimate content.

### decision-note-for-fork-rejection

- **Decision:** Record the fork rejection as a short "Why not fork?" subsection at the end of
  `mill-go/SKILL.md`'s `## Agent-mode dispatch` section.
- **Content (~six lines):** fork inherits the parent's context but (1) always runs on the
  parent's model and ignores a `model` override, breaking `roles.*.model` tiers; (2) inherits the
  *parent's* tools, so a forked reviewer would hold `Edit`/`Write`/`Bash` and lose its read-only
  guarantee; (3) has no on-disk brief, so a forked dispatch cannot be resumed after a crash.
  Fork is therefore used only in mill-start's Explore phase.
- **Rationale:** "Why don't we just fork the reviewer?" will recur, and `## Agent-mode dispatch`
  is where the next person will be standing when they ask. Needs no new docs convention (the repo
  has no `docs/decisions/`).
- **Rejected:** Relying on `discussion.md` alone (it is squash-merged into history where nobody
  finds it); inventing an ADR directory for one note.

## Technical context

**The dispatch protocol** is documented once, in `mill-go/SKILL.md` §"## Agent-mode dispatch"
(~lines 105–175); every other skill points at it. It is prepare → Agent → finalize:

- `--stage prepare` renders the brief via `_agent_dispatch.write_brief()` and emits a JSON
  envelope: `{stage, brief_path, subagent_type, model, session_id, role, scope, round, …}`.
- The orchestrator calls the `Agent` tool with `prompt: "Read this file and follow the
  instructions exactly: <brief_path>"`, then waits for the `<task-notification>`.
- **Step 5 (`:149`) — the defect:** "Write the message captured from the `<task-notification>` to
  `<brief_path>.out.md`."
- `--stage finalize --agent-output <brief>.out.md` parses the file and emits the verdict JSON that
  the Builder actually consumes.

**The three reviewer dispatch sites in scope:**

| Site | Skill → CLI | Template |
|---|---|---|
| Discussion review | `mill-start` → `millpy-review-discussion.py` | `review-discussion.md` |
| Plan review | `mill-plan` → `millpy-review-plan.py --holistic-only` | `review-plan-{batch,holistic}.md` |
| Code review (batch + holistic) | `mill-go` → `millpy-review-code.py` | `review-code-{batch,holistic}.md` |

All three spawn `mill:mill-reviewer` and emit
`{type, round, verdict, blocking_count, nit_count, reviews:[{scope, verdict, file, session_id}]}`
from finalize. That envelope is unchanged by this task.

**What an `.out.md` must contain.** Unchanged from what the reviewer emits today, only
redirected: the whole `MILL_REVIEW_BEGIN … MILL_REVIEW_END` block including the fenced yaml
verdict and the `## Findings` body, which `finalize` renders into `_mill/reviews/`. **Only the
delivery channel changes** — the report goes to the file instead of the chat, and the final
message becomes the ack.

**Authoritative edit set — 19 files (1 + 5 + 3 + 8 + 2).** This is the **single** enumerated
list, and the only file count in this document; the conformance test asserts against it.

*Group 1 — agent definition (1 file):*

- `plugins/mill/agents/mill-reviewer.md` — "Your sole output is your final message. Do not create
  intermediate files…" must go; tool list gains `Write`; add the `_mill/briefs/` guardrail,
  naming the report file **by description** (no token — agent definitions never pass through
  `_render`). `mill-implementer.md` is **not** touched (descope).

*Group 2 — the five review templates (5 files):*

- `plugins/mill/templates/review-{code-batch,code-holistic,discussion,plan-batch,plan-holistic}.md`.
  **The contradiction is the static READ-ONLY header, not a JSON clause.** All five open with
  identical prose (`review-discussion.md:1-4`, same at `review-code-batch.md:1-4` et al.): *"You
  are a READ-ONLY reviewer. You MUST NOT call Edit, **Write**, Bash… **Your sole output is the
  review file in the format below.**"* That is **static template prose on a shared channel, so
  unlike `<TOOL_RULE>` it cannot be made dispatch-aware.** Resolution:
  - **Delete the tool prohibitions from the header** and let the dispatch-aware
    `build_tool_rule` own the **entire** read-only clause — it is the only channel-aware
    injection point in the review prompt, so all tool permissions must live there and nowhere
    else.
  - **Keep** the non-tool half: "You are an independent reviewer. REPORT issues; do NOT fix
    them."
  - **Keep the `MILL_REVIEW_BEGIN` … `MILL_REVIEW_END` wrapper and the review format** — that is
    the *content format of the `.out.md` file*, which `finalize` parses. Only "Your sole output is
    the review file in the format below" changes, to say the report is **written to** the file
    named in the brief and the final message is the ack.
  - **Also sweep the "source-grounding" paragraph** (`review-discussion.md:21` and counterparts),
    which statically asserts *"You are in tool-use mode — … open it with Read/Grep/Glob"*. That is
    a tool statement outside `build_tool_rule`, and it is **already wrong today** for a `bulk`
    reviewer (told the opposite two paragraphs earlier). Fold the mode-specific clause into
    `build_tool_rule`; leave the paragraph with only its channel-neutral half ("Never fabricate
    file contents or code behaviour you have not actually read"). A pre-existing bug this sweep
    fixes for free.

*Group 3 — orchestrator skills (3 files):*

- `plugins/mill/skills/mill-go/SKILL.md` — `:123`, step 4(a) (`:129`), step 5 (`:149`, becomes
  reviewer-skipped), step 6 (`:151`). Steps 4(b), 6.5 and the Clean mid-work stop paragraph
  (`:131-141`, `:159-165`) are **implementer-only and stay untouched**. Plus the new "Why not
  fork?" subsection.
- `plugins/mill/skills/mill-start/SKILL.md` — Phase: Explore Step 3 (`:117-125`) gains the fork
  guidance (item A); and the stale rationale at `:152` (below).
- `plugins/mill/skills/mill-plan/SKILL.md` — the stale rationale at `:111` (below).

*Group 4 — Python (8 files):*

- `_agent_dispatch.py` — the `.md` → `.out.md` helper; `write_brief` gains the optional
  `output_contract` flag (default `False`), appends the footer with the literal absolute path,
  and **unlinks any stale `.out.md`**. Return shape unchanged.
- **`_review_common.py`** — **the easiest file in this change to miss, because the contradiction is
  injected from Python, not from a template.** `_TOOL_RULE_BULK` and `_TOOL_RULE_TOOL_USE`
  (`:1216-1228`) hardcode `**CRITICAL: Do NOT use Write. Return review as text.**`, and
  `build_tool_rule` (`:1231`) feeds that into **every** review prompt. Make it dispatch-aware per
  the four-cell matrix. Its docstring ("Write, Edit, and shell access are forbidden in both
  modes — the backend owns file writes and git") also stops being true for agent mode.
- `_review_discussion.py`, `_review_code.py`, `_review_plan.py` — thread the agent-mode flag
  through `prepare()` (`_review_discussion.py:82`, `_review_code.py:335`,
  `_review_plan.py:401,490`). **Do not** thread it into `_review_plan.py:196` or `:836`.
- `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py` — prepare
  envelopes gain `output_path`; each passes `output_contract=True` to `write_brief` and sets the
  agent-mode flag `True` in its `--stage prepare` branch **only**; read sites `:146` / `:185` /
  `:183` gain the missing-file guard and lose `html.unescape` (+ the `import html`).

**Explicitly *not* in the edit set:** `_implementer_common.py`, `millpy-implement.py`,
`millpy-fix.py`, `millpy-merge-in-subagent.py`, all five non-review brief templates, and
`mill-implementer.md`. They keep today's contract. This is the descope, and the plan must not
create batches for them.

*Group 5 — existing tests that go red (2 files):*

- `unit_tests/test-agents-defs.py:60-69` — asserts `mill-reviewer`'s tools are **exactly**
  `{Read, Grep, Glob}` and that none of `{Edit, Write, Bash, NotebookEdit}` is present. **This
  test *is* the reviewer safety invariant, not incidental scaffolding** — do not weaken it to a
  subset check. New assertion: exactly `{Read, Grep, Glob, Write}`, with `Edit`, `Bash`, and
  `NotebookEdit` still forbidden.
- `unit_tests/test-review-finalize.py` — the three
  `test_review_{code,plan,discussion}_finalize_unescapes_html_entities` tests assert `finalize`
  **unescapes** HTML entities. Under `remove-html-unescape` the assertion **inverts**: the text
  must survive **byte-identically**, entities and all. Rewrite them rather than delete — the #605
  concern is real, it just moves.

Staying green, and worth stating so the plan does not chase them:
`test-implementer-common.py` (case 63 — the implementer path is untouched, so its unescape stays),
`test-agent-dispatch.py` and `test-agent-mode-dispatch.py` (`write_brief`'s return shape and
default rendering are unchanged), and `test-review-common.py` (the agent-mode flag defaults to
`False`, so its seven positional `build_tool_rule` calls still work).

**Downstream rationale that goes stale.** `mill-start/SKILL.md:152` and `mill-plan/SKILL.md:111`
both pre-emptively load `mill-receiving-review`, justified by the claim that "under Agent-mode
dispatch a reviewer's findings arrive already embedded in the `<task-notification>` payload the
orchestrator must read just to learn the round's verdict". After this change that is **no longer
true** — findings arrive only in the review file. The pre-emptive load is still *correct* (the
orchestrator must have the skill active before it reads the review file to present gaps or NITs),
but the stated reason must be rewritten or it will mislead the next reader.

**Relationship to the deferred `mill-orchestrator` task (id 0).** Its core principle is "Thread B
never reads source files", and its own context-budget evidence section already names this defect
class. The two are **complementary**: id 0 restructures *who* orchestrates; this task fixes *what
the orchestrator is forced to read*. Landing this makes id 0 cheaper. Fork is orthogonal to both.

**Fork availability** (verified): requires Claude Code ≥ 2.1.117, on by default from 2.1.161; this
environment runs 2.1.207. `subagent_type: "fork"` is present in the orchestrator's own `Agent` tool
schema. It **cannot** be dispatched by mill's Python CLIs — it is a harness-level feature — a
further structural reason it can only appear in SKILL.md-level guidance, never in a `prepare`
envelope.

## Constraints

- No `CONSTRAINTS.md` at the hub root.
- `finalize`'s external contract (`--agent-output <path>`, and the JSON envelopes it emits) must
  not change — mill-go, mill-start, and mill-plan all parse those envelopes. Adding `output_path`
  to the *prepare* envelope is additive and does not violate this.
- **The implementer path must come out byte-identical.** The descope is only safe if
  implementer/fixer/merge-in briefs, envelopes, and finalize behaviour are provably unchanged.
  `write_brief`'s `output_contract` flag defaulting to `False` is what guarantees this.
- **`--stage full` must keep working.** It is the reviewer's API-error fallback; both non-agent
  `build_tool_rule` cells stay byte-identical to today's text.
- The reviewer must not touch source code or git. Note this becomes a **prompt guardrail**, not a
  construction-level guarantee, once `Write` is granted — `tools:` frontmatter has no path scoping.
- Briefs are committed artifacts (`git add _mill/briefs/` throughout mill-go). The `.out.md` files
  land in the same directory and are committed with them, so the audit trail is preserved — the
  reviewer's full output stays on disk and in git, it simply stops passing through the
  orchestrator's context.
- ASCII-only in `print()` / `_log()` output (Windows cp1252).

## Testing

Unit tests live in `plugins/mill/unit_tests/test-<name>.py`, run via `run-all.py`, with
in-memory/tempfile fixtures and no real git or LLM. That suits every part of this change except the
SKILL.md edits, which are prose and verified by inspection.

**Scope note:** the 19-file edit set enumerates contract-carrying files plus the two tests that go
red. The *new* assertions below are **additive** and not bounded by that list — they extend
existing suites (`build_tool_rule` cases → `test-review-common.py`; footer, truncation, and
no-token cases → `test-agent-dispatch.py`; missing/empty/stale cases → `test-review-finalize.py`)
plus one new suite for the conformance sweep. The conformance test asserts *against* the edit set;
it is not a member of it.

- **`build_tool_rule` — all four cells, TDD candidate.** Assert **`bulk` × full**, **`bulk` ×
  agent**, **`tool-use` × full**, **`tool-use` × agent**. The two `--stage full` cells must be
  **byte-identical to today's text** — that is what stops the reviewer's API-error fallback from
  being collaterally broken. The `bulk` × agent cell matters most: assert it does **not** contain a
  bare "Do NOT request tool calls" that would contradict the Write instruction, and that it *does*
  carve out the single `Write`. Assert every agent-mode cell still forbids `Edit`, git, and bash.
  Assert the flag **defaults to `False`**.
- **`finalize` on a missing / empty / stale `.out.md` — the most important TDD candidate.**
  - *missing / empty / whitespace-only:* assert the `verdict: ERROR` envelope is emitted for each
    of the three review CLIs (**not** a traceback — the current code raises an uncaught
    `FileNotFoundError` on missing, so this test fails on today's code, which is the point).
  - *stale:* write an `.out.md` containing `APPROVE`, then call `write_brief` for the same
    role/scope/round, then run `finalize`. Assert the pre-existing file **did not survive** — the
    reviewer must NOT report `APPROVE`. This is the regression guard for
    `write-brief-truncates-stale-out-md`; without truncation, a killed-then-retried reviewer's old
    green verdict is silently reused, and this test is the only thing that catches it.
- **`html.unescape` removal — regression test.** A finding whose body quotes source code containing
  a literal `&lt;`, `&gt;`, and `&amp;` must round-trip through the three review `finalize` paths
  **byte-identically** into the review file. Fails on today's code; pins the correctness bug the
  removal fixes. **Assert the converse for the implementer path:** `_implementer_common`'s unescape
  still fires (the descope means its behaviour must not change).
- **`write_brief` output-contract footer + default-off.** Assert that with `output_contract=True`
  the written brief ends with a footer naming the absolute `.out.md` path as literal text and
  instructing the ack; and that with the flag **omitted** the brief is byte-identical to
  `prompt_text` — the guarantee that the implementer path is untouched.
- **`write_brief` truncation.** Assert a pre-existing `.out.md` is unlinked at brief-write time,
  for every role.
- **Prepare-envelope shape.** Assert `output_path` is present, absolute, and equals `brief_path`
  with `.md` → `.out.md` on every **brief-emitting success** envelope from the three review CLIs.
  **Assert the converse for both carve-outs:** the plan-validator `{"errors": …}` envelope and
  `print_error_envelope` carry no `output_path`.
- **No-token regression test.** Assert no template under `templates/` and no agent definition under
  `agents/` contains an `<OUTPUT_FILE>` token, and that `_render.render` succeeds on every template
  with its normal `values` dict. Pins the `_render.py:35` constraint that made the first token
  design unbuildable.
- **Conflicting-instruction conformance sweep.** Assert no *agent-mode reviewer* prompt still says
  its sole output is its final message, or forbids `Write`. **Search root must include `scripts/`,
  not just `templates/` and `agents/`** — the `<TOOL_RULE>` contradiction is injected from
  `_review_common.py`, so a doc-directories-only sweep provably cannot catch it. Better: assert
  against the **rendered `prompt_text`** for each of the three reviewer sites, which catches
  contradictions regardless of source file.

Not covered by unit tests, and accepted: that the orchestrator's context actually shrinks. Verify
manually on the first real review round after this lands, by observing that the
`<task-notification>` payload is one line instead of a full findings dump.

## Q&A log

- **Q:** Given fork is a poor fit for the scripted dispatch sites, what should this task build? **A:** Fork where it fits, *and* fix the `.out.md` bloat — it is the motivating problem and fork cannot solve it.
- **Q:** Which dispatch sites get the new contract? **A:** Initially all nine; **revised to reviewers only** after review showed the implementer half drags in the `#574` classifier hazard, the git-state recount, and the warm-resume path. Reviewers carry the biggest payloads and none of the risk. Implementers follow as a separate task.
- **Q:** Fork `mill-self-report`? **A:** No. It fires as the last step of Handoff, so the context it would save is nearly worthless.
- **Q:** How should mill-start's Explore phase use fork? **A:** Guidance, not a mandate — prefer fork for scoped sub-investigations that need the task context; cold `Explore` agents for broad mechanical sweeps.
- **Q:** What is the reviewer's final message once it writes its own `.out.md`? **A:** A one-line ack (`WROTE <path>`). The Builder needs nothing from it — `finalize` supplies the verdict.
- **Q:** How do we preserve the reviewer's read-only invariant while letting it write? **A:** Grant `Write` guardrailed to `_mill/briefs/`. Honest caveat: `tools:` frontmatter has no path scoping, so this is a prompt guardrail, not a construction-level guarantee. A `PreToolUse` hook is the follow-up if that proves insufficient.
- **Q:** What if the reviewer dies before writing `.out.md`? **A:** Add a missing-file guard at the three review read sites — today an absent file raises an uncaught `FileNotFoundError` — after which the existing `ERROR` envelope and its retry path take over.
- **Q:** Deleting the orchestrator's `Write` also deletes the guarantee that `.out.md` is fresh. What replaces it? **A:** `write_brief` unlinks any pre-existing `.out.md` at brief-write time. Nothing in mill truncates it today, and the transient retry reuses the same path — so without this, a killed-then-retried reviewer could return a stale `APPROVE` that no live reviewer produced. Reviewers have no git-state backstop. Rejected an mtime check as clock-dependent.
- **Q:** Does the new contract apply to the `--stage full` reviewer path? **A:** No — agent-mode only. `--stage full` is *not* dead: it is the reviewer's fallback after two consecutive API errors, and it shares the review templates and `<TOOL_RULE>`. The footer is agent-mode-only by construction (`write_brief` is prepare-only), but `build_tool_rule` must be made dispatch-aware so the two channels don't get contradictory instructions.
- **Q:** What does `build_tool_rule` emit for a **bulk** reviewer under agent-mode? **A:** All four cells are enumerated. bulk×agent is the trap — `tooluse` defaults to `False`, so it is reachable — and its "Do NOT request tool calls" clause must be narrowed to "no tool calls **to gather content**, with the single exception of the one `Write` of your report", or the reviewer writes no file and returns `ERROR` every round.
- **Q:** Can the templates carry an `<OUTPUT_FILE>` token? **A:** **No.** `_render.render` raises `KeyError` on any unresolved `<UPPERCASE>` token, so a token in a template hard-fails rendering *before* `write_brief` runs, and agent definitions never pass through `_render` at all. Templates and agent defs name the file by description; `write_brief` appends a footer with the literal path.
- **Q:** The review templates open with a static "READ-ONLY reviewer / MUST NOT call Write" header. How is that reconciled? **A:** The tool prohibitions are **deleted from the header** and `build_tool_rule` becomes the sole owner of the read-only clause — a static template cannot be made dispatch-aware. The `MILL_REVIEW_BEGIN`/`END` wrapper stays: it is the content format of the `.out.md`.
- **Q:** How does the implementer path stay safe under the descope? **A:** It is byte-identical. `write_brief`'s `output_contract` flag defaults to `False`, its return shape is unchanged, and `_implementer_common.py` is not touched — including its `html.unescape`, which is still correct there.
- **Q:** How should review gaps be resolved for the rest of this mill-start? **A:** Auto-pick the recommended option on every review round.
