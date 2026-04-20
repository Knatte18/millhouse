# Integration test for mill-review-code.py
#
# The .millhouse/ layout, wiki junction, and slug file are all placed inside
# $tmp/project/ (not directly in $tmp/) because the code backend uses
# cwd=project_root for its git commands (git merge-base, git diff).
#
# Setup:
#   1. Init git repo in $tmp/project/ with main branch.
#   2. Create base-file.py, commit as "base" on main.
#   3. Checkout task-branch; apply sample-code-diff.patch; commit.
#   4. Seed .millhouse/ + wiki junction + slug file inside $tmp/project/.
#   5. Seed active/test-slug/plan/00-overview.md in the fixture wiki.
#   6. Push-Location $tmp/project; invoke mill-review-code.py; Pop-Location.
#
# Assertions:
#   - Exit 0
#   - Valid JSON with type="code", reviews.Count=1, scope="holistic"
#   - review file exists, has matching verdict: in frontmatter
#
# Prerequisites: claude in PATH, valid Claude subscription, git in PATH.
#
# Usage (from hub/):
#     pwsh plugins/mill/integration_tests/test-review-code.ps1
#
# Exits 0 on PASS, non-zero with a descriptive error on FAIL.

$ErrorActionPreference = 'Stop'

$millRoot   = Split-Path -Parent $PSScriptRoot
$scripts    = Join-Path $millRoot 'scripts'
$fixtures   = Join-Path $PSScriptRoot 'fixtures'

$env:PYTHONPATH      = $scripts
$env:PYTHONIOENCODING = 'utf-8'

$randomId   = [Guid]::NewGuid().ToString('N').Substring(0, 8)
$tmp        = Join-Path $env:TEMP "mill-layer02-test-code-$randomId"
$projectDir = Join-Path $tmp 'project'

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & git @Args 2>&1 | Out-String
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args -join ' ') failed (exit $LASTEXITCODE): $out"
    }
    return $out
}

function Remove-Junction {
    param([string]$JunctionPath)
    if (Test-Path $JunctionPath) {
        $savedEAP = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            python -c "from pathlib import Path; import _junction; _junction.remove(Path(r'$JunctionPath').resolve())" 2>&1 | Out-Null
        } catch { }
        $ErrorActionPreference = $savedEAP
    }
}

# -------------------------------------------------------------------------
# Setup: project directory + git repo
# -------------------------------------------------------------------------
New-Item -ItemType Directory -Path $projectDir | Out-Null

# Init git repo on main branch
Invoke-Git '-C' $projectDir 'init' '--initial-branch=main' | Out-Null
Invoke-Git '-C' $projectDir 'config' 'user.email' 'test@mill' | Out-Null
Invoke-Git '-C' $projectDir 'config' 'user.name'  'mill-test' | Out-Null

# Create base-file.py that the patch will modify
$baseFileContent = @"
"""base-file.py — simple utility module used as a code-review test fixture."""
from __future__ import annotations


