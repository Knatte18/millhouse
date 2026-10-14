# Deploy all plugins from this source repo to the container's deploy directory,
# which is what Claude Code actually reads. Run from the millhouse repo root.
#
# Why a separate deploy directory rather than the plugin cache: the `millhouse`
# marketplace is a directory source, and Claude Code reads a directory-sourced
# plugin in place from <marketplace-dir>/<plugin source path> -- it never reads
# the copy under ~/.claude/plugins/cache/. Pointing the marketplace at the
# source repo therefore makes every session run the live dev tree, mid-edit,
# and makes whatever this script deploys dead weight. Pointing it at the deploy
# directory instead restores the intended model: you edit the repo, you run
# this script, and only then does the change reach running sessions.
#
# `claude plugin update` cannot do this job: it is version-gated and skips when
# marketplace.json's version is unchanged, so it cannot deploy in-place file
# edits without a version bump. robocopy mirrors regardless of version.
#
# Before deploying, refreshes scribe@scribe (mill's declared dependency) when
# installed and warns if it is older than mill requires.
# After deploying, prints an uninstall hint for each <name>@millhouse install
# whose plugin is no longer in marketplace.json, and warns if the marketplace
# is still registered against anything other than the deploy directory.

$ManifestPath = Join-Path $PSScriptRoot ".claude-plugin\marketplace.json"
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$marketplace = $manifest.name
$installedPath = Join-Path $env:USERPROFILE ".claude\plugins\installed_plugins.json"
$millManifestPath = Join-Path $PSScriptRoot "plugins\mill\.claude-plugin\plugin.json"

# The repo lives at <container>\wts\<slug>; the deploy directory is a sibling of
# wts\, wiki\ and portals\, so it never sits inside a git checkout.
$container = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$deployRoot = Join-Path $container "deploy"

# Refresh scribe@scribe (mill's dependency) and check it meets mill's minimum.
$installed = $null
if (Test-Path $installedPath) {
    $installed = Get-Content $installedPath -Raw | ConvertFrom-Json
}
$scribeInstalled = $installed -and ($installed.plugins.PSObject.Properties.Name -contains "scribe@scribe")

if ($scribeInstalled) {
    foreach ($refreshArgs in @(@("marketplace", "update", "scribe"), @("update", "scribe@scribe"))) {
        $refreshCommand = "claude plugin $($refreshArgs -join ' ')"
        try {
            & claude plugin @refreshArgs
            if ($LASTEXITCODE -ne 0) {
                Write-Host "WARNING: '$refreshCommand' failed -- continuing"
            }
        } catch {
            Write-Host "WARNING: '$refreshCommand' failed -- continuing"
        }
    }

    # A directory-sourced install records its version with a '-<hash>' suffix; strip it before parsing.
    $lowest = $installed.plugins.'scribe@scribe' | ForEach-Object { [version]($_.version -replace '[-+].*$', '') } | Sort-Object | Select-Object -First 1
    $millManifest = Get-Content $millManifestPath -Raw | ConvertFrom-Json
    $scribeDependency = $millManifest.dependencies | Where-Object { $_.name -eq "scribe" -and $_.marketplace -eq "scribe" } | Select-Object -First 1
    if ($lowest -and $scribeDependency -and $scribeDependency.version) {
        $minimum = [version]($scribeDependency.version -replace '^(\^|~|>=|=)', '')
        if ($lowest -lt $minimum) {
            Write-Host "WARNING: scribe@scribe is $lowest, mill needs $minimum -- run 'claude plugin marketplace update scribe' and 'claude plugin update scribe@scribe'."
        }
    }
} else {
    Write-Host "scribe@scribe is not installed -- mill fails to load without it. Add and install it: '/plugin marketplace add Knatte18/scribe', then '/plugin install scribe@scribe'."
}

# The marketplace manifest is part of what gets deployed: the deploy directory
# IS the marketplace once it is registered, so it needs its own copy.
$manifestTarget = Join-Path $deployRoot ".claude-plugin"
robocopy (Join-Path $PSScriptRoot ".claude-plugin") $manifestTarget /MIR /NFL /NDL /NJH /NJS | Out-Null
Write-Host "Deployed: .claude-plugin\marketplace.json"

