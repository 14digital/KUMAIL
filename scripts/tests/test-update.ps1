param([string]$UpdaterPath = (Join-Path $PSScriptRoot '../update-windows.ps1'))
$ErrorActionPreference = 'Stop'
. $UpdaterPath -LibraryOnly
$script:GitExe = (Get-Command git).Source
$original = Get-Location
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('mi-updater-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $scratch | Out-Null
$script:Passed = 0
function Assert-True { param($Value,[string]$Message) if (-not $Value) { throw "FAIL: $Message" }; $script:Passed++; Write-Host "PASS: $Message" }
function Save-Text {
    param([string]$Name,[string]$Text)
    $full = Join-Path (Get-Location) $Name
    New-Item -ItemType Directory -Path (Split-Path $full -Parent) -Force | Out-Null
    [IO.File]::WriteAllText($full,$Text,(New-Object Text.UTF8Encoding($false)))
}
function Git { param([string[]]$A) Invoke-Git -Arguments $A }
function New-Installation {
    param([string]$Name)
    $path = Join-Path $scratch $Name
    New-Item -ItemType Directory -Path $path | Out-Null
    Set-Location $repo
    Git @('archive','--format=zip',"--output=$scratch/$Name.zip",$baseline)
    [IO.Compression.ZipFile]::ExtractToDirectory("$scratch/$Name.zip",$path)
    Set-Location $path
    Save-Text '.env' "APP_TOKEN=fixture-private-value`n"
    Save-Text 'state/private-note.txt' 'private-state'
    Save-Text 'Update My Intelligence.cmd' "known-new-launcher`n"
    Save-Text 'scripts/update-windows.ps1' "known-new-updater`n"
    Git @('init','-b','main')
    Git @('config','core.autocrlf','false')
    Git @('config','core.filemode','false')
    Git @('remote','add','origin',$repo)
    Git @('fetch','origin','refs/heads/main:refs/remotes/origin/main')
    New-Item -ItemType File '.git/mi-bootstrap-pending' | Out-Null
    return $path
}
try {
    $repo = Join-Path $scratch 'release-repository'
    New-Item -ItemType Directory -Path $repo | Out-Null
    Set-Location $repo
    Git @('init','-b','main')
    Git @('config','user.name','Updater fixture')
    Git @('config','user.email','fixture@example.invalid')
    Git @('config','core.autocrlf','false')
    Save-Text '.gitignore' ".env`nstate/`n"
    Save-Text 'compose.yaml' "services: {}`n"
    Save-Text 'backend/intelligence/api.py' "version = 1`n"
    Save-Text 'web/app/page.tsx' "version = 1;`n"
    Save-Text 'README.md' "Original release`n"
    Git @('add','.')
    Git @('commit','-m','baseline')
    $baseline = ("$(Invoke-Git -Arguments @('rev-parse','HEAD') -Capture)").Trim()
    Save-Text 'backend/intelligence/api.py' "version = 2`n"
    Save-Text 'web/app/page.tsx' "version = 2;`n"
    Save-Text 'README.md' "New release`n"
    Save-Text 'config/publisher-feeds.json' "[]`n"
    Save-Text 'Update My Intelligence.cmd' "known-new-launcher`n"
    Save-Text 'scripts/update-windows.ps1' "known-new-updater`n"
    Git @('add','.')
    Git @('commit','-m','target')
    $target = ("$(Invoke-Git -Arguments @('rev-parse','HEAD') -Capture)").Trim()

    $install = New-Installation -Name 'zip-install'
    Save-Text 'config/publisher-feeds.json' "[]`n"
    $matched = Initialize-ZipCheckout -Target $target
    Assert-True ($matched -eq $baseline) 'ZIP migration identifies the exact original release'
    Assert-True (@(Invoke-Git -Arguments @('status','--porcelain','--untracked-files=no') -Capture).Count -eq 0) 'migration leaves tracked source clean'
    Git @('merge','--ff-only','--no-edit',$target)
    Assert-True ((Get-Content 'backend/intelligence/api.py' -Raw) -eq "version = 2`n") 'fast-forward updates application source'
    Assert-True ((Get-Content '.env' -Raw) -eq "APP_TOKEN=fixture-private-value`n") 'private environment file is unchanged'
    Assert-True ((Get-Content 'state/private-note.txt' -Raw) -eq 'private-state') 'private local data is unchanged'
    Assert-True ((Get-Content 'Update My Intelligence.cmd' -Raw) -eq "known-new-launcher`n") 'one-file launcher survives its own installation'
    $backups = @(Get-ChildItem '.git/mi-bootstrap-backup' -Recurse -File)
    Assert-True ($backups.Count -eq 3) 'identical pre-existing new files are preserved in metadata backups'
    Git @('merge','--ff-only','--no-edit',$target)
    Assert-True (@(Invoke-Git -Arguments @('status','--porcelain','--untracked-files=no') -Capture).Count -eq 0) 'repeated fast-forward is idempotent'

    $edited = New-Installation -Name 'edited-install'
    Save-Text 'backend/intelligence/api.py' "my local source edit`n"
    $stopped = $false
    try { Initialize-ZipCheckout -Target $target | Out-Null } catch { $stopped = $_.Exception.Message -like '*does not match*' }
    Assert-True $stopped 'edited source stops ZIP migration'
    Assert-True ((Get-Content 'backend/intelligence/api.py' -Raw) -eq "my local source edit`n") 'edited source is not overwritten'
    Assert-True ((Get-Content '.env' -Raw) -eq "APP_TOKEN=fixture-private-value`n") 'blocked migration preserves keys'

    $collision = New-Installation -Name 'collision-install'
    Save-Text 'config/publisher-feeds.json' "my local configuration`n"
    $stopped = $false
    try { Initialize-ZipCheckout -Target $target | Out-Null } catch { $stopped = $_.Exception.Message -like '*would be overwritten*' }
    Assert-True $stopped 'conflicting untracked file stops migration'
    Assert-True ((Get-Content 'config/publisher-feeds.json' -Raw) -eq "my local configuration`n") 'conflicting untracked file is unchanged'

    $crlf = New-Installation -Name 'crlf-install'
    Save-Text 'README.md' "Original release`r`n"
    Assert-True ((Get-MatchingRelease -Target $target) -eq $baseline) 'ordinary Windows line endings match the release'
    Assert-True ((@(Get-BuildTargets -Paths @('README.md','scripts/import_publishers.py'))).Count -eq 0) 'documentation and host-only script updates skip image builds'
    Assert-True ((@(Get-BuildTargets -Paths @('backend/intelligence/api.py')) -join ',') -eq 'api') 'backend changes build one shared image'
    Assert-True ((@(Get-BuildTargets -Paths @('web/app/page.tsx')) -join ',') -eq 'web') 'frontend changes build only the dashboard'
    Assert-True ((@(Get-BuildTargets -Paths @('compose.yaml')) -join ',') -eq 'api,web') 'Compose changes build both image targets'
    Assert-True ((@(Get-BuildTargets -Paths @('backend/tests/test_core.py'))).Count -eq 0) 'test-only changes skip production image builds'
    foreach ($unsafe in @('.env','state/private.sqlite','.env.local','web/.env.local')) {
        $stopped = $false
        try { Assert-SafeTree -Tree @{$unsafe='fixture'} } catch { $stopped=$true }
        Assert-True $stopped "protected release path is rejected: $unsafe"
    }
    Assert-SafeTree -Tree @{'.env.example'='fixture';'backend/intelligence/api.py'='fixture'}
    Assert-True $true 'environment template remains permitted'
    # Exercise deployment orchestration with real Git and controlled Docker failures.
    # These mocks never run against the developer's actual containers.
    $script:Calls = @(); $script:FailBuild = $true; $script:ReadyChecks = 0
    function Test-ImagePresent { param([string]$Name) return $true }
    function Invoke-Compose {
        param([string[]]$Arguments)
        $script:Calls += ($Arguments -join ' ')
        if ($script:FailBuild -and $Arguments[0] -eq 'build') { throw 'Controlled build failure' }
    }
    function Wait-ForApp { $script:ReadyChecks++ }
    function Open-Dashboard { }
    $retry = New-Installation -Name 'retry-install'
    Initialize-ZipCheckout -Target $target | Out-Null
    $stopped = $false
    try { Complete-Update -Before $baseline -Target $target } catch { $stopped = $_.Exception.Message -eq 'Controlled build failure' }
    Assert-True $stopped 'controlled image-build failure stops deployment'
    $state = Get-Content '.git/mi-update-state.json' -Raw | ConvertFrom-Json
    Assert-True ($state.last_applied_commit -eq $baseline) 'failed build retains the last deployed revision'
    Assert-True (($script:Calls -join ';') -eq 'build api web') 'failed builds never restart running services'
    $script:Calls = @(); $script:FailBuild = $false
    Complete-Update -Before $target -Target $target
    Assert-True (($script:Calls -join ';') -eq 'build api web;up -d --no-build') 'retry rebuilds pending changes even when Git is already updated'
    Assert-True ($script:ReadyChecks -eq 1) 'successful update checks authenticated application readiness'
    $state = Get-Content '.git/mi-update-state.json' -Raw | ConvertFrom-Json
    Assert-True ($state.last_applied_commit -eq $target) 'deployed revision advances only after readiness'
    $script:Calls = @()
    Complete-Update -Before $target -Target $target
    Assert-True (($script:Calls -join ';') -eq 'up -d --no-build') 'up-to-date application skips rebuilding images'
    Save-Text 'README.md' "local edited documentation`n"
    $script:Calls = @(); $stopped = $false
    try { Complete-Update -Before $target -Target $target } catch { $stopped = $_.Exception.Message -like '*Local source edits*' }
    Assert-True $stopped 'Git checkout with local edits is not updated'
    Assert-True ($script:Calls.Count -eq 0) 'local edits stop before any container operation'
    Git @('restore','--','README.md')
    Save-Text 'README.md' "local-only commit`n"
    Git @('add','README.md')
    Git @('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','local-only')
    $localHead = ("$(Invoke-Git -Arguments @('rev-parse','HEAD') -Capture)").Trim()
    $stopped = $false
    try { Complete-Update -Before $localHead -Target $target } catch { $stopped=$true }
    Assert-True $stopped 'local-ahead branch requires review instead of an implicit reset'
    Assert-True ((Get-Content '.env' -Raw) -eq "APP_TOKEN=fixture-private-value`n") 'failure and retry cycles preserve environment values'
    # Run the complete entry point with GitHub fetch redirected to the fixture.
    # Docker availability/readiness are controlled; all Git file operations are real.
    $entry = New-Installation -Name 'entrypoint-install'
    Remove-Item '.git' -Recurse -Force
    $script:RealGit = $script:GitExe
    $script:OriginalInvokeGit = (Get-Command Invoke-Git).ScriptBlock
    $script:TestRemote = $repo
    function Find-Git { return $script:RealGit }
    function docker { $global:LASTEXITCODE = 0 }
    function Invoke-Git {
        param([string[]]$Arguments,[switch]$Capture)
        if ($Arguments[0] -eq 'fetch') { $Arguments[1] = $script:TestRemote }
        & $script:OriginalInvokeGit -Arguments $Arguments -Capture:$Capture
    }
    $script:Calls = @()
    Invoke-Update -Root $entry
    Assert-True (("$(Invoke-Git -Arguments @('rev-parse','HEAD') -Capture)").Trim() -eq $target) 'full updater entry point migrates the existing ZIP folder'
    Assert-True (($script:Calls -join ';') -eq 'build api web;up -d --no-build') 'full entry point applies the selective build plan'
    Assert-True ((Get-Content '.env' -Raw) -eq "APP_TOKEN=fixture-private-value`n") 'full entry point keeps the original environment file'
    $script:Calls = @()
    Invoke-Update -Root $entry
    Assert-True (($script:Calls -join ';') -eq 'up -d --no-build') 'full entry point supports a second one-click update'
    Write-Host "ALL $script:Passed UPDATER CHECKS PASSED"
} finally {
    Set-Location $original
    Remove-Item -LiteralPath $scratch -Recurse -Force
}
