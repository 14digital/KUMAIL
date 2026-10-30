param([string]$Repository = (Join-Path $PSScriptRoot '../..'))
$ErrorActionPreference = 'Stop'
$Repository = (Resolve-Path -LiteralPath $Repository).Path
. (Join-Path $Repository 'scripts/update-windows.ps1') -LibraryOnly
$script:GitExe = (Get-Command git).Source
$original = Get-Location
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('mi-release-upgrade-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $scratch | Out-Null
try {
    Set-Location $Repository
    $first = ("$(Invoke-Git -Arguments @('rev-list','--max-parents=0','HEAD') -Capture)").Trim()
    $current = ("$(Invoke-Git -Arguments @('rev-parse','HEAD') -Capture)").Trim()
    $archive = Join-Path $scratch 'original-release.zip'
    Invoke-Git -Arguments @('archive','--format=zip',"--output=$archive",$first)
    $installed = Join-Path $scratch 'original-windows-install'
    [IO.Compression.ZipFile]::ExtractToDirectory($archive,$installed)
    Copy-Item -LiteralPath (Join-Path $Repository 'Update My Intelligence.cmd') -Destination $installed
    [IO.File]::WriteAllText((Join-Path $installed '.env'),"APP_TOKEN=private-fixture-only`n")
    Set-Location $installed
    Invoke-Git -Arguments @('init','-b','main')
    Invoke-Git -Arguments @('config','core.autocrlf','true')
    Invoke-Git -Arguments @('config','core.filemode','false')
    Invoke-Git -Arguments @('fetch',$Repository,'HEAD:refs/remotes/origin/main')
    New-Item -ItemType File '.git/mi-bootstrap-pending' | Out-Null
    $matched = Initialize-ZipCheckout -Target $current
    if ($matched -ne $first) { throw 'Original released ZIP was not recognised.' }
    Invoke-Git -Arguments @('merge','--ff-only','--no-edit',$current)
    if (@(Invoke-Git -Arguments @('status','--porcelain','--untracked-files=no') -Capture).Count -ne 0) { throw 'Migration left source edits.' }
    if ((Get-Content '.env' -Raw) -ne "APP_TOKEN=private-fixture-only`n") { throw 'Private fixture was changed.' }
    if (-not (Get-Content 'compose.yaml' -Raw).Contains('my-intelligence-backend:local')) { throw 'Shared-image configuration was not applied.' }
    Write-Host 'PASS: actual first app release upgrades to current HEAD, preserving the environment and leaving clean Git source.'
} finally {
    Set-Location $original
    Remove-Item -LiteralPath $scratch -Recurse -Force
}
