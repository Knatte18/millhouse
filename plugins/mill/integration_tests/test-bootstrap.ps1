# Layer 01 end-to-end test.
#
# Exercises the M1.1–M1.4 scripts against a throwaway wiki + hub pair in
# $env:TEMP. Asserts that mill-add produces a single commit touching
# Home.md + _Sidebar.md, that the sidebar contains the new task, and that
# mill-list prints it back out.
#
# This is the only integration test for Layer 01 — all other verification
# is the standalone-usage message on each script plus the real-world runs
# against Knatte18/millhouse.wiki. No pytest, no fixtures.
#
# Usage (from hub/):
#     pwsh plugins/mill/integration_tests/test-bootstrap.ps1
#
# Exits 0 on PASS, non-zero with a descriptive error on FAIL.

$ErrorActionPreference = 'Stop'

$millRoot  = Split-Path -Parent $PSScriptRoot
$scripts   = Join-Path $millRoot 'scripts'
$templates = Join-Path $millRoot 'templates'

# Per conversation/SKILL.md: never use $env:TEMP; use .scratch/ instead.
$hubRoot   = Split-Path -Parent $millRoot
$scratch   = Join-Path $hubRoot '.scratch'
New-Item -ItemType Directory -Path $scratch -Force | Out-Null
$tmp       = Join-Path $scratch ('bootstrap-test-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
$container = Join-Path $tmp       'container'
$bare      = Join-Path $container 'wiki.git'
$wiki      = Join-Path $container 'wiki'
$hub       = Join-Path $container 'hub'

# Some earlier milestones discovered cp1252-vs-UTF8 issues when Python
# prints rendered text to a Windows console (see legacy handoff notes).
# Force UTF-8 I/O for the duration of the test so assertions on output
# do not trip over mojibake.
$env:PYTHONIOENCODING = 'utf-8'

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    # PowerShell 5's Out-File -Encoding UTF8 writes a BOM which
    # _sidebar.regenerate strips on its next run and causes a spurious
    # diff. Write UTF-8 without BOM directly via .NET so the test's
    # seed state matches what _sidebar produces.
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    # PowerShell promotes stderr-via-2>&1 into ErrorRecords and, under
    # ErrorActionPreference=Stop, that converts harmless git warnings
    # ("warning: You appear to have cloned an empty repository") into
    # terminating failures. Temporarily drop EAP to Continue around the
    # git call so only a non-zero exit code — which we check ourselves —
    # raises.
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

try {
    # ------------------------------------------------------------------
    # 1. Seed the fake wiki remote.
    # ------------------------------------------------------------------
    #
    # The bare repo stands in for github.com/<owner>/<repo>.wiki.git.
    # --initial-branch=master matches the real GitHub wiki (which uses
    # master, not main) so `git push` with no args goes where we expect.
    New-Item -ItemType Directory -Path $bare | Out-Null
    Invoke-Git 'init' '--initial-branch=master' '--bare' $bare | Out-Null

    # Working clone of the wiki + initial Home.md from the real template.
    Invoke-Git 'clone' '-q' $bare $wiki | Out-Null
    Copy-Item (Join-Path $templates 'Home.md') (Join-Path $wiki 'Home.md')
    Invoke-Git '-C' $wiki 'add' 'Home.md' | Out-Null
    Invoke-Git '-C' $wiki '-c' 'user.email=test@mill' '-c' 'user.name=mill-test' 'commit' '-m' 'init Home.md' | Out-Null
    Invoke-Git '-C' $wiki 'push' '-u' 'origin' 'master' | Out-Null

    # ------------------------------------------------------------------
    # 2. Seed the fake hub + run the mill-setup phases (4/5/6a) that the
    #    scripts under test depend on. Phases 1/2/3/7/8 are skill-only
    #    judgment and not exercised here.
    # ------------------------------------------------------------------
    New-Item -ItemType Directory -Path (Join-Path $hub '.millhouse') -Force | Out-Null

    # Phase 4: junction
    uv run --project $millRoot python -c "from pathlib import Path; import _junction; _junction.create(Path(r'$wiki').resolve(), Path(r'$hub/.millhouse/wiki').resolve())" | Out-Null

    # Phase 5: config
    Copy-Item (Join-Path $templates 'config.local.yaml') (Join-Path $hub '.millhouse/config.local.yaml')

    # Phase 6a: sidebar regen + seed commit (so the remote has a valid sidebar)
    uv run --project $millRoot python -c "from pathlib import Path; import _sidebar; _sidebar.regenerate(Path(r'$wiki').resolve())" | Out-Null
    Invoke-Git '-C' $wiki 'add' '_Sidebar.md' | Out-Null
    Invoke-Git '-C' $wiki '-c' 'user.email=test@mill' '-c' 'user.name=mill-test' 'commit' '-m' 'init _Sidebar.md' | Out-Null
    Invoke-Git '-C' $wiki 'push' | Out-Null

    # Phase 4.7: PS1 shortcut wrappers
    $shortcutScripts = @(
        'millpy-add', 'millpy-list', 'millpy-status', 'millpy-inspect',
        'millpy-spawn', 'millpy-claim', 'millpy-cleanup', 'millpy-abandon',
        'millpy-color', 'millpy-terminal', 'millpy-vscode', 'millpy-worktree',
        'millpy-fetch-issues'
    )
    foreach ($s in $shortcutScripts) {
        Set-Content (Join-Path $hub ".millhouse/$s.py") "# legacy" -Encoding utf8
    }
    uv run --project $millRoot python -c "from pathlib import Path; import _shortcuts; _shortcuts.write_all(Path(r'$hub/.millhouse').resolve())" | Out-Null
    foreach ($s in $shortcutScripts) {
        if (-not (Test-Path (Join-Path $hub ".millhouse/$s.ps1"))) {
            throw "Phase 4.7: missing PS1 wrapper for $s"
        }
        if (Test-Path (Join-Path $hub ".millhouse/$s.py")) {
            throw "Phase 4.7: legacy .py wrapper not deleted for $s"
        }
    }

    # ------------------------------------------------------------------
    # 3. mill-add (plain — no proposal).
    # ------------------------------------------------------------------
    Push-Location $hub
    try {
        # Git needs user identity for the add task commit. Set it in the
        # wiki repo's local config — _wiki.write_commit_push runs git
        # from there, not from the hub.
        Invoke-Git '-C' $wiki 'config' 'user.email' 'test@mill' | Out-Null
        Invoke-Git '-C' $wiki 'config' 'user.name'  'mill-test' | Out-Null

        uv run --project $millRoot "$scripts/millpy-add.py" plain-foo --title 'Plain foo' --summary 'summary for plain foo' | Out-Null
    } finally { Pop-Location }

    # ------------------------------------------------------------------
    # 4. mill-add with proposal body.
    # ------------------------------------------------------------------
    Push-Location $hub
    try {
        uv run --project $millRoot "$scripts/millpy-add.py" linked-bar --title 'Linked bar' --summary 'summary for linked bar' --proposal-body "# Linked bar`n`nBackground paragraph." | Out-Null
    } finally { Pop-Location }

    # ------------------------------------------------------------------
    # 5. Assertions.
    # ------------------------------------------------------------------
    # NB: $home / $HOME is a read-only automatic variable in PowerShell,
    # so use $homeText here. $sidebar has no such conflict but keeping the
    # parallel naming avoids future surprises.
    $homeText    = Get-Content (Join-Path $wiki 'Home.md')    -Raw
    $sidebarText = Get-Content (Join-Path $wiki '_Sidebar.md') -Raw

    if ($homeText -notmatch '## Plain foo \[plain-foo\]') {
        throw "Home.md missing plain heading. Got:`n$homeText"
    }
    if ($homeText -notmatch '## Linked bar \[\[linked-bar\]\]\(proposal-linked-bar\)') {
        throw "Home.md missing linked heading. Got:`n$homeText"
    }

    if ($sidebarText -notmatch '- Plain foo') {
        throw "Sidebar missing plain entry. Got:`n$sidebarText"
    }
    if ($sidebarText -notmatch '- \[Linked bar\]\(proposal-linked-bar\)') {
        throw "Sidebar missing linked entry. Got:`n$sidebarText"
    }

    $proposalPath = Join-Path $wiki 'proposal-linked-bar.md'
    if (-not (Test-Path $proposalPath)) {
        throw "Proposal file not written: $proposalPath"
    }

    # Each mill-add should produce exactly one commit touching both
    # Home.md and _Sidebar.md (plus the proposal on the linked run).
    $plainStat  = Invoke-Git '-C' $wiki 'show' '--name-only' '--format=' 'HEAD^'
    $linkedStat = Invoke-Git '-C' $wiki 'show' '--name-only' '--format=' 'HEAD'

    foreach ($expected in 'Home.md', '_Sidebar.md') {
        if ($plainStat -notmatch [regex]::Escape($expected)) {
            throw "plain-foo commit missing $expected. Got:`n$plainStat"
        }
        if ($linkedStat -notmatch [regex]::Escape($expected)) {
            throw "linked-bar commit missing $expected. Got:`n$linkedStat"
        }
    }
    if ($linkedStat -notmatch [regex]::Escape('proposal-linked-bar.md')) {
        throw "linked-bar commit missing proposal file. Got:`n$linkedStat"
    }

    # ------------------------------------------------------------------
    # 6. mill-list — must show both tasks and mark the one with a
    #    proposal. Columns align on the longest slug width.
    # ------------------------------------------------------------------
    Push-Location $hub
    try {
        $listOut = (uv run --project $millRoot "$scripts/millpy-list.py") -join "`n"
    } finally { Pop-Location }

    if ($listOut -notmatch '    plain-foo\s+Plain foo') {
        throw "mill-list missing plain-foo row. Got:`n$listOut"
    }
    if ($listOut -notmatch '\[P\] linked-bar\s+Linked bar') {
        throw "mill-list missing linked-bar row with [P] marker. Got:`n$listOut"
    }

    # ------------------------------------------------------------------
    # 7. Duplicate-slug rejection. Same 2>&1 / EAP=Stop trap as Invoke-Git:
    # mill-add's stderr breadcrumbs (_acquire/_release inside wiki_lock, the
    # SystemExit message) get promoted to ErrorRecords under EAP=Stop and
    # the first one throws before we can inspect $LASTEXITCODE. Drop EAP
    # to Continue for the duration of the negative test.
    # ------------------------------------------------------------------
    Push-Location $hub
    try {
        $savedEAP = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $dupOut = (uv run --project $millRoot "$scripts/millpy-add.py" plain-foo --title 'dup' 2>&1) -join "`n"
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($LASTEXITCODE -eq 0) {
            throw "Duplicate add should have failed but exited 0. Output:`n$dupOut"
        }
        if ($dupOut -notmatch 'already present') {
            throw "Duplicate error message unexpected. Got:`n$dupOut"
        }
    } finally { Pop-Location }

    # Cleanup on success. The junction must come out before
    # Remove-Item can recurse into the hub, otherwise PowerShell follows
    # it into the wiki and fails on the bare repo's locked files.
    $junction = Join-Path $hub '.millhouse/wiki'
    if (Test-Path $junction) {
        try {
            uv run --project $millRoot python -c "from pathlib import Path; import _junction; _junction.remove(Path(r'$junction').resolve())" 2>&1 | Out-Null
        } catch { }
    }
    if (Test-Path $tmp) {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }

    Write-Host 'PASS'
    exit 0
}
catch {
    # Leave scratch dir on failure for inspection.
    Write-Host "FAIL: $_"
    Write-Host "Scratch left at: $tmp"
    exit 1
}
