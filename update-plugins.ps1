# Force-sync all plugins from the local source dir to the Claude Code plugin
# cache. `claude plugin update` is version-gated and skips when marketplace.json
# version is unchanged, so it cannot deploy in-place file edits without a
# version bump. We use robocopy directly to mirror the current source into the
# cache regardless of version. Run from the millhouse repo root.
# NOTE: This script sets User-level environment variables. When CC uses directory-source
# mode (marketplace.json relative source paths), CC sets Process-level CLAUDE_PLUGIN_ROOT
# that overrides this User-level setting; see ## Conventions worth carrying in CLAUDE.md.

$ManifestPath = Join-Path $PSScriptRoot ".claude-plugin\marketplace.json"
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$marketplace = $manifest.name
$cacheBase = Join-Path $env:USERPROFILE ".claude\plugins\cache\$marketplace"

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
