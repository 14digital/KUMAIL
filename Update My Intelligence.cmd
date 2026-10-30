@echo off
setlocal
set "MI_UPDATER_ROOT=%~dp0"
set "MI_UPDATER_FILE=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$raw = [IO.File]::ReadAllText($env:MI_UPDATER_FILE); $marker = '# BEGIN POWERSHELL'; & ([scriptblock]::Create($raw.Substring($raw.LastIndexOf($marker) + $marker.Length))) -RootDirectory $env:MI_UPDATER_ROOT"
if errorlevel 1 (
  echo Update stopped. Read the message above.
  pause
  exit /b 1
)
pause
exit /b 0
# BEGIN POWERSHELL
param([string]$RootDirectory, [switch]$LibraryOnly)
$ErrorActionPreference = 'Stop'
$script:GitExe = $null
$script:BootstrapFiles = @('Update My Intelligence.cmd', 'Update KUMAIL.cmd', 'scripts/update-windows.ps1')

function Find-Git {
    $command = Get-Command git -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($candidate in @("$env:ProgramFiles\Git\cmd\git.exe", "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe")) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}

function Invoke-Git {
    param([string[]]$Arguments, [switch]$Capture)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($Capture) { $output = @(& $script:GitExe @Arguments 2>&1) }
        else { & $script:GitExe @Arguments | Out-Host }
        $result = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($result -ne 0) {
        if ($Capture) { $output | ForEach-Object { Write-Host $_ } }
        throw "Git command failed: $($Arguments[0]). Your running app and data have not been removed."
    }
    if ($Capture) { return $output }
}

function Get-Tree {
    param([string]$Commit)
    $tree = @{}
    foreach ($line in @(Invoke-Git -Arguments @('ls-tree','-r',$Commit) -Capture)) {
        if ("$line" -notmatch '^([0-9]+) blob ([0-9a-f]+)\t(.+)$') { throw 'Unsupported Git tree entry; update stopped.' }
        $name = $Matches[3]
        # Git quotes unusual paths. All application release paths are ordinary UTF-8 paths.
        if ($name.StartsWith('"')) { throw 'Quoted Git paths require a manual update.' }
        if ($Matches[1] -notin @('100644','100755')) { throw 'Symlinks and submodules require a manual update.' }
        $tree[$name] = $Matches[2]
    }
    return $tree
}

function Assert-SafeTree {
    param([hashtable]$Tree)
    foreach ($name in $Tree.Keys) {
        if ($name -match '(^|/)(\.git|state|node_modules|\.venv)(/|$)' -or
            $name -match '(^|/)\.env($|\.)' -and $name -ne '.env.example' -or
            $name -in @('publisher-import-results.json','docs/MASTER_SPEC.md') -or
            $name -match '(^|/)\.\.(/|$)' -or $name.Contains(':') -or $name.Contains('\')) {
            throw "Release contains a protected or unsafe path: $name"
        }
    }
}

function Get-BlobHash {
    param([byte[]]$Bytes)
    $prefix = [Text.Encoding]::UTF8.GetBytes("blob $($Bytes.Length)`0")
    $buffer = New-Object byte[] ($prefix.Length + $Bytes.Length)
    [Array]::Copy($prefix,0,$buffer,0,$prefix.Length)
    [Array]::Copy($Bytes,0,$buffer,$prefix.Length,$Bytes.Length)
    $sha = [Security.Cryptography.SHA1]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($buffer))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Get-LocalHashes {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return @() }
    $item = Get-Item -LiteralPath $Path -Force
    $root = (Get-Location).Path
    $check = $item
    while ($check -and $check.FullName.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)) {
        if ($check.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "A linked source path needs manual review: $Path" }
        if ($check -is [IO.FileInfo]) { $check = $check.Directory } else { $check = $check.Parent }
    }
    # .NET relative paths use process CWD, which can differ from PowerShell's location.
    $bytes = [IO.File]::ReadAllBytes($item.FullName)
    $hashes = @(Get-BlobHash -Bytes $bytes)
    # Git for Windows treats ordinary CRLF/LF differences as text checkout details.
    $utf8 = New-Object Text.UTF8Encoding($false,$true)
    try {
        $text = $utf8.GetString($bytes)
        if (-not $text.Contains([string][char]0)) {
            $hashes += Get-BlobHash -Bytes ([Text.Encoding]::UTF8.GetBytes($text.Replace("`r`n","`n")))
        }
    } catch [Text.DecoderFallbackException] { }
    return $hashes
}

