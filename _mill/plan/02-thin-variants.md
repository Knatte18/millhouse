# Batch: thin-variants

```yaml
task: 'mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)'
batch: 'thin-variants'
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
depends-on: [1]
```

## Batch Scope

This batch writes the variant-contract test first, then the two thin variant files it asserts on:
`mill-go` (restored at its original path, now ~30 lines instead of 1424) and the new `mill-go2`.
Both bind a distinct `VARIANT_LABEL`, declare both override-point sections as `(none)`, and load
`mill:mill-go-base` for all machinery. At the end of this batch mill-go2 is functionally identical
to mill-go — only the invocation name, the commit-subject prefix, the notify event prefix, and the
echo prefix differ.

Card order is deliberate: card 6 writes `test-mill-go-variants.py` before either variant file exists,
so the test drives the shape of the contract rather than describing it after the fact. The batch's
`verify:` runs at batch end, after cards 7 and 8 have satisfied it.

The external interface this batch publishes, and that batch 3 consumes, is the existence of the
`plugins/mill/skills/mill-go2/` directory — enough on its own to register `mill:mill-go2`, since
`plugins/mill/.claude-plugin/plugin.json` lists only `agents` and skills are discovered from the
directory tree.

## Cards

### Card 6: Write the variant-contract test

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/unit_tests/test-skill-helper-drift.py`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-mill-go-variants.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create a new test file following the house shape used by
  `plugins/mill/unit_tests/test-skill-helper-drift.py`: a module docstring,
  `HUB = Path(__file__).resolve().parent.parent.parent.parent`,
  `SKILLS = HUB / "plugins" / "mill" / "skills"`, one function per check returning a list of failure
  strings, a `main()` that prints those strings to stderr and emits a `PASS:` or `FAIL:` summary
  line, returning 0 or 1, and `sys.exit(main())` under `if __name__ == "__main__":`. ASCII-only
  output — no non-ASCII characters in any `print()` string.

  Define `VARIANTS = ("mill-go", "mill-go2")` and `BASE = "mill-go-base"` as module constants, and
  build every file path the test reads as `SKILLS / <name> / "SKILL.md"`. The two variant files do
  not exist yet when this card runs — cards 7 and 8 create them — so the test is written against the
  contract, not against file content the implementer can inspect. The base file does exist, having
  been relocated in batch 1.

  Assert the following seven checks:

  1. **Label binding.** Each variant file matches `^VARIANT_LABEL:\s*(\S+)\s*$` on some line
     (compile with `re.MULTILINE`). Exactly one match per file. The captured value equals that
     variant's own directory name. The two captured values are distinct.
  2. **Both override-point sections present.** Each variant file contains a line that is exactly
     `## Dispatch overrides` and a line that is exactly `## Driver preamble`, so a variant cannot
     silently omit one and leave the base consulting a section that does not exist. Each variant
     also contains a line that is exactly `## Variant binding`.
  3. **Base is loaded.** Each variant file contains the literal `mill:mill-go-base`.
  4. **Base halts unbound.** `mill-go-base/SKILL.md` contains the literal
     `[mill-go-base] HALT: mill-go-base is not invocable directly` — the directive that fires when
     no variant bound a `VARIANT_LABEL`.
  5. **Variants carry no machinery.** For each variant file: its byte length is under 4096, and it
     contains none of the literals `## Agent-mode dispatch`, `## Holistic code review`,
     `## Execute`, or `You are the **Builder**`. This is the regression catch for someone
     re-inlining the base into a variant.
  6. **Override points are not called hooks.** Scoped, not global. Assert that neither variant file
     contains a line that is exactly `## Dispatch hooks` or exactly `## Driver hook`, and that
     neither of the base's two consulting directives names a hook: locate each base line containing
     the literal `consult your variant's` or the literal `treat your variant's`, and assert the word
     `hook` (case-insensitive) does not appear in that line. Do NOT search the base globally for the
     word — it legitimately inherits two incidental pre-existing occurrences of the English word
     unrelated to override points.
  7. **Parameterization lock.** `mill-go-base/SKILL.md` contains zero occurrences of each of the
     literals `commit -m "mill-go: `, `_notify.notify("mill-go.`, and `[mill-go]`, and contains at
     least one occurrence of each of `commit -m "<VARIANT_LABEL>: `,
     `_notify.notify("<VARIANT_LABEL>.`, and `[<VARIANT_LABEL>]`. Neither variant file contains any
     of the three `mill-go` literals either.

  Every failure message must name the offending file path and what was expected. Do not use the word
  `hook` in any function name, variable name, docstring, or comment except where check 6 quotes the
  banned header strings.
- **Commit:** `test: add mill-go variant-contract test`

