# Batch: commit-none-and-done-gate

```yaml
task: "mill-go-base / mill-plan documentation gaps"
batch: "commit-none-and-done-gate"
number: 2
cards: 4
verify: null
depends-on: []
```

## Batch Scope

Covers #1145 (external-side-effect idempotency for `Commit: none` cards, in both the implementer brief and the planner guidance) and #1148 (making mill-plan's done-gate reminder explicitly advisory).
The brief rule is generic and applies on every dispatch; the planner rule makes each such card spell out the concrete state check the generic rule then runs.
No batch-local decisions differ from the overview.

## Cards

### Card 3: Add the external-side-effect idempotency rule to the implementer brief

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edits inside `## Implementation discipline`.
  1. In the "**Resume-after-incomplete:**" paragraph, replace its last two lines, which begin "Treat a Commit: none card as complete once you have (re-)performed its Requirements: verification step" and end "it needs no log entry to be considered done.", with the text below.

     ```text
     Treat a Commit: none card as complete once its Requirements are satisfied:
     re-run pure verification steps freely, but re-perform an external action only after the state check described in "External side effects in Commit: none cards" below shows it has not yet happened;
     it needs no log entry to be considered done.
     ```

  2. Insert a new paragraph between that paragraph and the numbered list item starting "1. Work through `## Cards` in order.", separated by blank lines.
     It sits outside the `<START_SHA>`-gated Resume-after-incomplete paragraph, because a fresh re-fire has an empty `<START_SHA>`.

     ```text
     **External side effects in Commit: none cards.**
     This applies on every dispatch: fresh, re-fired, resumed, or warm-resumed, whatever `<START_SHA>` holds.
     A prior session may already have performed the action, and the git log cannot show that.
     Before performing any external or hard-to-reverse side effect, query the current external state first.
     Such effects include network/API calls (`gh issue comment`, `gh issue close`, `gh pr ...`), pushes to other remotes, messages, and wiki or tracker mutations.
     Skip the action when the state already reflects the intended outcome, e.g. run `gh issue view <n> --json state,comments` before commenting on or closing an issue.
     When the card's Requirements name a state check, run exactly that check.
     ```

  Do not change the other `Commit: none` mentions in the brief (the count and `commit_sha` rules).
  The `mill-plan/SKILL.md` context is the counterpart rule (Card 4) that tells planners to write that state check into Requirements.
- **Commit:** `docs(implementer-brief): require state check before external side effects in Commit: none cards`

### Card 4: Add the Commit: none external-side-effect authoring rule to mill-plan

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Phase: Plan, insert a new bold-titled paragraph immediately after the line beginning "**Card numbering is global across batches**" and before the line "**Verify command shape.**", separated from each by a blank line.
  Do not edit the Step 1.5 fix-table row `commit-none-with-content` or add any validator check.

  ```text
  **Commit: none cards with external side effects.**
  A Commit: none card leaves no git-log trace, so a re-dispatched implementer cannot tell from history whether its action already ran.
  When such a card's Requirements perform an external, hard-to-reverse side effect (`gh issue comment`, `gh issue close`, a push to another remote, a message, a tracker mutation), spell out in those Requirements the concrete state check that detects "already done".
  Name the command to run and the state it must show, e.g. `gh issue view <n> --json state,comments`: skip the comment when the expected text already appears, skip the close when `state` is `CLOSED`.
  This gives the implementer brief's generic external-side-effect rule an exact check to run.
  This is authoring guidance only; no validator check enforces it, since external side effects are not detectable from card fields.
  ```

  The `implementer-brief.md` context is the generic rule this paragraph feeds (Card 3).
- **Commit:** `docs(mill-plan): require an already-done state check on external Commit: none cards`

