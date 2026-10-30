$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Install Docker Desktop for Windows, start it, then run this launcher again.'
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait until it is ready, then try again.' }
if (-not (Test-Path '.env')) {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $token = [Convert]::ToBase64String($bytes)
    $template = Get-Content '.env.example' -Raw
    $config = $template -replace '(?m)^APP_TOKEN=.*$', ('APP_TOKEN=' + $token)
    [System.IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $config)
}
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Docker startup failed. Check the error above.' }
Write-Host 'Waiting for the dashboard...'
$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $response = Invoke-WebRequest 'http://localhost:3000' -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'The dashboard did not become ready. Run docker compose logs to investigate.' }
Write-Host 'Copy the APP_TOKEN value from the file opening in Notepad into the dashboard access-key field. Keep this file private.'
Start-Process notepad.exe -ArgumentList '.env'
Start-Process 'http://localhost:3000'