### Card 7: Write the thin mill-go variant

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create the file at the path batch 1 vacated. It has exactly five parts, in this
  order, and contains no machinery of any kind:

  1. `---` frontmatter with `name: mill-go` and, as `description:`, the exact description value the
     mill-go skill carried before batch 1 relocated it, so `/mill-go`'s entry in the operator's skill
     list stays byte-identical to today's. Recover it verbatim — do not retype it from memory — with:

     ````bash
     git -C <worktree> show 6442a688:plugins/mill/skills/mill-go/SKILL.md | head -4
     ````

     `6442a688` is the last commit before this task's plan work began and is the anchor the rest of
     this plan cites for verified counts; use that literal SHA, never a relative `HEAD~N` offset.
     The recovered line begins "description: In a spawned worktree with an approved plan,
     sequentially execute every batch...". If that SHA is unreachable (a rebase since planning),
     find the pre-move blob with
     `git -C <worktree> log --follow --oneline -- plugins/mill/skills/mill-go-base/SKILL.md` and read
     the commit immediately before the rename; do not fall back to retyping.
  2. The H1 title line `# mill-go`.
  3. A `## Variant binding` section whose body is a fenced yaml block containing the single line
     `VARIANT_LABEL: mill-go`.
  4. A `## Driver preamble` section whose body is the single line `(none)`, immediately followed by
     a `## Dispatch overrides` section whose body is the single line `(none)`. Both sections must be
     present even though both are empty — the base halts on a missing `## Driver preamble`, and the
     variant-contract test asserts both headers exist.
  5. A short closing section instructing: load the `mill:mill-go-base` skill via the Skill tool,
     unconditionally and immediately, before any other action; all of this skill's behaviour — the
     Builder role, the entry phase gate, Prepare, the sequential batch loop, Agent-mode dispatch,
     Resume, holistic code review, and Handoff — lives in that skill; follow `mill-go-base` from its
     `## Entry` onward with `VARIANT_LABEL` bound to the value declared in part 3.

  Do NOT reproduce the `> Wiki access:` banner or the "You are the **Builder** — a lean orchestrator"
  paragraph here — both moved to the base in batch 1, and reproducing them would recreate exactly the
  duplication the base exists to remove. Do not use the word `hook` anywhere in this file.
  Keep the whole file under 4096 bytes.
- **Commit:** `feat(mill-go): reduce to a thin variant that loads mill-go-base`

### Card 8: Write the mill-go2 variant

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create the file with the same five-part shape card 7 defines, differing in
  exactly three places:

  - Frontmatter `name: mill-go2`.
  - Frontmatter `description:` — new text, not a copy of mill-go's. It must convey: an experimental,
    opt-in variant of the mill-go orchestrator; behaviourally identical to `/mill-go` today; exists
    so fork-dispatch experiments never destabilise the production orchestrator; invoked only by an
    explicit `/mill-go2`.
  - The `## Variant binding` block declares `VARIANT_LABEL: mill-go2`, and the H1 title line is
    `# mill-go2`.

  `## Driver preamble` and `## Dispatch overrides` are both present and both `(none)` — mill-go2
  introduces no fork behaviour and no dispatch divergence in this task. Do not add an
  `Agent(subagent_type: "fork")` call, or any reference to forking, anywhere in this file.

  Do not wire mill-go2 into any automatic path: mill-plan's handoff text keeps naming `/mill-go`
  alone, and mill-autofix, mill-resume, mill-status, and mill-pause are not taught about mill-go2.
  Do not add a `roles.mill-go2.*` section to any config file. Do not use the word `hook` anywhere in
  this file. Keep the whole file under 4096 bytes.
- **Commit:** `feat(mill-go2): add opt-in orchestrator variant`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-mill-go-variants.py` directly — the single test file
this batch creates, and the only test that asserts the variant contract. Running it by path rather
than through `run-all.py --only` keeps the gate to exactly the surface this batch introduces.

The seven checks in card 6 cover every claim the contract makes: distinct labels bound (1), both
override-point sections declared by both variants (2), the base actually loaded (3), the base's
unbound-halt directive present (4), no machinery re-inlined into a variant (5), the scoped
no-`hook`-as-a-name rule (6), and the three literal families fully parameterized in the base with
none left behind in the variants (7). Check 7 is what would catch a site missed by card 4's greps.

The two retargeted locks from batch 1 (`test-guards.py`, `test-skill-helper-drift.py`) are not
re-run here — they were already green at the end of batch 1, and this batch adds no wiki-cwd pattern
and no helper reference to any SKILL.md. Batch 3's `verify:` re-runs both alongside this batch's own
test as the plan's closing gate.
