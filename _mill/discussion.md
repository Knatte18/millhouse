# Discussion: Audit mill-start/mill-plan/mill-go for turn reduction

```yaml
task: Audit mill-start/mill-plan/mill-go for turn reduction
slug: turn-reduction-audit
status: discussing
parent: main
```

## Problem

Mill orchestration is slow mainly from LLM round-trip latency (the number of separate tool-call
turns a run takes), not raw script CPU time — worse on a Win11 machine running the Cortex EDR,
which scans per-process-spawn and per-file-import, independent of whether Python itself is fast
enough.
`mill-start`, `mill-plan`, and `mill-go-base` all repeat the same shape dozens of times: a
deterministic, no-judgment read/write/branch, executed as its own separate Bash-tool turn, right
next to genuine LLM reasoning or Agent dispatch that legitimately needs to stay a visible turn.
This task produces the audit that identifies which of those repeated shapes are safe to mechanize
into a single script call, before any of that mechanization is actually built.

## Scope

**In:**

- Walk every numbered step / phase in `plugins/mill/skills/mill-start/SKILL.md`,
  `plugins/mill/skills/mill-plan/SKILL.md`, and `plugins/mill/skills/mill-go-base/SKILL.md`,
  classifying each as **Mechanical/collapsible**, **Borderline**, or **Excluded** per the scheme
  below.
- Confirm whether `plugins/mill/skills/mill-go/SKILL.md` and
  `plugins/mill/skills/mill-go2/SKILL.md` add any step sequences of their own beyond loading
  `mill-go-base` (this discussion's own exploration already found: no — see Technical context).
- For each Mechanical/collapsible candidate: step range, what each step currently does, whether
  the mechanical work is already scripted per-step (so the only win is collapsing N
  script-invoking turns into 1) or involves un-scripted logic, and a rough per-run turn-count
  saving.
- For each Borderline candidate: why it can't be a blind collapse, and the partial-collapse
  question resolved under Decisions below.
- Produce one permanent, reviewable audit document: `doc/turn-reduction-audit.md`.

**Out:**

- Implementing any candidate (new helper functions, new `millpy-*.py` scripts, SKILL.md edits).
  Every accepted candidate becomes its own follow-up backlog task once this audit is reviewed.
- `mill-merge`/`mill-finalize` and any other skill. The task's own background section cites
  `mill-merge`'s 8-9-step shape only as *motivating example* for why this problem matters — the
  task's own "What needs to happen" section names only `mill-start`/`mill-plan`/`mill-go-base`
  (+ `mill-go`/`mill-go2`) as audit targets. Auditing `mill-merge` or other skills is explicitly
  a separate future task, not folded in here silently.
- The Go/Cobra rewrite mentioned in the task's background — explicitly out of scope, mechanizing
  turns is the language-agnostic first step.
- A full, formally exhaustive verification that the audit doc lists literally every character of
  every SKILL.md — the review criterion (see Testing) is "every `###`/numbered step is assigned to
  exactly one bucket," which is checkable without re-deriving each file from scratch.

## Decisions

### Audit document location and format

- Decision: The deliverable lives at `doc/turn-reduction-audit.md`, git-tracked at the repo root's
  existing `doc/` directory (alongside `doc/backlog.md`, `doc/v3-architecture.md`,
  `doc/psmux-tui-behavior.md`), using the repo's fenced-`yaml`-metadata-block convention (not `---`
  frontmatter, which CLAUDE.md reserves for SKILL.md/plugin manifests).
- Rationale: `_mill/` is deleted or restored-from-base at merge time (CLAUDE.md's "Never cite
  `_mill/discussion.md`... from a permanent doc" rule generalizes: nothing in `_mill/` survives
  merge). Since this task's entire deliverable *is* a permanent document, it cannot live in
  `_mill/`. `doc/` is the repo's existing, git-tracked home for exactly this kind of durable design
  document — precedent already established by `doc/backlog.md` and `doc/v3-architecture.md`.
- Rejected: a wiki page (CLAUDE.md: "Wiki holds only `Home.md`" — not a valid destination for a
  standing design doc); leaving it only in `_mill/discussion.md` or a review file (both wiped or
  effectively inaccessible after merge).

### Classification scheme (carried over from the task body, restated for mill-plan)

- Decision: Use the task body's three buckets verbatim — **Mechanical/collapsible** (deterministic,
  no judgment call, no Agent dispatch, no operator-facing halt/prompt in between — candidate for a
  single script call), **Borderline** (mechanical on paper but entangled with a halt message, an
  operator-visible phase name, or brackets an Agent dispatch — needs explicit design treatment),
  **Excluded** (genuine LLM reasoning, judgment, Agent dispatch, or a round-by-round loop per
  `plugins/mill/skills/workflow/SKILL.md`'s anti-pattern #2).
- Rationale: this scheme is already well-specified in the task body and matches this repo's own
  documented anti-pattern rule; no reason to invent a different one.
- Rejected: a finer-grained or binary (collapsible / not) scheme — loses exactly the distinction
  (Borderline) that keeps a later implementer from blindly collapsing something that shouldn't be.

### Helper-function home for the `append_phase` + git-commit pattern

- Decision: **Do not** add the proposed `append_phase_and_commit` (or equivalent) helper to
  `_status.py` itself. The audit document should record this as a recommendation for whichever
  follow-up task implements candidate #1: house it in a new, separate module (e.g.
  `_status_commit.py`) that composes `_status.append_phase` with the existing
  `_subprocess_util.git_commit` helper (`plugins/mill/scripts/_subprocess_util.py:219`), plus
  `git add`/`git push`.