foreach ($p in $manifest.plugins) {
    $name = $p.name
    $sourceDir = Join-Path $PSScriptRoot "plugins\$name"
    $targetDir = Join-Path $deployRoot "plugins\$name"

    # Mirror source -> target. Exclude .venv because uv creates it in the deploy
    # tree at runtime; its .pyd and .exe files are often locked and cannot be
    # deleted by /MIR's purge step.
    robocopy $sourceDir $targetDir /MIR /XD ".venv" /NFL /NDL /NJH /NJS | Out-Null
    Write-Host "Deployed: $name@$marketplace ($($p.version))"

    # Create/update the venv if the plugin has a pyproject.toml.
    $pyproject = Join-Path $targetDir "pyproject.toml"
    if (Test-Path $pyproject) {
        Write-Host "  -> Running uv sync for $name..."
        uv sync --project $targetDir --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  WARNING: uv sync failed for $name (exit $LASTEXITCODE)"
        }
    }
}

# Point out installs whose plugin no longer exists in this marketplace.
if ($installed) {
    $currentNames = $manifest.plugins | ForEach-Object { $_.name }
    foreach ($key in $installed.plugins.PSObject.Properties.Name) {
        $name, $keyMarketplace = $key -split '@', 2
        if ($keyMarketplace -eq $marketplace -and $currentNames -notcontains $name) {
            Write-Host "Orphaned: $key is no longer in this marketplace -- run 'claude plugin uninstall $key'."
        }
    }
}

# Set env vars so mill scripts resolve to the deployed copy.
$millTarget = Join-Path $deployRoot "plugins\mill"
[System.Environment]::SetEnvironmentVariable('CLAUDE_PLUGIN_ROOT', $millTarget, 'User')
[System.Environment]::SetEnvironmentVariable('PYTHONPATH', "$millTarget\scripts", 'User')
Write-Host "  -> CLAUDE_PLUGIN_ROOT=$millTarget"
Write-Host "  -> PYTHONPATH=$millTarget\scripts"

$codeguide = $manifest.plugins | Where-Object { $_.name -eq "codeguide" }
if ($codeguide) {
    $cgTarget = Join-Path $deployRoot "plugins\codeguide"
    [System.Environment]::SetEnvironmentVariable('CODEGUIDE_PLUGIN_ROOT', $cgTarget, 'User')
    Write-Host "  -> CODEGUIDE_PLUGIN_ROOT=$cgTarget"
}

# MILL_PYTHON lives in ~/.claude/settings.json, not in the registry -- that is
# where mill-setup Phase 4.8 writes it and where a session reads it from. Let
# the deployed interpreter rewrite it, so the file keeps json.dumps formatting
# rather than PowerShell's ConvertTo-Json reflow.
$millPython = Join-Path $millTarget ".venv\Scripts\python.exe"
if (Test-Path $millPython) {
    & $millPython -c @"
import json
from pathlib import Path

mill_python = r'$millPython'
settings_path = Path.home() / '.claude' / 'settings.json'

data = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
env_block = data.setdefault('env', {})
if env_block.get('MILL_PYTHON') == mill_python:
    print(f'  -> MILL_PYTHON already correct: {mill_python}')
else:
    env_block['MILL_PYTHON'] = mill_python
    settings_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(f'  -> MILL_PYTHON set: {mill_python}')
"@
} else {
    Write-Host "  WARNING: $millPython is missing -- MILL_PYTHON left unchanged."
}

# Deploying is pointless if the marketplace still points somewhere else: Claude
# Code would keep reading that other directory and ignore everything above.
$knownPath = Join-Path $env:USERPROFILE ".claude\plugins\known_marketplaces.json"
if (Test-Path $knownPath) {
    $known = Get-Content $knownPath -Raw | ConvertFrom-Json
    $entry = $known.PSObject.Properties | Where-Object { $_.Name -eq $marketplace } | Select-Object -First 1
    if ($entry) {
        $registered = $entry.Value.installLocation
        if ($registered -and ((Resolve-Path $registered -ErrorAction SilentlyContinue).Path -ne $deployRoot)) {
            Write-Host ""
            Write-Host "WARNING: marketplace '$marketplace' is registered against $registered, not $deployRoot."
            Write-Host "         Sessions read that directory, so this deploy has no effect. Re-register once:"
            Write-Host "           claude plugin marketplace remove $marketplace"
            Write-Host "           claude plugin marketplace add $deployRoot"
            Write-Host "         then reinstall each plugin: $(($manifest.plugins | ForEach-Object { "$($_.name)@$marketplace" }) -join ', ')"
        }
    }
}

Write-Host ""
Write-Host "Done."
