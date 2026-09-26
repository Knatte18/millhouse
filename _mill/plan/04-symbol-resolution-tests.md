# Batch: symbol-resolution-tests

```yaml
task: "plan validator and wiki-guard hook false positives"
batch: "symbol-resolution-tests"
number: 4
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate-symbol-resolution.py
depends-on: [3]
```

## Batch Scope

Tests for the batch 3 validator change, split into its own batch because citing the very large validator module as Context in the same batch as its Edits entry would exceed the batch context cap.
The new file is standalone; the existing very large validator test file is not edited.

## Cards

### Card 8: symbol-resolution tests

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate-indent-drift-line.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-plan-validate-symbol-resolution.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create a standalone test file modelled on the sibling style-model file listed in Context (sys.path insert of the scripts directory relative to `HUB`, import the `_plan_validate` module, plain `def test_*` functions with assertions, `main() -> int` runner printing failures to stderr, `sys.exit(main())`). Build each fixture in a `tempfile.TemporaryDirectory`: a project root with real `.cs` files, hand-written overview and batch text, and a call to the module-level function named run in the validator module with the plan directory and project root as its two positional arguments, filtering results to `check == "context-completeness"`. Write the overview and batch text helpers locally (a small overview builder and a batch builder taking context, edits, and requirements); the overview needs a fenced yaml Batch Index whose entries match the batch files, and each batch file needs the fenced yaml frontmatter plus cards with all six fields and a Commit field. Every cited file must be cited in some card's `Context:` or `Edits:` so it enters the plan-wide cited-file search space. Scenarios:
  - A bare framework exception name in Requirements with a cited `.cs` file that mentions it only in a member-shaped line (for example a `public` method line that names it before an opening parenthesis): no error.
  - The same with a cited `.cs` file that declares `class` of that exact name: still flagged, naming that file (repo-type override).
  - Framework-qualified tokens for `Path.Combine` and `Math.Max`: no error even when cited files declare methods named `Combine` and `Max`.
  - A dotted `HydraulicsParticipant.Replace` where the card's `Edits:` is the file declaring the class (member not yet declared there) and another cited file declares a `Replace` method: no error.
  - Same with the member already declared in the Edits file: no error.
  - The class file is cited elsewhere in the plan (different card) and declares `Replace`, but is not in the token card's own refs: exactly one error whose message contains the resolved class file path, with the unchanged wording `which resolves to '`.
  - The class file does not declare the member (another cited file does): no error.
  - Two cited `.cs` files in directories named `a` and `b`, in namespaces `Alpha` and `Beta`, both declare `public class Widget` with a `Run` method, neither in the token card's own refs; the token `Widget.Run` falls through to the existing qualifier filtering, which matches neither namespace nor directory name: assert no error.
  - Regression guard: a lowercase Go package qualifier token such as `reedengine.New` with two cited `.go` files still narrows by package and flags the right file.
- **Commit:** `test(plan-validate): cover framework-type and Type.Member resolution`

## Batch Tests

`verify:` runs only the new `test-plan-validate-symbol-resolution.py`.
