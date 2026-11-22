$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Ensure isolated test environment is initialized
$TestEnvRoot = Join-Path $RepoRoot ".test_desktop_env"
$RuntimeHome = Join-Path $TestEnvRoot "runtime"
$LibraryDir  = Join-Path $TestEnvRoot "Library"

if (-not (Test-Path "$LibraryDir\library.sqlite3")) {
    Write-Host "Initializing isolated test environment..." -ForegroundColor Cyan
    & "$RepoRoot\.venv_stabilization\Scripts\python.exe" "$RepoRoot\scripts\setup_test_desktop_env.py"
}

# 2. Sync staged source to ensure app-runtime has latest code
node "$RepoRoot\scratch\sync_runtime.js"

# 3. Set isolated environment variables and clear ELECTRON_RUN_AS_NODE
Remove-Item env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
$env:ELECTRON_RUN_AS_NODE = $null
$env:NODE_PATH = "$RepoRoot\desktop\node_modules"
$env:RESEARCHLENS_RUNTIME_HOME = $RuntimeHome

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " RESEARCHLENS ISOLATED DESKTOP ACCEPTANCE TEST LAUNCHER   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Runtime Home: $RuntimeHome" -ForegroundColor Yellow
Write-Host " Test Library: $LibraryDir" -ForegroundColor Yellow
Write-Host " Production:   UNTOUCHED ($env:USERPROFILE\Documents\ResearchLens Library)" -ForegroundColor Green
Write-Host " Login User:   testuser" -ForegroundColor Cyan
Write-Host " Password:     TestPassword123!" -ForegroundColor Cyan
Write-Host " Sample Files: $TestEnvRoot\sample_uploads" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Starting ResearchLens Desktop Application..." -ForegroundColor White

& "$RepoRoot\desktop\node_modules\.bin\electron.cmd" "$RepoRoot\desktop\main.cjs"