function Get-MatchingRelease {
    param([string]$Target)
    $cache = @{}
    foreach ($commit in @(Invoke-Git -Arguments @('log','--format=%H','--max-count=200',$Target) -Capture)) {
        $tree = Get-Tree -Commit "$commit"
        Assert-SafeTree -Tree $tree
        $matchesRelease = $true
        foreach ($name in $tree.Keys) {
            if ($name -in $script:BootstrapFiles) { continue }
            if (-not $cache.ContainsKey($name)) { $cache[$name] = @(Get-LocalHashes -Path $name) }
            if ($tree[$name] -notin $cache[$name]) { $matchesRelease = $false; break }
        }
        if ($matchesRelease -and $tree.ContainsKey('compose.yaml') -and $tree.ContainsKey('backend/intelligence/api.py')) {
            return "$commit"
        }
    }
    throw 'This ZIP does not match a published release, or source files were edited. No source files were replaced. Keep this folder and its .env; ask for help reviewing the differences.'
}

function Initialize-ZipCheckout {
    param([string]$Target)
    $baseline = Get-MatchingRelease -Target $Target
    $baseTree = Get-Tree -Commit $baseline
    $targetTree = Get-Tree -Commit $Target
    Assert-SafeTree -Tree $targetTree
    $adopt = @()
    foreach ($name in $targetTree.Keys) {
        if (($name -notin $baseTree.Keys -or $name -in $script:BootstrapFiles) -and (Test-Path -LiteralPath $name)) {
            if ($targetTree[$name] -notin @(Get-LocalHashes -Path $name)) {
                throw "A local file would be overwritten: $name. Update stopped before replacing files."
            }
            $adopt += $name
        }
    }
    # Attach metadata to the exact installed release, without resetting the working tree.
    Invoke-Git -Arguments @('read-tree',$baseline)
    Invoke-Git -Arguments @('update-ref','refs/heads/main',$baseline)
    $backup = Join-Path '.git' ('mi-bootstrap-backup/' + [guid]::NewGuid().ToString('N'))
    foreach ($name in $adopt) {
        $destination = Join-Path $backup $name
        New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $name -Destination $destination
        if ($baseTree.ContainsKey($name)) {
            # Only known installer files, checked against the target above, can reach this branch.
            Invoke-Git -Arguments @('restore','--source',$baseline,'--worktree','--',$name)
        } else {
            Remove-Item -LiteralPath $name
        }
    }
    Remove-Item -LiteralPath '.git/mi-bootstrap-pending' -ErrorAction SilentlyContinue
    return $baseline
}

function Get-BuildTargets {
    param([string[]]$Paths)
    $backend = $false; $web = $false
    foreach ($path in $Paths) {
        if ($path -eq 'compose.yaml') { $backend = $true; $web = $true }
        if ($path -match '^backend/(?!tests/)' -or $path -in @('Dockerfile','pyproject.toml','uv.lock','.dockerignore')) { $backend = $true }
        if ($path -match '^web/') { $web = $true }
    }
    $targets = @()
    if ($backend) { $targets += 'api' }
    if ($web) { $targets += 'web' }
    return $targets
}

function Invoke-Compose {
    param([string[]]$Arguments)
    & docker compose @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed: $($Arguments[0]). No data volumes were deleted. Fix the error and run this updater again." }
}

function Wait-ForApp {
    $probe = "import os,json,urllib.request; c=urllib.request.build_opener(urllib.request.ProxyHandler({})); r=urllib.request.Request('http://web:3000/api/dashboard',headers={'Authorization':'Bearer '+os.environ['APP_TOKEN']}); d=json.load(c.open(r,timeout=5)); assert 'integrations' in d"
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-WebRequest 'http://localhost:3000' -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                # The key is read inside the container, never printed or passed on the host command line.
                $previous = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
                try { & docker compose exec -T api python -c $probe *> $null; $probeResult = $LASTEXITCODE }
                finally { $ErrorActionPreference = $previous }
                if ($probeResult -eq 0) { return }
            }
        } catch { }
        Start-Sleep -Seconds 2
    }
    throw 'Dashboard/API readiness failed. Your files and data remain in place. Check Docker Desktop or run docker compose logs, then retry the updater.'
}

function Test-ImagePresent {
    param([string]$Name)
    $previous = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & docker image inspect $Name *> $null; $present = $LASTEXITCODE -eq 0 }
    finally { $ErrorActionPreference = $previous }
    return $present
}

function Open-Dashboard { Start-Process 'http://localhost:3000' }

