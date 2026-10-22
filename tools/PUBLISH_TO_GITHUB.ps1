param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')]
    [string]$Repository
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot
$existing = (& git remote get-url origin 2>$null)
$url = "https://github.com/$Repository.git"
if ($existing -and $existing.Trim() -ne $url) {
    throw "Existing origin points to $existing, expected $url. Review remote before proceeding."
}
if (-not $existing) { & git remote add origin $url }
$branch = (& git branch --show-current).Trim()
if ($branch -ne 'main') { throw "Expected local branch main; found $branch" }
Write-Host "Repository: $Repository" -ForegroundColor Cyan
Write-Host 'Pushing imported snapshots and current release as-is. No rewritten dates or fake teammate commits.'
& git push -u origin main
if ($LASTEXITCODE -ne 0) {
    throw "Push failed. Ensure the private repository is empty and you are authenticated with GitHub."
}
Write-Host 'Push completed.' -ForegroundColor Green