def greet(name: str) -> str:
    """Return a greeting string for the given name."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


def main() -> None:
    print(greet("world"))
    print(add(1, 2))


if __name__ == "__main__":
    main()
"@
Write-Utf8NoBom -Path (Join-Path $projectDir 'base-file.py') -Text $baseFileContent

Invoke-Git '-C' $projectDir 'add' 'base-file.py' | Out-Null
Invoke-Git '-C' $projectDir 'commit' '-m' 'base' | Out-Null

# Create task branch and apply the fixture patch
Invoke-Git '-C' $projectDir 'checkout' '-b' 'task-branch' | Out-Null

$fixturePatch = Join-Path $fixtures 'sample-code-diff.patch'
# git apply needs the path in a form git understands; use forward slashes
$fixturePatchFwd = $fixturePatch -replace '\\', '/'
Invoke-Git '-C' $projectDir 'apply' $fixturePatchFwd | Out-Null

Invoke-Git '-C' $projectDir 'add' 'base-file.py' | Out-Null
Invoke-Git '-C' $projectDir 'commit' '-m' 'apply diff' | Out-Null

# -------------------------------------------------------------------------
# Setup: .millhouse/ + wiki fixture inside $projectDir
# -------------------------------------------------------------------------
$millhouseDir = Join-Path $projectDir '.millhouse'
$wikiDir      = Join-Path $projectDir 'wiki-fixture'
$planDir      = Join-Path $wikiDir 'active\test-slug\plan'
$reviewsDir   = Join-Path $wikiDir 'active\test-slug\reviews'

New-Item -ItemType Directory -Path $millhouseDir | Out-Null
New-Item -ItemType Directory -Path $planDir      -Force | Out-Null
New-Item -ItemType Directory -Path $reviewsDir   -Force | Out-Null

# Seed slug file
$slugContent = @"
---
slug: test-slug
task_title: "Test code review"
---
"@
Write-Utf8NoBom -Path (Join-Path $millhouseDir '.test-slug.slug.md') -Text $slugContent

# Write fixture config.yaml
$configContent = @"
paths:
  discussion_file: active/<SLUG>/discussion.md
  plan_dir:        active/<SLUG>/plan/
  reviews_dir:     active/<SLUG>/reviews/

review:
  discussion:
    rounds: 2
    holistic: sonnetmax_tool

  plan:
    rounds: 3
    batch: sonnetmax
    holistic: sonnetmax

  code:
    rounds: 3
    reviewer: sonnetmax
    style: single
"@
Write-Utf8NoBom -Path (Join-Path $wikiDir 'config.yaml') -Text $configContent

# Seed a minimal plan overview referencing the changed file
$planOverviewContent = @"
---
kind: plan-overview
task: Test code review
verify: N/A
dev-server: N/A
approved: true
started: 20260420-100000
batches: [core]
root: .
---

# Test code review — Plan

## Context

Small refactor of base-file.py: add input validation to `greet()`, introduce
a `slugify()` helper with lru_cache.

## All Files Touched

- base-file.py
"@
Write-Utf8NoBom -Path (Join-Path $planDir '00-overview.md') -Text $planOverviewContent

# Create wiki junction: .millhouse/wiki -> wiki-fixture/
python -c "from pathlib import Path; import _junction; _junction.create(Path(r'$wikiDir').resolve(), Path(r'$millhouseDir\wiki').resolve())" | Out-Null

# -------------------------------------------------------------------------
# Test 1: happy path
# -------------------------------------------------------------------------
Write-Host "Test 1: happy path (code review)..."

$stderrFile = Join-Path $projectDir '_stderr1.txt'
Push-Location $projectDir
$savedEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $stdout = (python "$scripts\mill-review-code.py" 2>$stderrFile) -join "`n"
    $exitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedEAP
    Pop-Location
}

if ($exitCode -ne 0) {
    $stderrText = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw } else { "(no stderr)" }
    Write-Host "FAIL: mill-review-code.py exited $exitCode"
    Write-Host "stderr: $stderrText"
    Write-Host "stdout: $stdout"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($stdout)) {
    Write-Host "FAIL: stdout is empty (expected JSON)"
    exit 1
}

try {
    $result = $stdout | ConvertFrom-Json
} catch {
    Write-Host "FAIL: stdout is not valid JSON: $stdout"
    exit 1
}

if ($result.type -ne "code") {
    Write-Host "FAIL: expected type='code', got '$($result.type)'"
    exit 1
}

if ($result.round -ne 1) {
    Write-Host "FAIL: expected round=1, got '$($result.round)'"
    exit 1
}

if ($result.verdict -notin @("APPROVE", "REQUEST_CHANGES")) {
    Write-Host "FAIL: unexpected verdict '$($result.verdict)'"
    exit 1
}

if ($result.reviews.Count -ne 1) {
    Write-Host "FAIL: expected reviews.Count=1, got $($result.reviews.Count)"
    exit 1
}

if ($result.reviews[0].scope -ne "holistic") {
    Write-Host "FAIL: expected reviews[0].scope='holistic', got '$($result.reviews[0].scope)'"
    exit 1
}

$reviewFile = $result.reviews[0].file
if (-not (Test-Path $reviewFile)) {
    Write-Host "FAIL: review file does not exist: $reviewFile"
    exit 1
}

$reviewText   = Get-Content $reviewFile -Raw
$entryVerdict = $result.reviews[0].verdict
if ($reviewText -notmatch "verdict:\s*$entryVerdict") {
    Write-Host "FAIL: review file frontmatter does not contain 'verdict: $entryVerdict'"
    Get-Content $reviewFile | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
    exit 1
}

Write-Host "Test 1 PASS"

# -------------------------------------------------------------------------
# Cleanup (only on success; leave on failure for inspection)
# -------------------------------------------------------------------------
Remove-Junction -JunctionPath (Join-Path $millhouseDir 'wiki')
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

Write-Host "PASS — all code review tests passed"
exit 0