- Rationale: `_status.py` (1482 lines) currently has **zero** git/subprocess imports — it is pure
  YAML/file manipulation, which is exactly what lets `plugins/mill/unit_tests/` test it with
  in-memory/tempfile fixtures and no real git (per CLAUDE.md's `unit_tests` description and
  `mill:testing`/`python:python-testing`). Adding a git-committing function to `_status.py` would
  break that separation and force every future `_status.py` unit test to either mock git or become
  an integration test. A separate module preserves both the existing test story and the existing
  `_subprocess_util.git_commit` precedent (already used elsewhere for exactly this kind of
  author-pinned commit).
- Rejected: growing `_status.py` directly (task body's own phrasing, "should it live in `_status.py`
  itself" — rejected for the testability reason above); a bespoke ad hoc subprocess call per site
  instead of a shared helper (defeats the whole point of collapsing turns).
- This is a recommendation for the audit document to record against candidate #1, not an
  implementation performed by this task.

### Borderline treatment: partial collapse over all-or-nothing

- Decision: For every Borderline candidate, the audit document must record **two** alternatives —
  full exclusion (leave the step sequence entirely as orchestrator-driven text) and a
  scoped partial collapse (a script call does only the deterministic read+classify work and
  returns a JSON blob; the SKILL.md keeps ownership of the actual halt-message text, the
  operator-facing phase name, and the decision of which named branch to take) — with an explicit
  recommendation between them, never a forced single verdict.
- Rationale: this discussion's own exploration of `mill-plan/SKILL.md` Entry step 4 (the task
  body's own cited Borderline example) found it has grown substantially since the task's
  first-pass audit — it is no longer just a "~60 lines" phase-table branch. As currently written it
  spans roughly `plugins/mill/skills/mill-plan/SKILL.md:54-138` and now includes `--revise`/
  `--approve` pre-checks, an entry-gate wait for upstream `mill-start`, and a full blocked-resume
  procedure — each ending in a distinct, differently-worded halt or fallthrough. Collapsing that
  whole thing into one opaque script call would hide exactly the operator-facing decision points
  the Borderline bucket exists to protect. But the underlying *reads* (parse `phase:`, `approved:`,
  `blocked_reason:`, decide which table row matches) are still fully deterministic and could be one
  script call that returns "which row/branch applies" — leaving the SKILL to keep only the
  branch-specific halt text and any Agent-dispatch bracket.
- Rejected: forcing every Borderline candidate to an all-or-nothing verdict (task body's own
  phrasing of the open question) — rejected because the one concrete Borderline example examined
  during this discussion clearly benefits from a scoped split, and a blanket rule would either
  under-collapse (leave clearly-mechanical read/parse work fully manual) or over-collapse (bury a
  halt decision inside a script's exit code, the exact risk the task body itself flags for this
  candidate).

### First-pass findings are a starting point, not ground truth

- Decision: The audit document must re-verify every count and line reference the task body's
  "Findings so far" section cites against the current worktree source, not copy them verbatim.
- Rationale: this discussion's own spot-check already found drift in two days: `mill-go-base`'s
  `_status.append_phase` call count is 21 in the current source vs. the first-pass audit's cited
  22; candidate #3 (`mill-go-base`'s `## Prepare` section, `plugins/mill/skills/mill-go-base/SKILL.md:209-215`)
  checked out exactly as described and is a clean, accurate example of the pattern; candidate #2
  (Entry path/config/slug resolution, mirrored in `mill-start/SKILL.md:85-95` under `## Entry` and
  `mill-plan/SKILL.md:33-45` under the same heading) also checked out. The one cited Borderline
  case checked out as *understated*, not wrong (see previous Decision). Per CLAUDE.md's own
  "Task-worktree path for source verification" rule, all of this must be read from the task
  worktree, never the plugin cache, since the two can silently diverge.
- Rejected: treating the task body's first-pass numbers as authoritative and skipping
  re-verification — this is precisely what the task itself asked for ("to be verified/deepened by
  this task").

## Technical context

- Files to walk: `plugins/mill/skills/mill-start/SKILL.md` (441 lines), `.../mill-plan/SKILL.md`
  (685 lines), `.../mill-go-base/SKILL.md` (996 lines). Also read `.../mill-go/SKILL.md` (29
  lines) and `.../mill-go2/SKILL.md` (105 lines) — this discussion already confirmed both add no
  mechanical sequences of their own: `mill-go` is a bare "load `mill-go-base`, follow it" wrapper;
  `mill-go2` only overrides dispatch calls with fork/cold-fallback branching logic (judgment, not
  mechanical) and preloads a fixed skill set once per session. State this confirmation in the audit
  doc rather than re-deriving it.
- `_status.append_phase` call-site counts in the current worktree (a starting point for candidate
  #1, not a final count): `mill-start/SKILL.md` — 6, `mill-plan/SKILL.md` — 14,
  `mill-go-base/SKILL.md` — 21. `commit -m` occurrence counts track the same shape: 6 / 21 / 17
  respectively (not a 1:1 match to `append_phase` counts since some commits bundle other files with
  no preceding `append_phase`, or vice versa — the audit doc should note actual paired vs.
  unpaired sites, not just raw counts).
- `_status.py` (`plugins/mill/scripts/_status.py`, 1482 lines) has no git/subprocess imports today
  — see the "Helper-function home" decision above for why this matters.
- `_subprocess_util.git_commit` (`plugins/mill/scripts/_subprocess_util.py:219`) is the existing
  precedent for issuing an author-pinned git commit from Python; any new commit-composing helper
  should build on it rather than inventing a second git-commit wrapper.
- `doc/` (repo root) is the existing precedent for permanent, git-tracked design docs
  (`doc/backlog.md`, `doc/v3-architecture.md`, `doc/psmux-tui-behavior.md`), using fenced-`yaml`
  metadata blocks — see `doc/backlog.md`'s own opening block for the exact style to match.
- `plugins/mill/skills/workflow/SKILL.md` anti-pattern #2 (script-per-transactional-op is fine,
  script-per-loop is not) is the standing rule the whole audit is checked against for the
  **Excluded** bucket — cite it directly rather than restating its content in the audit doc.

## Testing

Not applicable in the code-test sense — this task produces one markdown document, no code changes.
The completeness check that stands in for a test suite, to be applied by the plan reviewer during
Plan Review and by any implementer/reviewer during Code Review:

- Every `###`/numbered step or phase heading in each of the three walked SKILL.md files is assigned
  to exactly one of the three buckets in `doc/turn-reduction-audit.md` — no step silently dropped,
  none double-counted.
- Every Mechanical/collapsible entry records: step range, current per-step behavior, already-
  scripted vs. un-scripted, and a rough turn-count saving (the four fields the task body requires).
- Every Borderline entry records both alternatives (full exclusion vs. scoped partial collapse)
  with an explicit recommendation, per the Decisions section above.
- The document contains no implementation of any candidate (no new helper code, no SKILL.md edits
  outside the audit doc itself) — a scope violation the reviewer should flag as a BLOCKING finding
  if found.
- `mill-merge`/`mill-finalize`/other skills are not silently pulled into scope.

Batch-level `verify:` for the implementing batch should be `null` — there is no executable test for
a prose audit document; this is a deliberate exception to CLAUDE.md's Python-verify-shape rule,
which only governs `verify:` commands that exist, not whether one is required. Record this
justification in the plan's `00-overview.md` Shared Decisions per the "Done-gate reminder"
precedent (leave the field unset with a recorded reason, rather than silently omitting the
reasoning).

## Q&A log

- **Q:** Where should the permanent audit document live, given `_mill/` is wiped at merge?
  **A:** [auto-pick] `doc/turn-reduction-audit.md`, following the existing `doc/backlog.md` /
  `doc/v3-architecture.md` precedent. **Why:** it's the repo's only existing home for permanent,
  git-tracked design docs outside the wiki (which CLAUDE.md restricts to `Home.md` only).
- **Q:** Should the proposed `append_phase_and_commit` helper live in `_status.py` or a new module?
  **A:** [auto-pick] A new module (e.g. `_status_commit.py`) built on the existing
  `_subprocess_util.git_commit`. **Why:** `_status.py` has zero git/subprocess dependencies today,
  which is what lets its unit tests stay in-memory/tempfile with no real git; adding git calls to
  it would break that test story for every future `_status.py` change, not just this one.
- **Q:** Should Borderline candidates get one global all-or-nothing verdict, or case-by-case
  partial-collapse treatment? **A:** [auto-pick] Case-by-case: the audit doc records both a
  full-exclusion and a scoped-partial-collapse alternative per Borderline candidate, with a
  recommendation, never a forced single verdict. **Why:** the one concrete example examined
  (`mill-plan/SKILL.md` Entry step 4) has grown well past its original "~60 lines" description and
  now brackets several distinct operator-facing halts — a blanket verdict either buries those halts
  behind a script's exit code or leaves genuinely mechanical parsing fully manual.
- **Q:** Is `mill-merge` (cited in the task's background as a motivating example) in scope for this
  audit? **A:** [auto-pick] No — the task's own "What needs to happen" section names only
  `mill-start`/`mill-plan`/`mill-go-base` (+ `mill-go`/`mill-go2`). **Why:** the background section
  uses `mill-merge` only to establish that the problem is real elsewhere too; auditing it is a
  natural, separate follow-up task, not a silent scope expansion of this one.