function Complete-Update {
    param([string]$Before, [string]$Target)
    $dirty = @(Invoke-Git -Arguments @('status','--porcelain','--untracked-files=no') -Capture)
    if ($dirty.Count -gt 0) { throw 'Local source edits or staged changes were found. Update stopped; no edits were overwritten. Commit or review them before updating.' }
    # Refuse local-ahead/diverged branches; do not deploy unpushed local commits.
    Invoke-Git -Arguments @('merge-base','--is-ancestor',$before,$target)
    $statePath = '.git/mi-update-state.json'
    $applied = $before
    if (Test-Path $statePath) {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if ($state.last_applied_commit) { $applied = [string]$state.last_applied_commit }
    } else {
        @{last_applied_commit=$before} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    }
    Invoke-Git -Arguments @('merge','--ff-only','--no-edit',$target)
    $paths = @(Invoke-Git -Arguments @('diff','--name-only',$applied,$target) -Capture)
    $targets = @(Get-BuildTargets -Paths $paths)
    # First migration to shared images must build both even if code itself is unchanged.
    foreach ($image in @(@('api','my-intelligence-backend:local'),@('web','my-intelligence-dashboard:local'))) {
        $present = Test-ImagePresent -Name $image[1]
        if (-not $present -and $image[0] -notin $targets) { $targets += $image[0] }
    }
    if ($targets.Count -gt 0) {
        Write-Host ('Building changed components: ' + ($targets -join ', ') + '. The running app stays up until builds finish.')
        Invoke-Compose -Arguments (@('build') + $targets)
    } else { Write-Host 'No application image rebuild is needed.' }
    # Same directory/project and existing named volume. Never down -v, reset, clean or stash.
    Invoke-Compose -Arguments @('up','-d','--no-build')
    Wait-ForApp
    @{last_applied_commit=$target;ready_at=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    Write-Host 'Update complete. Your saved keys and data remain in place.'
    Open-Dashboard
}

function Invoke-Update {
    param([string]$Root)
    if (-not $Root) { throw 'Open this updater from your existing My Intelligence app folder.' }
    Set-Location -LiteralPath $Root
    if (-not (Test-Path 'compose.yaml') -or -not (Test-Path 'backend/intelligence/api.py')) {
        throw 'Place Update My Intelligence.cmd inside the existing KUMAIL-main app folder, beside Start My Intelligence.cmd.'
    }
    if (-not (Test-Path '.env')) { throw 'No .env was found. Use the existing app folder containing your saved keys, not a new Downloads folder.' }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker Desktop is required.' }
    $previous = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & docker info *> $null; $dockerReady = $LASTEXITCODE }
    finally { $ErrorActionPreference = $previous }
    if ($dockerReady -ne 0) { throw 'Start Docker Desktop and wait for Engine running, then retry.' }
    $script:GitExe = Find-Git
    if (-not $script:GitExe) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw 'Install Git for Windows once from https://git-scm.com/download/win, then run this updater again.'
        }
        Write-Host 'Installing Git for Windows once using Windows Package Manager. Windows may ask for permission.'
        & winget install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements --silent | Out-Host
        $script:GitExe = Find-Git
        if (-not $script:GitExe) { throw 'Git installation did not finish. Install Git for Windows, then retry.' }
    }
    if (-not (Test-Path '.git')) {
        Invoke-Git -Arguments @('init','-b','main')
        Invoke-Git -Arguments @('config','core.autocrlf','true')
        Invoke-Git -Arguments @('config','core.filemode','false')
        Invoke-Git -Arguments @('remote','add','origin','https://github.com/14digital/KUMAIL.git')
        New-Item -ItemType File -Path '.git/mi-bootstrap-pending' -Force | Out-Null
    }
    $rootPath = (Get-Item -LiteralPath '.').FullName.TrimEnd([char[]]@('\','/'))
    $gitRoot = ("$(Invoke-Git -Arguments @('rev-parse','--show-toplevel') -Capture)").Trim().Replace('/',[IO.Path]::DirectorySeparatorChar).TrimEnd([char[]]@('\','/'))
    if (-not $rootPath.Equals($gitRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'This folder belongs to another Git checkout. Update stopped.' }
    $origin = ("$(Invoke-Git -Arguments @('remote','get-url','origin') -Capture)").Trim()
    if ($origin -notin @('https://github.com/14digital/KUMAIL.git','https://github.com/14digital/KUMAIL','git@github.com:14digital/KUMAIL.git')) {
        throw 'The Git origin is not 14digital/KUMAIL. No remote configuration was changed.'
    }
    Write-Host 'Connecting to GitHub. If a browser sign-in opens, sign in to the account that can access 14digital/KUMAIL.'
    Invoke-Git -Arguments @('fetch','origin','+refs/heads/main:refs/remotes/origin/main')
    $target = ("$(Invoke-Git -Arguments @('rev-parse','refs/remotes/origin/main') -Capture)").Trim()
    Assert-SafeTree -Tree (Get-Tree -Commit $target)
    if (Test-Path '.git/mi-bootstrap-pending') {
        Write-Host 'Connecting this ZIP installation to its matching Git release. Existing .env and Docker data stay in place.'
        $before = Initialize-ZipCheckout -Target $target
    } else {
        $branch = ("$(Invoke-Git -Arguments @('branch','--show-current') -Capture)").Trim()
        if ($branch -ne 'main') { throw 'Switch to a clean main branch before updating. No branch was reset.' }
        $before = ("$(Invoke-Git -Arguments @('rev-parse','HEAD') -Capture)").Trim()
    }
    Complete-Update -Before $before -Target $target
}

if (-not $LibraryOnly) {
    try { Invoke-Update -Root $RootDirectory }
    catch { Write-Host ("UPDATE STOPPED: " + $_.Exception.Message) -ForegroundColor Red; exit 1 }
}
