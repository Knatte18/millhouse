# Batch: docs

```yaml
task: 32 (A) — Bug-fix batch 2
batch: docs
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Two pure-documentation updates. No code change, no test surface, no runnable verify. Grouped into one batch because both are short prose edits to existing files; they have no logical dependency on each other but are too small to justify separate batches. `verify: null` is correct — the batch has no executable behavior to test.

## Cards

### Card 10: Add $CLAUDE_PLUGIN_ROOT empty-shell warning to CLAUDE.md

- **Context:** none
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Locate the bullet starting `**Mill scripts are invoked via \`uv run\`, not \`python\`.**` in `CLAUDE.md`'s "Conventions worth carrying" section (currently around lines 104). At the end of that bullet's paragraph (after the existing sentence ending `…uses an inline \`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"\` prefix on each call.`), append a new sentence: `Similarly, \`${CLAUDE_PLUGIN_ROOT}\` may be empty in some Bash subshells (observed on Windows VS Code's integrated terminal); when empty, hardcode the cache path the user supplies, or fall back to \`plugins/mill/\` source-tree paths only when running from the millhouse repo itself — never assume the env var resolves at runtime.` Keep the bullet as a single coherent paragraph; do not introduce a new sub-bullet. Do not modify any other section of CLAUDE.md.
- **Commit:** `docs(claude-md): warn about empty $CLAUDE_PLUGIN_ROOT in subshells`

### Card 11: Document --holistic-only and --no-holistic in mill-plan SKILL.md

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-plan/SKILL.md`, locate "Phase: Plan Review" → step 2 (the bash invocation block ending `\`\`\``). Immediately AFTER the closing fence of that bash block (and before the existing step-2 paragraph that begins `This returns immediately with \`pid=<N> log=<abs-path>\`...`), insert a new paragraph: `The CLI accepts two optional scope flags (mutually exclusive): \`--holistic-only\` skips per-batch reviews and runs only the holistic plan review; \`--no-holistic\` skips the holistic plan review and runs per-batch reviews only. Default — both run per the \`review.plan.batch\` and \`review.plan.holistic\` config keys. Append the flag to the inner \`uv run …millpy-review-plan.py\` portion of the millpy-bg invocation when needed.` The flag descriptions MUST match the help text in `millpy-review-plan.py` lines 7–10 verbatim — re-read that file to confirm wording before writing the paragraph. Do not modify the bash block itself; do not modify the surrounding step-2 prose. Do not modify any other phase of the SKILL.md.
- **Commit:** `docs(mill-plan): document --holistic-only and --no-holistic flags`

## Batch Tests

`verify: null` — no runnable surface. Correctness is verified by reading the rendered diff: Card 10's new sentence reads naturally as the final clause of the existing PYTHONPATH bullet; Card 11's new paragraph sits between step-2's bash block and its trailing prose without disrupting either.
