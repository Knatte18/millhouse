# Integration test for mill-review-discussion.py
#
# Sets up a temporary .millhouse/ layout with a seeded slug file, a wiki/
# junction pointing at a fixture wiki containing a sample discussion.md,
# then invokes mill-review-discussion.py and asserts:
#   - Exit 0
#   - Valid JSON with type/round/verdict/reviews fields
#   - verdict in {APPROVE, REQUEST_CHANGES}
#   - reviews.Count -eq 1, scope -eq "holistic"
#   - review file exists on disk
#   - review file has YAML frontmatter with matching verdict:
#
# Also tests the "No active task" error path.
#
# Prerequisites: claude in PATH, valid Claude subscription.
#
# Usage (from hub/):
#     pwsh plugins/mill/integration_tests/test-review-discussion.ps1
#
# Exits 0 on PASS, non-zero with a descriptive error on FAIL.

$ErrorActionPreference = 'Stop'

$millRoot   = Split-Path -Parent $PSScriptRoot
$scripts    = Join-Path $millRoot 'scripts'
$fixtures   = Join-Path $PSScriptRoot 'fixtures'

$env:PYTHONPATH      = $scripts
$env:PYTHONIOENCODING = 'utf-8'

$randomId = [Guid]::NewGuid().ToString('N').Substring(0, 8)
$tmp      = Join-Path $env:TEMP "mill-layer02-test-discussion-$randomId"

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
$activeDir    = Join-Path $wikiDir 'active\test-slug'
$reviewsDir   = Join-Path $wikiDir 'active\test-slug\reviews'

New-Item -ItemType Directory -Path $millhouseDir | Out-Null
New-Item -ItemType Directory -Path $activeDir    -Force | Out-Null
New-Item -ItemType Directory -Path $reviewsDir   -Force | Out-Null

# Seed slug file with task_title in frontmatter
$slugContent = @"
---
slug: test-slug
task_title: "Test discussion review"
---
"@
Write-Utf8NoBom -Path (Join-Path $millhouseDir '.test-slug.slug.md') -Text $slugContent

# Write fixture config.yaml (same shape as production wiki/config.yaml)
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

# Seed discussion fixture file
Copy-Item (Join-Path $fixtures 'sample-discussion.md') (Join-Path $activeDir 'discussion.md')

# Create wiki junction: .millhouse/wiki -> wiki-fixture/
python -c "from pathlib import Path; import _junction; _junction.create(Path(r'$wikiDir').resolve(), Path(r'$millhouseDir\wiki').resolve())" | Out-Null

# -------------------------------------------------------------------------
# Test 1: happy path
# -------------------------------------------------------------------------
Write-Host "Test 1: happy path (discussion review)..."

$stderrFile = Join-Path $tmp '_stderr1.txt'
Push-Location $tmp
$savedEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $stdout = (python "$scripts\mill-review-discussion.py" 2>$stderrFile) -join "`n"
    $exitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedEAP
    Pop-Location
}

if ($exitCode -ne 0) {
    $stderrText = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw } else { "(no stderr)" }
    Write-Host "FAIL: mill-review-discussion.py exited $exitCode"
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

if ($result.type -ne "discussion") {
    Write-Host "FAIL: expected type='discussion', got '$($result.type)'"
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

$reviewText = Get-Content $reviewFile -Raw
$entryVerdict = $result.reviews[0].verdict
if ($reviewText -notmatch "verdict:\s*$entryVerdict") {
    Write-Host "FAIL: review file frontmatter does not contain 'verdict: $entryVerdict'"
    Write-Host "Review file contents (first 20 lines):"
    Get-Content $reviewFile | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
    exit 1
}

Write-Host "Test 1 PASS"

# -------------------------------------------------------------------------
# Test 2: error path — no active task (slug file removed)
# -------------------------------------------------------------------------
Write-Host "Test 2: error path (no active task)..."

$slugFile = Join-Path $millhouseDir '.test-slug.slug.md'
Remove-Item $slugFile -Force

Push-Location $tmp
$savedEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $errOut  = (python "$scripts\mill-review-discussion.py" 2>&1) -join "`n"
    $errExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedEAP
    Pop-Location
}

if ($errExit -eq 0) {
    Write-Host "FAIL: expected exit 1 when no slug file present, got exit 0"
    exit 1
}

if ($errOut -notmatch "No active task") {
    Write-Host "FAIL: expected 'No active task' in stderr, got: $errOut"
    exit 1
}

Write-Host "Test 2 PASS"

# -------------------------------------------------------------------------
# Cleanup (only on success; leave on failure for inspection)
# -------------------------------------------------------------------------
Remove-Junction -JunctionPath (Join-Path $millhouseDir 'wiki')
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

Write-Host "PASS — all discussion review tests passed"
exit 0
