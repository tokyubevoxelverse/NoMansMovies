$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

py -m pip install --upgrade pip
py -m pip install -r requirements.txt

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
py -m PyInstaller --noconfirm build.spec

if (Test-Path "dist\NoMansMovies.exe") {
    Write-Host "Built: dist\NoMansMovies.exe" -ForegroundColor Green
} else {
    Write-Host "Build failed" -ForegroundColor Red
    exit 1
}
