# Dev Loop — how to build v2 iteratively

```yaml
status: draft
audience: the developer (you) and the CC that helps build v2
```

## How to work on a layer

Each layer is built to completion before moving on. Within a layer, the rhythm is:

1. **Re-read the layer spec.** Refresh on deliverables, v1 reuse candidates, non-goals.
2. **Lift v1 primitives first.** Open the files listed under "v1 reuse for this layer", copy, strip, clean. Commit as a distinct commit (`reuse: carry junction from v1`).
3. **Write the new script(s).** One at a time. Keep each under 300 LOC.
4. **Write the integration test for that script.** One `.ps1` file. Run it. If it passes, the script is "done" for this layer.
5. **Write the skill file.** Short markdown, 50–150 lines. Describe what Claude does when invoked.
6. **Commit and move to next script.**

When all scripts for the layer are done + tested + skilled, the layer is done. Tag it: `layer-01-done`.

## Commands you'll actually type

### First-time setup in this repo

```powershell
cd C:\Code\millhouse\hub
# nothing else — the repo starts with LICENSE + specs only
```

### Testing a script during development

```powershell
# From hub/, run the script against a throwaway setup
python plugins/mill/scripts/mill-setup.py --wiki-url https://github.com/Knatte18/test-wiki.git

# Check result
ls .millhouse/
```

### Running integration tests

```powershell
# Single test
pwsh plugins/mill/integration_tests/test-bootstrap.ps1

# All tests in a layer
Get-ChildItem plugins/mill/integration_tests/test-*.ps1 | ForEach-Object {
    Write-Host "=== $($_.Name) ==="
    pwsh $_.FullName
}
```

If a test needs a fake wiki, it creates one in `$env:TEMP`. Never point tests at the real wiki.

### Checking LOC budget

```powershell
# Total Python LOC (excluding blanks and comments)
Get-ChildItem plugins/mill/scripts -Recurse -Filter *.py | ForEach-Object {
    $lines = Get-Content $_.FullName | Where-Object { $_ -match '\S' -and $_ -notmatch '^\s*#' }
    [pscustomobject]@{ File = $_.Name; LOC = $lines.Count }
} | Format-Table
```

Over 1500 total → STOP, look at what's bloating.

### Checking skill file sizes

```powershell
Get-ChildItem plugins/mill/skills -Recurse -Filter SKILL.md | ForEach-Object {
    [pscustomobject]@{ Skill = $_.Directory.Name; Lines = (Get-Content $_.FullName).Count }
} | Sort Lines -Descending | Format-Table
```

Any skill over 200 lines → split or trim.

## Working with Claude Code while building

When CC helps write code for a layer, give it this minimal context:

> Read `specs/00-overview.md`, `specs/0N-<layer>.md`, `specs/06-v1-reuse.md`, `specs/08-legacy-index.md`. Then implement the scripts listed under "Deliverables" in the layer spec.

Tell CC explicitly:
- "Before writing any new code, lift v1 primitives per 06-v1-reuse.md"
- "Keep each file under 300 lines — if it's getting bigger, stop and show me the structure"
- "No pytest, no test files beyond what 01/02/... specs list"
- "No abstractions — dict dispatch over class hierarchies"

If CC produces a 500-line file with a Protocol class, stop, reject, ask for "minimum version".

## When to deviate from the spec

The specs are the plan, not the law. If while building you discover:

- A layer's boundary is wrong (something belongs in layer N-1)
- A format needs a field you didn't anticipate
- An LOC budget is unachievable without sacrificing clarity

Edit the spec first. Commit the spec change. Then adjust the code.

What you should NOT do:
- Silently write code that contradicts the spec
- Add abstractions "because they'll help later"
- Add tests beyond the integration test for this layer

## Measuring progress

After each layer lands:

- [ ] Integration test passes
- [ ] LOC budget not exceeded
- [ ] No new formats beyond what the format inventory lists
- [ ] Skill file exists and is under 200 lines
- [ ] A real-world end-to-end run works (not just the integration test)

Only when all five check out: tag the layer and move on.

## Debugging workflow

When a layer doesn't work end-to-end:

1. **Read stderr from the script.** If `print(..., file=sys.stderr)` isn't enough, add more.
2. **Check the wiki state.** `cat wiki/active/<slug>/status.md`. Often reveals the disconnect.
3. **Inspect `.millhouse/scratch/`.** Briefs, prompts, and transient output live here.
4. **Re-run the integration test.** If it fails now but passed before, something drifted.
5. **Do NOT add pytest fixtures to chase the bug.** Add a `.ps1` integration test if you want it permanently caught.

## Stop conditions

Stop working on a layer if:

- You've rewritten the same file 3 times — the design is wrong
- CC has produced >500 LOC for the layer — scope creep
- You're about to add a new format not in the inventory — stop, spec first
- A test requires mocking multiple things — indicates coupling, simplify
- You've spent more than 2 days on a single script — it's bigger than it should be

## Releasing

There is no release cycle for v2.0. Main is the only reference. Push to main when:

- A layer is fully done
- Integration tests pass
- You've personally verified it end-to-end

No semver, no changelog, no tags beyond `layer-0N-done` for your own reference.
