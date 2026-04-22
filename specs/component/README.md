# specs/component — mill-v2 implementation roadmap

Each file in this directory is **one task** on the way to a working
mill-v2. Together they describe everything between the current code and
a complete, self-driving Layer-03/04 system. Files are numbered by
implementation order — dependencies are encoded in the numbering.

## Finding the next task

```yaml
rule: "Next task = the lowest-numbered file in this directory whose name
       does not start with done-."
```

`done-`-prefixed files are finished and merged to `main`; their body is
kept as historical reference (implementation notes, design rationale,
what was in scope vs. dropped). They sort last alphabetically so the
unfinished work is always at the top of the listing.

At the time of writing, `done-01-llm-session-id.md`, `done-02-mill-
spawn-script.md`, and `done-03-mill-start-skill.md` are complete; the
next unfinished file is whatever currently reads `NN-<name>.md` with the
lowest `NN`.

## Workflow: spec → branch → done

A new thread picking up here should follow this cycle. None of it is
automated yet (that's partly what we're building).

1. **Pick the next spec.** Read the lowest-numbered `NN-*.md`. Grill
   the user on any "Open design points" section before writing code;
   specs are marked `status: partially discussed` until a concrete
   implementation thread has pinned them down.

2. **Create a branch.** Name it `impl/NN-<short-name>` (matching the
   spec's number), check it out, and do all work there. Do not commit
   work-in-progress directly to `main` — see the project commit
   discipline.

3. **Implement + test.**
   - Scripts + helpers live under `plugins/mill/scripts/`, skills under
     `plugins/mill/skills/<name>/SKILL.md`, templates under
     `plugins/mill/templates/`.
   - Python helpers get a `__main__` smoke test at the bottom. End-to-
     end integration tests live in `plugins/mill/integration_tests/`.
   - Skills stay **short** — anything that can live in a template file
     (`plugins/mill/templates/<something>.md`) should live there; the
     SKILL.md itself is prose instructions only.

4. **Verify.** All smoke tests pass locally. Any new integration test
   passes against an isolated fixture under `.millhouse/scratch/`. Any
   existing integration test that touches changed code still passes.

5. **Mark the spec done.** Same pattern used on `done-01`/`02`/`03`:
   - Flip `status:` in the spec's fenced-yaml frontmatter to
     `done — merged to main <date> (branch impl/NN-<short>)`.
   - Replace the "For the thread that will do the full-write" paragraph
     with an **Implementation notes** block summarising what was actually
     built (files added / modified, deviations from the spec, tests
     added, non-obvious design calls). Keep it tight — one paragraph.
   - `git mv NN-<name>.md done-NN-<name>.md`.

6. **Merge to main.**
   - `git push origin impl/NN-<short>`.
   - `git checkout main && git merge --no-ff impl/NN-<short>`.
   - `git push origin main`.
   - `git branch -d impl/NN-<short> && git push origin --delete
     impl/NN-<short>`.

7. **Propagate any wiki changes.** If the spec added new config keys,
   commit + push them in the wiki repo separately.

## Definition of done

A spec is done when all of the following are true:

- Implementation code is committed on `main`.
- All helpers have smoke tests in `__main__` and they pass.
- Any new integration test passes; existing ones still pass.
- The spec file is renamed with a `done-` prefix.
- The spec's frontmatter `status:` reads `done — ...` with the merge
  date and implementation branch.
- The spec body has an **Implementation notes** paragraph replacing the
  "grill Henrik" preamble.
- The `impl/NN-<short>` branch is deleted locally and on origin.

## Why this lives here instead of a script

A `mill-next-spec` script could do all the bookkeeping above
automatically, but the value of the flow is the human judgment at each
step (design grilling, tradeoffs, test coverage calls). Scripting it
would hide the judgment without removing the work. Once Layer-04's
`mill-groom` and related tooling are built, parts of the done-marking
step may move into `_tasks_md` / a thin helper; the branch/merge loop
stays manual.
