# Batch: mill-go2-fixer-override

```yaml
task: 'mill-go2: fork-based fixer (NIT-fix) dispatch'
batch: 'mill-go2-fixer-override'
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
depends-on: [1]
```

## Batch Scope

This batch delivers the experiment itself: the `### fixer` block under `mill-go2`'s
`## Dispatch overrides`, and the contract check that locks it in place. It is one batch because the
check and the prose it asserts on are written against each other — the extraction rule in the check
only works given the exact section shape the override adopts, and neither is meaningful alone.

It depends on batch 1 because the override text names
`_status.append_fork_fallback_log` and `_status.read_fork_fallback_log` as calls the mill-go2 Builder
makes at runtime. Writing the prose before those helpers exist would leave the shipped skill
referencing functions that are not in the module.

Batch-local decisions beyond `## Shared Decisions`: the override is prose addressed to the Builder
LLM, not executable code — nothing parses it, and its correctness is a matter of the Builder reading
it and acting correctly. The check therefore asserts structural facts (the section is non-empty, names
the role, carries the fork literal) rather than trying to validate the instruction's semantics.

## Cards

### Card 3: Add the fork-override contract check to test-mill-go-variants.py

- **Context:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-mill-go-variants.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Write this check before card 4 and confirm it fails against the current `(none)` state;
  card 4 is what turns it green.

  Add a module-level helper `_dispatch_overrides_body(text: str) -> str | None` that extracts the
  `## Dispatch overrides` section body. Return `None` when the header line is absent. Otherwise walk
  the lines after the header and stop at whichever comes first: a line beginning `"## "`, a line
  beginning ``"Load the `mill:mill-go-base` skill"``, or end of file. Join the collected lines and
  return them `.strip()`ped.

  The stop condition is not optional detail. `## Dispatch overrides` is the last `##` header in both
  variant files, and the shared closing paragraph that loads the base sits directly beneath it with no
  separating header, so a naive run-to-EOF rule swallows that boilerplate into the body and makes the
  `mill-go`-is-exactly-`(none)` assertion below fail on an unedited file. State that in the helper's
  docstring.

  Add `_check_fork_override() -> list[str]` following the file's established shape — a module-level
  function returning a list of `FAIL: ...` strings, no assertions, no printing. It must assert:

  - `mill-go2`'s extracted body is not `None`, is not the string `"(none)"`, contains the literal
    `fixer`, and contains the literal `subagent_type: "fork"`.
  - `mill-go`'s extracted body is not `None` and is exactly the string `"(none)"` after stripping.
    Write this as an equality, never a `"(none)" in body` containment check — the equality is what
    fails loudly if the extraction rule ever regresses to running to EOF and starts swallowing the
    shared base-loading paragraph.

  Emit one distinct `FAIL:` string per violated condition, each naming the offending path, so the
  five scenarios the check exists to catch are distinguishable from the output alone: the override
  added to the wrong variant, the placeholder `(none)` left in place alongside the override, a
  section filled with prose that never names `fork`, `mill-go`'s `(none)` deleted during a
  sibling-task merge resolution, and the extraction rule regressing to EOF.

  Register `_check_fork_override` last in `main()`'s `checks` tuple and change `main()`'s docstring
  from "Run all seven variant-contract checks" to "Run all eight variant-contract checks". Extend the
  module docstring's closing sentence to mention that the file also locks each variant's declared
  fixer-dispatch override.

  Failure strings are ASCII only: use ` -- ` rather than an em dash and `->` rather than an arrow
  glyph, per the repo's ASCII-only rule for `print()` output.

- **Commit:** `test(variants): lock the mill-go2 fixer fork override`

### Card 4: Write the fixer fork override in mill-go2's SKILL.md

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/unit_tests/test-mill-go-variants.py`
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the single `(none)` line under `## Dispatch overrides` with the block below, verbatim.
  Leave the `## Dispatch overrides` header line itself byte-identical — the required-header check
  matches it against `splitlines()`, so altering, indenting, or suffixing it breaks the contract.
  Leave `## Driver preamble` at `(none)`, leave `## Variant binding` untouched, and leave the shared
  base-loading paragraph after the section untouched.

