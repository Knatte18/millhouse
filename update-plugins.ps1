# Update all plugins from the local marketplace, then set mill env vars.
# Run from the millhouse repo root.

$ManifestPath = Join-Path $PSScriptRoot ".claude-plugin\marketplace.json"
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$marketplace = $manifest.name

foreach ($p in $manifest.plugins) {
    claude plugin update "$($p.name)@$marketplace"
}

# Set env vars so mill scripts resolve to the installed version.
$mill = $manifest.plugins | Where-Object { $_.name -eq "mill" }
$target = Join-Path $env:USERPROFILE ".claude\plugins\cache\millhouse\mill\$($mill.version)"
[System.Environment]::SetEnvironmentVariable('CLAUDE_PLUGIN_ROOT', $target, 'User')
[System.Environment]::SetEnvironmentVariable('PYTHONPATH', "$target\scripts", 'User')
Write-Host "  -> CLAUDE_PLUGIN_ROOT=$target"
Write-Host "  -> PYTHONPATH=$target\scripts"

Write-Host ""
Write-Host "Done."
