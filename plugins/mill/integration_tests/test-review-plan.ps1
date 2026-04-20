# Integration test for mill-review-plan.py
#
# Sets up a temporary .millhouse/ layout with a seeded slug file, a wiki/
# junction pointing at a fixture wiki containing a sample plan (00-overview.md
# + 01-core.md), then invokes mill-review-plan.py and asserts:
#   - Exit 0
#   - Valid JSON with type/round/verdict/reviews fields
#   - verdict in {APPROVE, REQUEST_CHANGES}
#   - reviews.Count -eq 2 (1 batch + 1 holistic)
#   - reviews contains entry with scope "01-core" and entry with scope "holistic"
#   - each entry's file exists on disk
#   - each review file has YAML frontmatter with matching verdict:
#
# Prerequisites: claude in PATH, valid Claude subscription.
#
# Usage (from hub/):
#     pwsh plugins/mill/integration_tests/test-review-plan.ps1
#
# Exits 0 on PASS, non-zero with a descriptive error on FAIL.

$ErrorActionPreference = 'Stop'

$millRoot   = Split-Path -Parent $PSScriptRoot
$scripts    = Join-Path $millRoot 'scripts'
$fixtures   = Join-Path $PSScriptRoot 'fixtures'

$env:PYTHONPATH      = $scripts
$env:PYTHONIOENCODING = 'utf-8'

$randomId = [Guid]::NewGuid().ToString('N').Substring(0, 8)
$tmp      = Join-Path $env:TEMP "mill-layer02-test-plan-$randomId"

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
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
# Setup
# -------------------------------------------------------------------------
New-Item -ItemType Directory -Path $tmp | Out-Null

$millhouseDir = Join-Path $tmp '.millhouse'
$wikiDir      = Join-Path $tmp 'wiki-fixture'
$planDir      = Join-Path $wikiDir 'active\test-slug\plan'
$reviewsDir   = Join-Path $wikiDir 'active\test-slug\reviews'

New-Item -ItemType Directory -Path $millhouseDir | Out-Null
New-Item -ItemType Directory -Path $planDir      -Force | Out-Null
New-Item -ItemType Directory -Path $reviewsDir   -Force | Out-Null

# Seed slug file
$slugContent = @"
---
slug: test-slug
task_title: "Test plan review"
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

# Seed plan fixture files.
# 01-core.md Reads: scripts/_render.py  (relative to root: plugins/mill).
# The real file exists in the hub repo; the plan backend resolves Reads: paths
# relative to project_root (which is $tmp when Push-Location is used).
# We need the file to exist at $tmp/plugins/mill/scripts/_render.py so the
# bulker can read it. Copy it from the real repo.
$readsTarget = Join-Path $tmp 'plugins\mill\scripts'
New-Item -ItemType Directory -Path $readsTarget -Force | Out-Null
Copy-Item (Join-Path $scripts '_render.py') (Join-Path $readsTarget '_render.py')

Copy-Item (Join-Path $fixtures 'sample-plan\00-overview.md') (Join-Path $planDir '00-overview.md')
Copy-Item (Join-Path $fixtures 'sample-plan\01-core.md')     (Join-Path $planDir '01-core.md')

# Create wiki junction: .millhouse/wiki -> wiki-fixture/
python -c "from pathlib import Path; import _junction; _junction.create(Path(r'$wikiDir').resolve(), Path(r'$millhouseDir\wiki').resolve())" | Out-Null

# -------------------------------------------------------------------------
# Test 1: happy path
# -------------------------------------------------------------------------
Write-Host "Test 1: happy path (plan review)..."

$stderrFile = Join-Path $tmp '_stderr1.txt'
Push-Location $tmp
$savedEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $stdout = (python "$scripts\mill-review-plan.py" 2>$stderrFile) -join "`n"
    $exitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedEAP
    Pop-Location
}

if ($exitCode -ne 0) {
    $stderrText = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw } else { "(no stderr)" }
    Write-Host "FAIL: mill-review-plan.py exited $exitCode"
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

if ($result.type -ne "plan") {
    Write-Host "FAIL: expected type='plan', got '$($result.type)'"
    exit 1
}

if ($result.verdict -notin @("APPROVE", "REQUEST_CHANGES")) {
    Write-Host "FAIL: unexpected verdict '$($result.verdict)'"
    exit 1
}

if ($result.reviews.Count -ne 2) {
    Write-Host "FAIL: expected reviews.Count=2 (1 batch + 1 holistic), got $($result.reviews.Count)"
    exit 1
}

# Check for batch entry with scope "01-core"
$batchEntry    = $result.reviews | Where-Object { $_.scope -eq "01-core" }
$holisticEntry = $result.reviews | Where-Object { $_.scope -eq "holistic" }

if ($null -eq $batchEntry) {
    Write-Host "FAIL: no reviews entry with scope='01-core'"
    Write-Host "Scopes present: $($result.reviews | ForEach-Object { $_.scope })"
    exit 1
}

if ($null -eq $holisticEntry) {
    Write-Host "FAIL: no reviews entry with scope='holistic'"
    Write-Host "Scopes present: $($result.reviews | ForEach-Object { $_.scope })"
    exit 1
}

foreach ($entry in $result.reviews) {
    if (-not (Test-Path $entry.file)) {
        Write-Host "FAIL: review file does not exist for scope '$($entry.scope)': $($entry.file)"
        exit 1
    }
    $reviewText   = Get-Content $entry.file -Raw
    $entryVerdict = $entry.verdict
    if ($reviewText -notmatch "verdict:\s*$entryVerdict") {
        Write-Host "FAIL: review file for scope '$($entry.scope)' missing 'verdict: $entryVerdict'"
        Get-Content $entry.file | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
        exit 1
    }
}

Write-Host "Test 1 PASS"

# -------------------------------------------------------------------------
# Cleanup (only on success; leave on failure for inspection)
# -------------------------------------------------------------------------
Remove-Junction -JunctionPath (Join-Path $millhouseDir 'wiki')
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

Write-Host "PASS — all plan review tests passed"
exit 0
