$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker Desktop is required.' }
$source = Get-Content 'scripts/import_publishers.py' -Raw -Encoding UTF8
$rows = Get-Content 'config/publisher-feeds.json' -Raw -Encoding UTF8
# Base64 is transport encoding, not an executable downloaded command or a secret.
$code64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($source))
$data64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($rows))
$payload = "import base64,json; exec(compile(base64.b64decode('$code64'), 'import_publishers.py', 'exec')); raise SystemExit(main(json.loads(base64.b64decode('$data64'))))"
$env:PYTHONIOENCODING = 'utf-8'
Write-Host 'Checking 33 publisher feeds from your computer. This can take several minutes.'
$output = $payload | docker compose exec -T -e PYTHONIOENCODING=utf-8 api python -
$result = $LASTEXITCODE
$output | ForEach-Object { if (-not $_.StartsWith('IMPORT_REPORT_JSON=')) { Write-Host $_ } }
$report = $output | Where-Object { $_.StartsWith('IMPORT_REPORT_JSON=') } | Select-Object -Last 1
if ($report) {
    [IO.File]::WriteAllText((Join-Path (Get-Location) 'publisher-import-results.json'), $report.Substring('IMPORT_REPORT_JSON='.Length))
    Write-Host 'Details saved to publisher-import-results.json. Refresh Sources in the app.'
}
if ($result -eq 2) { Write-Host 'Some feeds need review; working feeds were imported.' }
elseif ($result -ne 0) { throw 'Import could not complete. Make sure the application containers are running.' }
