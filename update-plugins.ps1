# Copy plugins from source into the Claude Code plugin cache.
# Skips plugins that are not installed. Safe to run repeatedly.
# Run from the millhouse repo root.

$SourceDir = Join-Path $PSScriptRoot "plugins"
$CacheDir = Join-Path $env:USERPROFILE ".claude\plugins\cache\millhouse"
$ManifestPath = Join-Path $PSScriptRoot ".claude-plugin\marketplace.json"

if (-not (Test-Path $CacheDir)) {
    Write-Host "Error: Plugin cache not found at $CacheDir"
    Write-Host "Run 'claude plugin marketplace add' and install plugins first."
    exit 1
}

$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$versions = @{}
foreach ($p in $manifest.plugins) { $versions[$p.name] = $p.version }

Get-ChildItem -Path $SourceDir -Directory | ForEach-Object {
    $name = $_.Name
    $version = $versions[$name]

    if (-not $version) {
        Write-Host "Skipped (not in marketplace.json): $name"
        return
    }

    $pluginCacheDir = Join-Path $CacheDir $name
    $target = Join-Path $pluginCacheDir $version

    if (-not (Test-Path $pluginCacheDir)) {
        Write-Host "Skipped (not installed): $name"
        return
    }

    # If target is a junction from a previous symlink-plugins run, remove it
    # before copying — Copy-Item cannot write into a junction safely.
    if (Test-Path $target) {
        $item = Get-Item $target -Force
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            cmd /c "rmdir `"$target`"" | Out-Null
            Write-Host "Removed old junction: $name ($version)"
        }
    }

    # Remove existing target dir before copy — Copy-Item -Recurse otherwise
    # nests the source dir as a subdirectory instead of replacing contents.
    if (Test-Path $target) {
        Remove-Item $target -Recurse -Force
    }
    Copy-Item -Path $_.FullName -Destination $target -Recurse -Force
    Write-Host "Updated: $name ($version)"

    if ($name -eq "mill") {
        [System.Environment]::SetEnvironmentVariable('CLAUDE_PLUGIN_ROOT', $target, 'User')
        [System.Environment]::SetEnvironmentVariable('PYTHONPATH', "$target\scripts", 'User')
        Write-Host "  -> CLAUDE_PLUGIN_ROOT=$target"
        Write-Host "  -> PYTHONPATH=$target\scripts"
    }
}

Write-Host ""
Write-Host "Done."
