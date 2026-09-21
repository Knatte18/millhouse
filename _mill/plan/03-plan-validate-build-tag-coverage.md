# Batch: plan-validate-build-tag-coverage

```yaml
task: mill-go/mill-merge-in orchestration robustness gaps, round 2
batch: plan-validate-build-tag-coverage
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

Adds one new `_plan_validate.py` check (`_mill/discussion.md` Decision
`build-tag-tier-coverage-check`, #1069): flag an untouched, differently-build-tagged Go test file
co-located in a package some batch's non-test `Edits:`/`Creates:` DID touch, when no batch's
`verify:` command ever exercises that tag against that package. Distinct from the existing
`_check_verify_excludes_edited_tagged_test`, which only fires when a batch itself edits the tagged
test file — this new check covers the untouched-sibling-file gap that check was never meant to
cover. Single card, single new function, one batch.

## Cards

### Card 7: flag an untested build tag in a touched package

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new function `_check_verify_untested_tag_in_touched_package(batch_files: list[Path],
  project_root: Path, root: str | None, *, wiki_root: Path | None = None, git_root: Path | None =
  None) -> list[dict]` to `_plan_validate.py`, placed immediately after
  `_check_verify_excludes_edited_tagged_test`. Gate identically:
  `if not (project_root / "go.mod").exists(): return []`.
  Algorithm:
  1. Collect every package directory touched by ANY batch's non-test `Edits:`/`Creates:` tokens
     (a "touched" token is one that does NOT end in `_test.go`; reuse the existing `Edits:`/`Creates:`
     token-collection helpers this file already has for other checks, e.g. the pattern
     `_parse_edits_only` uses, extended to also read `Creates:` — or call both and union their
     results). For each such token, resolve it via `resolve_existing_paths` (only for `Edits:` —
     `Creates:` targets do not exist on disk yet, mirroring `_check_verify_excludes_edited_tagged_test`'s
     own documented exclusion of `Creates:` tokens for this exact reason) and take its parent
     directory as the touched package's relative path (relative to `project_root`, POSIX-separated).
  2. For each distinct touched package directory, list every `_test.go` file that exists in that
     directory on disk (`Path(project_root, pkg_rel).glob("*_test.go")` — every test file in the
     package, not just batch-`Edits:`-named ones; this is the deliberate difference from the sibling
     check). For each, call `_go_file_custom_tags(path)`; skip files with no custom tags.
  3. Build, once per plan (not per package), the list of every batch's normalized `verify:` command
     via `_plan_dag.parse_verify_field` on each batch's own frontmatter (skip a batch on `ValueError`
     — `_check_verify_malformed_cwd` is the sole reporter for that). For each command, split into
     shell segments via the existing `_RE_SHELL_OPERATOR.split(command)`. For each segment matching
     `_RE_GO_TEST_INVOCATION`, record the segment's raw text.
  4. For each (package, tag) pair discovered in step 2, the tag is "covered" when at least one
     recorded segment from step 3 both (a) has a `-tags` flag whose value includes the tag (via the
     existing `_verify_command_has_any_tag(segment, {tag})`) AND (b) targets the package: the segment
     contains the literal substring `"./..."`, OR contains `f"./{pkg_rel}"`, OR contains
     `f"./{parent}/..."` for any ancestor directory `parent` of `pkg_rel` (walk `pkg_rel`'s POSIX path
     upward one directory at a time, e.g. `internal/reedcli` also checks `internal`). When no segment
     satisfies both (a) and (b), report one finding: `{"check":
     "verify-untested-tag-in-touched-package", "batch": None, "card": None, "path": "<pkg_rel>/<test
     file name>", "message": f"package '{pkg_rel}' is touched by a batch's Edits:/Creates: but its
     custom-tagged test file '<test file name>' (tag '{tag}') is never exercised by any batch's
     verify: command"}`. Use `batch: None` (an overview-level, whole-plan finding) since the flagged
     tag's absence is a property of the plan's verify commands as a set, not any single batch's own
     command — mirrors `_check_verify_full_suite`'s own `batch=None` convention for its overview-level
     findings.
  Register the new check in the `validate()` aggregator's Go-specific check block, alongside the
  existing `errors.extend(_check_verify_excludes_edited_tagged_test(...))` call, passed the same
  `batch_files, project_root, root` positional args plus `wiki_root=wiki_root, git_root=git_root`.
  Add a `"verify-untested-tag-in-touched-package"` row to `mill-plan/SKILL.md`'s Step 1.5 fix table:
  the mechanical fix is "the batch touching the named package's `verify:` command must add a
  `-tags <tag>` invocation targeting that package (append a new `&&`-chained invocation mirroring
  `verify-excludes-edited-tagged-test`'s own remedy), or the plan reviewer must judge the untouched
  tagged test genuinely unaffected by this task's change and document that in `## Batch Tests` —
  not mechanically auto-fixable either way, since both require reading the untested file's actual
  assertions."
- **Commit:** `feat(plan-validate): flag an untested build tag in a touched package (#1069)`

## Batch Tests

Extends `test-plan-validate.py` with: a fixture package containing an edited non-test file and an
untouched `//go:build integration` test file, plus a plan whose only `verify:` command passes
`-tags integration` for a DIFFERENT package — asserts one finding naming the untested package/tag. A
second fixture where some batch's verify command does cover `-tags integration` against the correct
package (via `./...`, an exact package path, or a covering ancestor `.../...`) asserts zero findings.
A third fixture confirms the `go.mod`-absent fail-open gate (non-Go project) returns `[]`
unconditionally. Runs via `test-plan-validate.py` directly — this batch touches only that one test
file.
