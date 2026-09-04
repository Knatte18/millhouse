# Discussion: _plan_validate.py verify: command validation: false positives, missing escape hatches, and a doc/enforcement mismatch

```yaml
task: _plan_validate.py verify: command validation: false positives, missing escape hatches, and a doc/enforcement mismatch
slug: plan-validate-verify-command-validation-bugs
status: discussing
parent: main
```

## Problem

`_plan_validate.py`'s `verify-full-suite` check (which flags plan `verify:` commands that run an unscoped full test suite) has three classes of bugs, discovered across seven GitHub issues filed during real `mill-plan`/`review-plan` sessions on other repos (quarry, loomyard, NORCE Models):

1. **False positives / false negatives in Go detection.** The check's Go-test regex scans the raw command string, not the individual shell-operator-separated invocation it's supposed to be scoped to. A compound command like `go test ./internal/x/ && go vet ./...` is wrongly flagged (the `./...` belongs to `go vet`, not `go test`) — issue #961. Conversely, `go -C <dir> test ./...` (the standard Go 1.20+ way to target a nested module) is never matched at all, silently letting an unscoped run through — issue #933.
2. **No escape hatch for two legitimate cases**: an overview-level (`batch: null`) finding has no section to hold its justification, since both documented escape hatches key off a **batch's** `## Batch Tests` section (issue #937); and a batch `verify:` that is byte-identical to the hub's own configured `pipeline.done_gate` still gets flagged and pointed at Python-only remedies even in a Go/`.NET` project (issue #950, issue #935's fix-table wording bug). This has a second-order effect: the plan-review LLM reviewer can request a fix (e.g. adding the overview's "test half") that `verify-full-suite` then itself rejects, burning a review round with no way to resolve it that the docs describe (issue #983).
3. **Doc/enforcement mismatch.** `plugins/mill/templates/mill-config.yaml`'s "verify command shape" comment states the `PYTHONPATH=` prefix rule as an unconditional MUST, when `_plan_validate.verify-not-isolated` (the enforcer it names) only requires it for Python projects (gated on `_is_python_project`). A reviewer reading only the config comment files a false BLOCKING/NIT against every Go/Rust/etc. plan (issue #964). Note: `CLAUDE.md`'s own copy of this rule (this repo, "Verify command shape") is already correctly conditional — only the template comment is stale.

This task fixes all of it in one pass since the bugs share one check and its two consumer docs (`mill-plan/SKILL.md`'s Step 1.5 fix table and Phase: Plan escape-hatch text), and leaving any subset unfixed keeps #983's review-round-wasting conflict alive.

## Scope

**In:**
- `_plan_validate.py`: `_check_verify_full_suite`'s Go-test detection — split the command on shell operators (`&&`, `;`, `||`) and match each segment independently against a narrow `go (-C <dir> )?test` pattern; scope the `-run ` filter check and the `./...` substring check to the same matched segment.
- `_plan_validate.py`: add a `done_gate: str | None = None` parameter to `_check_verify_full_suite` and `run()`; when a frontmatter's fully-resolved verify command string exactly equals `done_gate`, skip the finding for that frontmatter (all four sub-checks, not just Go).
- Thread `done_gate=cfg.get("pipeline", {}).get("done_gate")` from `pipeline.done_gate` config through the three existing `_plan_validate.run(...)` call sites: `millpy-validate-plan.py`, and both call sites in `millpy-review-plan.py`.
- `mill-plan/SKILL.md`, Phase: Plan: extend the self-run `_plan_validate.run(...)` call with the new `done_gate` kwarg (update the "seven keyword arguments" cross-reference at line ~239 to "eight"); extend the `verify-full-suite` skip-check escape-hatch paragraph to cover the overview-level case via `00-overview.md`'s `## Shared Decisions` section (parallel to the existing batch `## Batch Tests` path).
- `mill-plan/SKILL.md`, Step 1.5 fix table: rewrite the `verify-full-suite` row so its remedy directs to the check's own per-runner `message` field (already runner-correct — `-run` for Go, `--filter` for dotnet, `-k`/`--only` for run-all.py, `-k` for bare pytest, which names only `-k` and not `--only`) instead of hardcoding the Python-only `-k`/`--only` phrasing for every runner; add routing for `batch: None` findings to the `## Shared Decisions` escape hatch.
- `plugins/mill/templates/review-plan-holistic.md`: add one criterion/reminder that a plan's overview-level module-wide `verify:` must stay a cheap compile/vet/smoke command (per `plan-overview.md`'s own documented intent) and a reviewer must not suggest converting it into an unscoped full-test command.
- `plugins/mill/templates/mill-config.yaml`: fix the "verify command shape" comment block (~lines 224-236) to state the Python-project gate condition, mirroring `CLAUDE.md`'s already-correct wording.
- Unit tests in `plugins/mill/unit_tests/test-plan-validate.py` covering: compound-command false positive (#961), `go -C <dir> test` detection (#933), `done_gate`-equality exemption (#950), and the existing Go/dotnet/pytest cases continuing to pass unchanged.

**Out:**
- No change to `_check_verify_not_isolated` (`verify-not-isolated`) — its Python-project gate is already correct in code; only the *template comment* documenting it is stale (issue #964's actual bug).
- No change to `run-all.py`/`dotnet test`/bare-pytest detection logic — issues #961/#933 are Go-specific (compound-command scoping and the `-C` flag); no compound-command bug was reported for the other three runners, so they keep their existing whole-string substring checks.
- No general shell-command parser (`shlex`/AST) — the segment-split + narrow regex approach is sufficient for the reported cases and matches this file's existing regex-based style.
- No change to `pipeline.done_gate`'s own semantics or default-selection logic in `mill-plan/SKILL.md`'s "Done-gate reminder" section — only its use as a `verify-full-suite` exemption input is new.
- No change to `verify-not-isolated`'s fix-table row (row is already correct and language-conditional).

## Decisions

### go-test-segment-scoping

- Decision: Split the verify command string on `&&` / `;` / `||` into segments (`re.split(r"&&|\|\||;", command)`). Match each segment against `re.compile(r"\bgo\s+(?:-C\s+\S+\s+)?test\b")`. For the first matching segment, check `"./..." in segment` and `"-run " not in segment` (both scoped to that segment, not the whole command) before reporting.
- Rationale: Fixes both #961 (false positive: a later segment's `./...` wrongly attributed to an earlier `go test`) and #933 (false negative: `go -C <dir> test` never matched the old literal `\bgo test\b`) with one coherent change. The narrow `-C` allowance (rather than a generic "any flags between go and test" pattern) avoids a new false-positive class like `go get test/pkg` matching a looser "any tokens between go and test" regex.
- Rejected: A generic `shlex`/AST-based command parser — overkill for shell-operator splitting (shlex doesn't split on `&&`/`;`/`||`, it would need custom tokenizing anyway) and inconsistent with the file's existing regex-based checks (e.g. `_RE_GO_BUILD_CONSTRAINT`, `_RE_VERIFY_TAGS_FLAG`). A broad "any flag sequence between go and test" pattern — rejected because it can misfire on non-flag tokens (`go get test/pkg`) that happen to contain a `test` word-boundary match; `-C` is the only flag Go's own tooling requires to precede the subcommand (Go 1.20+, must be first argument), so it's the only one worth special-casing.

### done-gate-exemption

- Decision: Add `done_gate: str | None = None` to `_check_verify_full_suite(...)` and `run(...)`. Inside `_check_frontmatter`, after extracting the command via `parse_verify_field`, return `None` immediately (no finding, any sub-check) when `done_gate is not None and command == done_gate` — exact string equality against the raw command as authored, before any of the four runner-specific checks run. Thread `done_gate=cfg.get("pipeline", {}).get("done_gate")` into all three `run()` call sites (`millpy-validate-plan.py`; `millpy-review-plan.py`'s two call sites, which already have `cfg` in scope from the neighboring `max_cards_per_batch`/`max_batch_context_tokens` kwargs).
- Rationale: #950's repro is a batch `verify:` byte-identical to the hub's own `pipeline.done_gate` — the check is flagging the hub's own prescribed repo-wide gate command, which is not a planner mistake. Exact-match keeps the exemption conservative: a scoped subset or superset of `done_gate` still gets flagged normally.
- Rejected: Fuzzy/prefix matching — ambiguous and could silently exempt a genuinely-unscoped command that merely resembles `done_gate`. Exempting all Go/`.NET` full-suite commands unconditionally — too broad, defeats the check's purpose for projects that don't set `done_gate`.

### overview-level-escape-hatch

- Decision: Extend the `verify-full-suite` skip-check escape hatch (`mill-plan/SKILL.md`, Phase: Plan) so an overview-level (`batch: null`) finding's justification lives in a new subsection under `00-overview.md`'s existing `## Shared Decisions` section (e.g. `### Decision: module-wide verify scope`), mirroring the batch-level `## Batch Tests` justification path. If present, apply the same `skip_checks | frozenset({"verify-full-suite"})` treatment as the batch case. Update the Step 1.5 fix-table row to route `batch: None` findings there instead of pointing at a nonexistent `## Batch Tests` section.
- Rationale: `## Shared Decisions` already exists in the `00-overview.md` template specifically for cross-cutting decisions every batch inherits — a module-wide `verify:` justification is exactly that kind of decision. No new section needed.
- Rejected: A new dedicated section next to the `verify:` field itself — adds a new template section for something `## Shared Decisions` already covers structurally.

### reviewer-prompt-guardrail

- Decision: Add a short reminder to `review-plan-holistic.md`'s `## Criteria` list: the overview's module-wide `verify:` should stay a cheap compile/vet/smoke command per `plan-overview.md`'s own documented intent, and a reviewer must not suggest converting it into an unscoped full-test run.
- Rationale: #983's root cause is that the plan-review reviewer prompt has no awareness of the overview `verify:` field's documented scope contract, so it filed a NIT whose own suggested fix directly triggers `verify-full-suite`. Fixing the escape hatch (above) only patches the after-the-fact conflict; this stops the wasted round from being generated at all.
- Rejected: Rely solely on the escape hatch + `done_gate` exemption — leaves the reviewer free to keep suggesting a fix that costs a round before the planner reaches for the escape hatch.

### fix-table-runner-agnostic-remedy

- Decision: Rewrite the Step 1.5 `verify-full-suite` fix-table row to say: apply the scoping flag already named in the finding's own `message` field (runner-correct: `-run <pattern>` for Go, `--filter` for dotnet, `-k <pattern>`/`--only <files>` for run-all.py, `-k <pattern>` for bare pytest — the pytest message names only `-k`, not `--only`, so the row must not claim `--only` applies there) rather than hardcoding a single Python-flavored instruction for every runner; if `batch:` is `None`, point to the `## Shared Decisions` overview-level escape hatch instead of `## Batch Tests`.
- Rationale: `_check_verify_full_suite`'s own `message` strings are already correctly runner-specific (verified by reading the check's source — the go-test message says "-run <pattern> filter", the dotnet message says "--filter", the run-all.py message says "-k <pattern>' or '--only <files>"). The fix-table row was the only place still hardcoding a single Python-only remedy; pointing at the check's own message avoids a second copy of per-runner logic to keep in sync.
- Rejected: Enumerating all four runner remedies explicitly in the table row — duplicates logic already correct in the check's message strings.

### config-doc-fix

- Decision: Edit only `plugins/mill/templates/mill-config.yaml`'s "verify command shape" comment block (~lines 224-236) to state the condition `_is_python_project` actually implements (root-level `pyproject.toml`/`setup.py`/`setup.cfg`, or the `plugins/mill/pyproject.toml` dogfood marker), mirroring this repo's own `CLAUDE.md` "Verify command shape" section, which is already correctly conditional. Do not touch `CLAUDE.md`.
- Rationale: The template comment is the only stale copy of this rule — it's what seeds every new hub's `mill-config.yaml`, so the mismatch propagates to every future hub. `CLAUDE.md` here already matches the code; editing it would be a no-op diff.
- Rejected: Editing both files for "redundancy" — unnecessary diff against text that's already correct.

## Technical context

- `plugins/mill/scripts/_plan_validate.py`:
  - `_is_python_project(project_root)` (~line 2073) — the shared Python-project gate, reused unchanged.
  - `_check_verify_not_isolated` (~line 2083) — sibling check, already conditionally gated on `is_python_project`; used as the pattern to mirror, not modified.
  - `_check_verify_full_suite` (~line 2363) — the check being fixed. Its `_check_frontmatter` inner closure (~line 2394) currently runs four sequential `if` blocks (run-all.py, go test, dotnet test, pytest) each returning on first match. The `done_gate` exemption must short-circuit before all four; the Go-segment-scoping change only touches the second `if` block.
  - `run()` (~line 2872) — the top-level validator entry point; add `done_gate` as a new keyword-only parameter (default `None`, consistent with existing optional kwargs like `parent_branch`), thread to `_check_verify_full_suite`'s call at line ~2957.
- `plugins/mill/scripts/millpy-validate-plan.py` (~line 51) — standalone CLI; already loads `cfg` before calling `_plan_validate.run`.
- `plugins/mill/scripts/millpy-review-plan.py` (~lines 214-224 and ~321-330, two call sites) — both already read `cfg.get("pipeline", {})` for `max_cards_per_batch`/`max_batch_context_tokens`; add `done_gate` alongside.
- `plugins/mill/skills/mill-plan/SKILL.md`:
  - Line ~238-240: "Self-run the validator gate" — the "same seven keyword arguments" cross-reference to `millpy-review-plan.py`'s gate; becomes eight.
  - Lines ~259-270: the self-run `_plan_validate.run(...)` call block — add `done_gate=cfg.get("pipeline", {}).get("done_gate")`.
  - Line ~255: `verify-full-suite` skip-check escape hatch paragraph — extend for the overview-level case.
  - Line ~369: Step 1.5 fix-table row for `verify-full-suite` — rewrite per the `fix-table-runner-agnostic-remedy` decision.
- `plugins/mill/templates/plan-overview.md` (lines 14-23) — already documents the module-wide `verify:` as "a cheap whole-module compile/vet/smoke command", and the `## Shared Decisions` section (lines 55-58) as the home for cross-cutting justifications — both are the existing contract the fixes above lean on, not new additions.
- `plugins/mill/templates/review-plan-holistic.md` — `## Criteria` list (lines 27-65) is where the new reviewer-guardrail line belongs; keep it to one line, matching the existing terse bullet style.
- `plugins/mill/templates/mill-config.yaml` (~lines 224-236) — "verify command shape" comment block to fix.
- `CLAUDE.md` (this repo, lines 74-78) — reference wording for the correct conditional phrasing; read-only reference, not edited.
- `plugins/mill/unit_tests/test-plan-validate.py` (~lines 4424-5079) — existing `verify-full-suite` test block; new tests should follow the established pattern (`tempfile` fixtures, `PASS`/`FAIL` print + return-code convention, registered in the `tests` list around line 7112-7131).

## Constraints

No `CONSTRAINTS.md` present at hub root — none beyond this repo's own `CLAUDE.md` conventions (regex-based checks stay in `_plan_validate.py`'s existing style; ASCII-only `print()`/`_log()` output; ` -> ` not `->` in generated docs where applicable).

## Testing

- `_check_verify_full_suite` (TDD candidate — write these first, they'll fail against current code):
  - Compound command `go test ./internal/x/ && go vet -tags lsp ./...` → no `verify-full-suite` finding (was a false positive; issue #961).
  - `go -C plugins/prowler test ./...` → one `verify-full-suite` finding (was a false negative; issue #933).
  - `go -C plugins/prowler test ./... -run TestFoo` → no finding (scoped, `-C` form still respects `-run`).
  - A command exactly equal to a passed `done_gate="go test ./... && go test -tags integration ./..."` → no finding, even though it would otherwise match the go-test branch (issue #950).
  - A command that is a *subset* of `done_gate` (e.g. `done_gate` is `go test ./... && golangci-lint run`, command is just `go test ./...`) → still flagged (exact-match only, not the exemption).
  - Existing tests (run-all.py, dotnet test, bare pytest, mapping form, overview-level) continue to pass unchanged — regression coverage for the sequential-`if` restructuring.
- `run()` — a test confirming `done_gate=None` (the default) preserves existing behavior with zero exemptions (covers every current call site that doesn't yet pass `done_gate`).
- No new tests needed for the `mill-plan/SKILL.md` / template doc changes — these are prose/prompt edits with no executable surface; validate by re-reading the rendered fix-table row and escape-hatch paragraph for internal consistency (batch case vs. overview case both point somewhere real) as part of plan self-review.

## Q&A log

- **Q:** Fix all 7 issues in one plan, or split? **A:** [auto-pick] All 7 in one plan. **Why:** they cluster on one check plus its two consumer docs; a subset leaves #983's review-round waste unresolved.
- **Q:** Go-command detection approach — segment-split regex vs. full shell parser? **A:** [auto-pick] Segment-split + narrow `go (-C <dir> )?test` regex. **Why:** matches the file's existing regex style; avoids new dependency; a generic "any flags between go and test" pattern would misfire on `go get test/pkg`-shaped commands.
- **Q:** `done_gate` exemption match granularity — exact string vs. fuzzy? **A:** [auto-pick] Exact string equality. **Why:** matches #950's literal "byte-identical" repro; conservative, no partial-match ambiguity.
- **Q:** Where does an overview-level (`batch: null`) escape-hatch justification live? **A:** [auto-pick] `00-overview.md`'s existing `## Shared Decisions` section. **Why:** already templated for cross-cutting justifications; no new section needed.
- **Q:** Fix #983's root cause (reviewer suggests a command the validator rejects) at the source, or only patch after the fact? **A:** [auto-pick] Add a one-line reviewer-prompt reminder in `review-plan-holistic.md`. **Why:** prevents the wasted review round instead of only resolving the conflict after it's already spent a round.
- **Q:** Fix-table remedy wording — point to the check's own per-runner message, or duplicate the remedies inline? **A:** [auto-pick] Point to the check's own `message` field. **Why:** it's already runner-correct; duplicating it in the table risks drift.
- **Q:** Edit CLAUDE.md too, or only the template mill-config.yaml comment? **A:** [auto-pick] Template only. **Why:** CLAUDE.md already states the Python-project gate correctly; editing it would be a no-op diff.
