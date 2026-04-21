# Batch 06: Integration tests

```yaml
kind: plan-batch
batch-name: integration-tests
batch-depends: [api-and-config]
approved: false
```

## Batch-Specific Context

One integration test per review type. Each test:

1. Creates a temporary `.millhouse/` layout with a seeded slug file, a
   `wiki/` junction pointing at a fixture wiki, an `active/<slug>/`
   directory with the relevant artefact (discussion.md / plan/ / test diff),
   and `config.yaml` with the `paths:` + `review:` sections.
2. Invokes the API script.
3. Asserts:
   - Exit code 0.
   - Stdout parses as JSON with required fields.
   - `verdict` ∈ {APPROVE, REQUEST_CHANGES}.
   - Each `reviews[]` entry has a file that exists.
   - Each review file has valid `verdict:` YAML frontmatter.

**Local-dev only.** Requires `claude` in PATH. Not for CI.

PowerShell is primary because Henrik's environment is Windows. Tests are
`.ps1` scripts under `plugins/mill/integration_tests/`.

Fixtures (shared across tests) live under
`integration_tests/fixtures/`:
- `fixtures/sample-discussion.md` — small-but-real discussion (could be a
  pared-down version of our own Layer 02 discussion).
- `fixtures/sample-plan/00-overview.md` + `01-core.md` — minimal two-file plan.
- `fixtures/sample-code-diff.patch` — a small git diff blob.

## Batch Files

- integration_tests/test-review-discussion.ps1
- integration_tests/test-review-plan.ps1
- integration_tests/test-review-code.ps1
- integration_tests/fixtures/sample-discussion.md
- integration_tests/fixtures/sample-plan/00-overview.md
- integration_tests/fixtures/sample-plan/01-core.md
- integration_tests/fixtures/sample-code-diff.patch

## Steps

### Step 14: Create fixtures + discussion integration test

- **Creates:** `integration_tests/fixtures/sample-discussion.md`, `integration_tests/test-review-discussion.ps1`
- **Modifies:** none
- **Reads:** `scripts/mill-review-discussion.py`, `specs/active/layer-02/discussion.md`
- **Requirements:**
  - `fixtures/sample-discussion.md`: a small but real discussion file with
    a `## Context`, `## Scope`, `## Decisions`, `## Open questions`, plus a
    `## Technical Context` section referencing 1–2 real-repo files (e.g.
    `plugins/mill/scripts/_render.py`). Enough that a tool-use reviewer
    has something meaningful to verify.
  - `test-review-discussion.ps1`:
    1. `$tmp = New-TemporaryDirectory`; set up `.millhouse/` inside it.
    2. Seed `.millhouse/.test-slug.slug.md` with `task_title: "Test discussion review"` in frontmatter.
    3. Create a test wiki dir `$tmp/wiki-clone/`; copy `config.yaml` with `paths:`/`review:`.
    4. Create `wiki-clone/active/test-slug/discussion.md` = contents of `sample-discussion.md`.
    5. Junction (`New-Item -ItemType Junction`): `$tmp/.millhouse/wiki` → `$tmp/wiki-clone`.
    6. `Push-Location $tmp`. `$output = python plugins/mill/scripts/mill-review-discussion.py`. `$exit = $LASTEXITCODE`. `Pop-Location`.
    7. `if ($exit -ne 0) { Write-Error "Exit $exit: $output"; exit 1 }`.
    8. `$result = $output | ConvertFrom-Json`. Assert:
       - `$result.type -eq "discussion"`
       - `$result.round -eq 1`
       - `$result.verdict` ∈ `@("APPROVE", "REQUEST_CHANGES")`
       - `$result.reviews.Count -eq 1`
       - `$result.reviews[0].scope -eq "holistic"`
       - `Test-Path $result.reviews[0].file` is true
       - review file contains `verdict:` line matching `$result.reviews[0].verdict`.
    9. Cleanup `$tmp`.
- **Explore:**
  - `scripts/mill-review-discussion.py` — the CLI contract.
  - `specs/active/layer-02/discussion.md` — Integration test fixtures section.
- **depends-on:** [13]
- **Test approach:** integration.
- **Key test scenarios:**
  - Happy: fixture discussion → valid JSON, review file written, exit 0.
  - Error: remove the slug file → exit 1, stderr "No active task".
- **Commit:** `test(review): integration test for discussion review`

### Step 15: Create plan fixtures + plan integration test

