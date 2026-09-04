# Plan: _plan_validate.py verify: command validation: false positives, missing escape hatches, and a doc/enforcement mismatch

```yaml
task: "_plan_validate.py verify: command validation: false positives, missing escape hatches, and a doc/enforcement mismatch"
slug: plan-validate-verify-command-validation-bugs
approved: false
started: "20260904-081228"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: verify-full-suite-check-fixes
    file: 01-verify-full-suite-check-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 2
    name: verify-full-suite-unit-tests
    file: 02-verify-full-suite-unit-tests.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 3
    name: docs-and-reviewer-guardrail
    file: 03-docs-and-reviewer-guardrail.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

### Decision: go-test-segment-scoping

- **Decision:** `_check_verify_full_suite`'s Go-test detection splits the `verify:` command on shell operators (`&&`, `;`, `||`) via `re.split(r"&&|\|\||;", command)`, then matches each segment independently against `re.compile(r"\bgo\s+(?:-C\s+\S+\s+)?test\b")`. The `./...` substring check and the `-run ` filter check are both scoped to the matching segment, not the whole command string.
- **Rationale:** Fixes issue #961 (false positive: a `./...` token belonging to a later `go vet`/other segment was wrongly attributed to an earlier `go test` segment) and issue #933 (false negative: `go -C <dir> test ./...`, the standard Go 1.20+ way to target a nested module, was never matched by the old literal `\bgo test\b` pattern) with one coherent change. The narrow `-C` allowance (rather than a generic "any flags between go and test" pattern) avoids a new false-positive class like `go get test/pkg` matching a looser regex.
- **Applies to:** batch `verify-full-suite-check-fixes`.

### Decision: done-gate-exemption

- **Decision:** `_check_verify_full_suite` and `run()` gain a new keyword-only parameter `done_gate: str | None = None`. Inside `_check_frontmatter`, immediately after extracting the command via `parse_verify_field` and before any of the four runner-specific sub-checks, return `None` (no finding) when `done_gate is not None and command == done_gate` — exact string equality against the command as authored. `done_gate` is threaded from `cfg.get("pipeline", {}).get("done_gate")` at all three `_plan_validate.run(...)` call sites (`millpy-validate-plan.py`; `millpy-review-plan.py`'s two call sites).
- **Rationale:** Issue #950's repro is a batch `verify:` byte-identical to the hub's own configured `pipeline.done_gate` — the check was flagging the hub's own prescribed repo-wide gate command, not a planner mistake. Exact-match keeps the exemption conservative: a scoped subset or a superset of `done_gate` is still flagged normally.
- **Applies to:** batch `verify-full-suite-check-fixes`.

### Decision: overview-level-escape-hatch

- **Decision:** The `verify-full-suite` skip-check escape hatch in `mill-plan/SKILL.md` Phase: Plan is extended so an overview-level (`batch: null`) finding's justification lives in a `### Decision:` subsection under `00-overview.md`'s `## Shared Decisions` section, mirroring the batch-level `## Batch Tests` justification path. The Step 1.5 fix-table row is updated to route `batch: None` findings there instead of a nonexistent `## Batch Tests` section.
- **Rationale:** Issue #937 — both prior documented escape hatches keyed the justification on a **batch's** `## Batch Tests` section, leaving no home for an overview-level finding. `## Shared Decisions` already exists in the `00-overview.md` template specifically for cross-cutting decisions every batch inherits, so no new section is introduced.
- **Applies to:** batch `docs-and-reviewer-guardrail`.

### Decision: reviewer-prompt-guardrail

- **Decision:** `review-plan-holistic.md` gains a short reminder, placed before `## Criteria`, that the overview's module-wide `verify:` must stay a cheap compile/vet/smoke command per `plan-overview.md`'s own documented intent, and that a reviewer must not suggest converting it into an unscoped full-test run.
- **Rationale:** Issue #983's root cause is that the plan-review reviewer prompt has no awareness of the overview `verify:` field's documented scope contract, so it filed a NIT whose own suggested fix (`go build ./... && go test ./...`) directly triggers `verify-full-suite`. The overview-level escape hatch (above) only resolves the after-the-fact conflict; this stops the wasted review round from being generated at all.
- **Applies to:** batch `docs-and-reviewer-guardrail`.

### Decision: fix-table-runner-agnostic-remedy

- **Decision:** The Step 1.5 `verify-full-suite` fix-table row in `mill-plan/SKILL.md` is rewritten to point at the finding's own `message` field for the runner-correct scoping flag (`-run <pattern>` for Go, `--filter` for dotnet, `-k <pattern>`/`--only <files>` for run-all.py, `-k <pattern>` for bare pytest — the pytest message names only `-k`, not `--only`) instead of hardcoding a single Python-flavored instruction for every runner.
- **Rationale:** Issue #935 — `_check_verify_full_suite`'s own `message` strings are already correctly runner-specific; the fix-table row was the only place still hardcoding a single Python-only remedy (`-k <pattern>`/`--only <files>` for every runner). Pointing at the check's own message avoids a second copy of per-runner logic that can drift out of sync.
- **Applies to:** batch `docs-and-reviewer-guardrail`.

### Decision: config-doc-fix

- **Decision:** `plugins/mill/templates/mill-config.yaml`'s "verify command shape" comment block is rewritten to state the Python-project gate condition `_is_python_project` actually implements, mirroring this repo's own `CLAUDE.md` "Verify command shape" section (already correctly conditional). `CLAUDE.md` itself is not edited.
- **Rationale:** Issue #964 — the template comment states the `PYTHONPATH=` rule as an unconditional MUST with no language carve-out, when the enforcer it names (`_plan_validate.verify-not-isolated`) only requires it for Python projects. The template comment is the only stale copy — it seeds every new hub's `mill-config.yaml`, so the mismatch propagates to every future hub.
- **Applies to:** batch `docs-and-reviewer-guardrail`.

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-validate-plan.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