### Card 5: Reword the Done-gate reminder as advisory

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Phase: Plan, replace the whole "**Done-gate reminder.**" block — from that heading line through the line beginning "Leave `done_gate: null` only when" — with the block below.
  The block ends immediately before the "**Interpreter-naming note.**" paragraph; keep the blank line separating them.
  Every imperative that implied mill-plan applies a config value ("default", "author", "leave `done_gate: null`") becomes a recommendation the plan records.

  ```text
  **Done-gate reminder (advisory).**
  mill-plan never writes `mill-config.yaml` (hub, committed, shared by every future task) and never writes `.millhouse/config.local.yaml` for this purpose.
  mill-go gates its pre-done step on the effective `cfg["pipeline"]["done_gate"]` only, and nothing in the plan changes that value.
  Everything below is a recommendation the plan records, not a value the plan applies.
  If the plan's batch-verify scopes do not cover the entire module tree (the common case for scoped plans), recommend a cheap repo-wide test command as `pipeline.done_gate` (e.g. `go test ./...` for Go repos, `dotnet test` for .NET solutions).
  mill-go runs the effective value from `git_root` before marking the task `done`, catching regressions in packages outside the batch-verify scope.
  Before recommending the target language's lint command (Go: `golangci-lint run`; Python: `ruff check .`), first run that candidate command against the current worktree tip (not the plan's own scoped changes) from `git_root` and confirm it exits 0.
  If it does, recommend including it, e.g. `go test ./... && golangci-lint run`.
  That includes a lint-only recommendation (`golangci-lint run`) when a repo-wide *test* command is skipped as too slow, since linters are fast, unlike full regression suites.
  If the candidate command does NOT exit 0 (pre-existing repo-wide lint debt unrelated to this task), recommend no lint command and record the finding in the plan overview's Shared Decisions, so the recommendation does not steer every future task in the hub toward fixing unrelated debt first.
  `csharp-build` defines no lint command today, so C# projects are unaffected by this recommendation.
  Recommend no `done_gate` only when the project has neither a meaningful repo-wide test nor a defined lint command.
  When the recommended value differs from the currently effective `cfg["pipeline"]["done_gate"]`, record a `### Decision:` under the overview's `## Shared Decisions` labelled as a recommendation for the operator.
  It names the recommended command and the currently effective value, and includes the sentence "Not applied: mill-go gates on the effective config value, not this Decision."
  When the task itself needs a repo-wide suite as its acceptance bar, express that as a batch `verify:` command instead, with the justification the `verify-full-suite` skip-check escape hatch requires.
  Never express it as a done_gate Decision, because only `verify:` is executed from the plan.
  ```

  Do not edit the `done_gate=cfg.get("pipeline", {}).get("done_gate")` validator-call keyword argument or any other `done_gate` mention elsewhere in the file.
  The `mill-config.yaml` template context is read-only; its `done_gate` comment is the operator-facing counterpart and stays unchanged.
- **Commit:** `docs(mill-plan): reword Done-gate reminder as an advisory recommendation`

### Card 6: Mirror the external-side-effect rule in the plan-batch template

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the HTML comment's field-conventions area, the paragraph beginning "Commit: also participates in the "none" convention" ends with the sentence "(enforced by the commit-none-with-content validator check)."
  Add a new line directly after that paragraph, before the blank line preceding "Note for reviewers:", containing the sentence below.
  Do not modify the `- **Commit:**` field bullet or the card skeleton below the comment.

  ```text
  A Commit: none card whose Requirements perform an external, hard-to-reverse side effect (e.g. `gh issue comment`, `gh issue close`) must include, in those Requirements, the concrete state check that detects "already done" (the command and the expected state) — see the mill-plan skill's "Commit: none cards with external side effects" paragraph.
  ```

  The `mill-plan/SKILL.md` context holds the paragraph this line points to (Card 4).
- **Commit:** `docs(plan-batch): mirror external-side-effect state-check rule for Commit: none cards`

## Batch Tests

`verify: null`: all four cards edit markdown guidance (one skill file, two templates) with no runnable surface, and the discussion records that no unit test pins the text of these passages.
Reviewer acceptance checks instead: the brief's rule sits outside the `<START_SHA>`-gated paragraph; the Done-gate reminder contains no imperative implying mill-plan applies a config value; the new paragraph in `mill-plan/SKILL.md` sits between the Card-numbering line and "**Verify command shape.**".