- **Creates:** `integration_tests/fixtures/sample-plan/00-overview.md`, `integration_tests/fixtures/sample-plan/01-core.md`, `integration_tests/test-review-plan.ps1`
- **Modifies:** none
- **Reads:** `scripts/mill-review-plan.py`, `specs/active/layer-02/discussion.md`, `C:/Code/millhouse-legacy/plugins/mill/doc/formats/plan.md`
- **Requirements:**
  - `sample-plan/00-overview.md`: v2 batch plan overview with `batches: [core]`, one Shared Decision, `## All Files Touched` listing 1–2 paths.
  - `sample-plan/01-core.md`: one batch file with 1–2 minimal cards (each with Reads/Modifies/Commit).
  - `test-review-plan.ps1`: like the discussion test, but seeds
    `active/test-slug/plan/00-overview.md` and `01-core.md`, plus the real-repo
    files referenced in `Reads:` must exist for the bulker to find them. Use
    `plugins/mill/scripts/_render.py` (exists from Layer 01) as a reference file the plan "reads".
  - Additional assertions over the discussion test:
    - `$result.type -eq "plan"`
    - `$result.reviews.Count -eq 2`  # 1 batch + 1 holistic
    - `$result.reviews` contains entry with `scope -eq "01-core"` and entry with `scope -eq "holistic"`
    - Each entry's file exists.
- **Explore:**
  - `C:/Code/millhouse-legacy/plugins/mill/doc/formats/plan.md` — v2 batch plan format details (frontmatter, Steps schema).
  - `scripts/mill-review-plan.py` — CLI contract and what config it expects.
- **depends-on:** [13]
- **Test approach:** integration.
- **Key test scenarios:**
  - Happy: 1-batch plan → 2 entries (batch + holistic), both files on disk.
  - Edge: plan with `holistic: ~` in config → only 1 entry (batch), no holistic.
- **Commit:** `test(review): integration test for plan review`

### Step 16: Create code fixture + code integration test

- **Creates:** `integration_tests/fixtures/sample-code-diff.patch`, `integration_tests/test-review-code.ps1`
- **Modifies:** none
- **Reads:** `scripts/mill-review-code.py`, `specs/active/layer-02/discussion.md`
- **Requirements:**
  - `sample-code-diff.patch`: a small unified-diff blob representing a
    plausible code change. Apply-able via `git apply`. 1–2 files, ~30 lines.
    **Important:** the patch must modify a file that **already exists in the
    base commit** (see fixture setup below). Concretely: base commit creates
    `project/base-file.py` with a simple stub; the patch modifies this same
    `base-file.py`. Otherwise `git apply` fails with "does not match index".
  - `test-review-code.ps1`:
    1. Set up `.millhouse/` + wiki junction + `.<slug>.slug.md` all **inside
       `$tmp/project/`** (not in `$tmp/` directly). This is different from
       the discussion and plan tests because the code backend uses
       `cwd=project_root` for its git commands, so `project_root` must
       both be a git repo AND contain the `.millhouse/` tree.
    2. Create a scratch git repo inside `$tmp/project/` with **explicit
       branch layout** so `git merge-base main HEAD` produces the expected
       base:
       ```powershell
       git -C $tmp/project init --initial-branch=main
       # write base file
       git -C $tmp/project add . ; git -C $tmp/project commit -m "base"
       git -C $tmp/project checkout -b task-branch
       git -C $tmp/project apply $fixtureDiffPath
       git -C $tmp/project add . ; git -C $tmp/project commit -m "apply diff"
       ```
       Now `git -C $tmp/project merge-base main HEAD` returns the base commit SHA,
       and `git -C $tmp/project diff <base>..HEAD` yields the fixture diff.
    3. Seed `active/test-slug/plan/00-overview.md` (simple plan referring to the changed files).
    4. `Push-Location $tmp/project`. Invoke `python <hub>/plugins/mill/scripts/mill-review-code.py`. `Pop-Location` after.
    5. Assert the same shape as the discussion test, with `type -eq "code"`.
- **Explore:**
  - `scripts/mill-review-code.py` — CLI contract.
  - `scripts/_review_code.py` — understand the `git merge-base main HEAD` dependency.
- **depends-on:** [13]
- **Test approach:** integration.
- **Key test scenarios:**
  - Happy: diff present → exit 0, review file written.
  - Error: no task branch (on main, no diff) → exit 1 with clear message.
- **Commit:** `test(review): integration test for code review`
