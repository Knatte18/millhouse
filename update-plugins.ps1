# Force-sync all plugins from the local source dir to the Claude Code plugin
# cache. `claude plugin update` is version-gated and skips when marketplace.json
# version is unchanged, so it cannot deploy in-place file edits without a
# version bump. We use robocopy directly to mirror the current source into the
# cache regardless of version. Run from the millhouse repo root.
# NOTE: This script sets User-level environment variables. When CC uses directory-source
# mode (marketplace.json relative source paths), CC sets Process-level CLAUDE_PLUGIN_ROOT
# that overrides this User-level setting; see ## Conventions worth carrying in CLAUDE.md.
#
# Before syncing, refreshes scribe@scribe (mill's declared dependency) when
# installed and warns if it is older than mill requires.
# After syncing, prints an uninstall hint for each <name>@millhouse install
# whose plugin is no longer in marketplace.json.

$ManifestPath = Join-Path $PSScriptRoot ".claude-plugin\marketplace.json"
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$marketplace = $manifest.name
$installedPath = Join-Path $env:USERPROFILE ".claude\plugins\installed_plugins.json"
$millManifestPath = Join-Path $PSScriptRoot "plugins\mill\.claude-plugin\plugin.json"
$cacheBase = Join-Path $env:USERPROFILE ".claude\plugins\cache\$marketplace"

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

    $lowest = $installed.plugins.'scribe@scribe' | ForEach-Object { [version]$_.version } | Sort-Object | Select-Object -First 1
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

foreach ($p in $manifest.plugins) {
    $name = $p.name
    $version = $p.version
    $sourceDir = Join-Path $PSScriptRoot "plugins\$name"
    $targetDir = Join-Path $cacheBase "$name\$version"

    if (-not (Test-Path $targetDir)) {
        Write-Host "Skipped (not installed): $name@$marketplace -- run 'claude plugin install $name@$marketplace' first."
        continue
    }

    # Mirror source -> target. Exclude .venv because uv creates it in the cache
    # at runtime; its .pyd and .exe files are often locked and cannot be
    # deleted by /MIR's purge step.
    robocopy $sourceDir $targetDir /MIR /XD ".venv" /NFL /NDL /NJH /NJS | Out-Null
    Write-Host "Force-synced: $name@$marketplace ($version)"

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

# Set env vars so mill scripts resolve to the installed version.
$mill = $manifest.plugins | Where-Object { $_.name -eq "mill" }
$target = Join-Path $cacheBase "mill\$($mill.version)"
[System.Environment]::SetEnvironmentVariable('CLAUDE_PLUGIN_ROOT', $target, 'User')
[System.Environment]::SetEnvironmentVariable('PYTHONPATH', "$target\scripts", 'User')
Write-Host "  -> CLAUDE_PLUGIN_ROOT=$target"
Write-Host "  -> PYTHONPATH=$target\scripts"

$codeguide = $manifest.plugins | Where-Object { $_.name -eq "codeguide" }
if ($codeguide) {
    $cgTarget = Join-Path $cacheBase "codeguide\$($codeguide.version)"
    [System.Environment]::SetEnvironmentVariable('CODEGUIDE_PLUGIN_ROOT', $cgTarget, 'User')
    Write-Host "  -> CODEGUIDE_PLUGIN_ROOT=$cgTarget"
}

Write-Host ""
Write-Host "Done."
