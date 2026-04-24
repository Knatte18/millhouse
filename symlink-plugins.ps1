# Link all millhouse plugins to source, bypassing the plugin cache.
# Uses Windows junctions (no admin required).
# Run from the millhouse repo root.

$SourceDir = Join-Path $PSScriptRoot "plugins"
$CacheDir = Join-Path $env:USERPROFILE ".claude\plugins\cache\millhouse"
$ManifestPath = Join-Path $PSScriptRoot ".claude-plugin\marketplace.json"

if (-not (Test-Path $CacheDir)) {
    Write-Host "Error: Plugin cache not found at $CacheDir"
    Write-Host "Run 'claude plugin marketplace add' and install plugins first."
    exit 1
}

if (-not (Test-Path $ManifestPath)) {
    Write-Host "Error: Marketplace manifest not found at $ManifestPath"
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

    # Check if already a junction
    if (Test-Path $target) {
        $item = Get-Item $target -Force
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            $currentTarget = $item.Target
            if ($currentTarget -eq $_.FullName) {
                Write-Host "Already linked: $name ($version)"
                return
            }
            # Junction points to wrong target — remove and re-create
            Write-Host "Repairing: $name ($version) (was -> $currentTarget)"
            cmd /c "rmdir `"$target`"" | Out-Null
        } else {
            # Backup existing cache
            $backup = "${target}.bak"
            if (Test-Path $backup) { Remove-Item $backup -Recurse -Force }
            Move-Item $target $backup
        }
    }

    # Create junction
    cmd /c "mklink /J `"$target`" `"$($_.FullName)`"" | Out-Null
    Write-Host "Linked: $name ($version)"
}

Write-Host ""
Write-Host "Done. Plugin edits are now live immediately."