```
### fixer

Governs the **first** fixer dispatch per scope and round only.
`fork_attempted` is true when this session already forked a fixer for that scope
and round, or when `_status.read_fork_fallback_log(status_path)` returns a row for
them; when it is true -- including step 4's re-dispatch -- use the default
`Agent()` call with the envelope's own `subagent_type` and `model`.

Otherwise dispatch `Agent(subagent_type: "fork", prompt: "Read this file and
follow the instructions exactly: <brief_path>")`.
Omit `model` and `isolation`: a fork runs on the driver's model regardless, and
the fixer must commit in the real worktree.
The brief stays the contract; inherited context never replaces reading it.

On the first terminal failure classification under the base's step 4, record the
fallback and re-dispatch cold, consuming the existing one-retry budget:

- `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"fixer {scope} r{N}", slug=slug)`
- `_status.append_fork_fallback_log(status_path, scope, N, _timestamp.now_utc_iso())`
- `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: fork-fallback for fixer {scope} r{N}"`

Commit that row **before** the cold retry -- a resumed session reconstructs
`fork_attempted` from it. `{scope}` is the batch name, or `holistic`.

Risks: a fork inherits the driver's broader tool grant (scope discipline still
comes from the brief and finalize's `scope_violations` gate), and forfeits
`roles.fixer.model` -- drive this variant from a solid model tier.
```

  The block is written the way it is for reasons that must survive an edit:

  - `<VARIANT_LABEL>` appears in the notify event and the commit message rather than a literal
    variant name. A literal `mill-go2` would not trip the hardcoded-literal ban, but the placeholder
    matches how the base parameterizes the same three literal families and survives a future rename.
  - The section never names the shared dispatch pattern by its heading, and never contains
    `## Agent-mode dispatch`, `## Holistic code review`, `## Execute`, or `You are the **Builder**`.
    All four are banned machinery literals in a variant file. Refer to the base by step number only.
  - The applicability condition is stated first and is not optional prose. The base's step 4 retry is
    an action inside step 4, not a fresh pass through step 3, so nothing structural distinguishes the
    retry from the first dispatch. Without the condition, the cold fallback silently becomes a
    re-fork.
  - The predicate consults `_status.read_fork_fallback_log` and not only session memory, because the
    base's Resume path re-runs the dispatch flow in a fresh Builder session with no memory of a prior
    attempt.
  - `model` and `isolation` are omitted deliberately, not passed and ignored. A fork always runs on
    the parent's model, and worktree isolation would break the fixer's requirement to commit in the
    real worktree.
  - The prompt string is character-identical to the base's default `Agent()` prompt. The brief stays
    the contract that finalize's `scope_violations` gate depends on;
    inherited context is additive, never a substitute.

  After the edit, the file must be under 4096 bytes — the thin-variant cap the contract test
  enforces. The block above lands the file at roughly 2330 bytes, leaving about 1770 bytes of
  headroom for the sibling `mill-go2-fork-implementer` task's `### implementer` block. Keep it there:
  do not pad the section with restatements of base behaviour.

- **Commit:** `feat(mill-go2): fork-dispatch the fixer role`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-mill-go-variants.py`, the standalone runner that owns
every assertion about the two variant SKILL.md files. It is scoped to exactly the surface this batch
touches — no `run-all.py` sweep is warranted, since nothing in this batch is importable code.

The new `_check_fork_override` is the batch's own coverage. The rest of the file's regression value
comes for free once the variant file is edited: the 4096-byte thin-variant cap, the four
machinery-literal bans, the three required header lines, the single-`VARIANT_LABEL`-binding rule, and
the hardcoded-`mill-go`-literal ban all re-run against the enlarged file and must still pass. Those
need no new assertions.

The fork dispatch itself is deliberately not tested. Whether `Agent(subagent_type: "fork")` produces a
usable fixer is the experiment's question, answered by running the variant on a real task;
the `## Fork-fallback log` rows batch 1 makes possible are the instrument for that observation.
