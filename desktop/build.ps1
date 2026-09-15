# Windows desktop build. From the repo root, in PowerShell:
#   powershell -ExecutionPolicy Bypass -File desktop\build.ps1
#   -> desktop\dist\QuadStickProfileStudio-<ver>-windows-x64.zip
# Needs: node 22, python 3.12 with `pip install -e core -e api -r desktop\requirements.txt`,
# and Git for Windows (for the version stamp; `sh` comes with it).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# scripts/version.sh is POSIX sh; Git for Windows ships sh.exe.
$lines = & sh scripts/version.sh
foreach ($line in $lines) {
  $k, $v = $line -split "=", 2
  Set-Item -Path "Env:$k" -Value $v
}
Write-Host "building $env:APP_VERSION ($env:GIT_SHA, $env:BUILD_TIME)"

Push-Location web
npm ci --no-audit --no-fund
if ($LASTEXITCODE) { throw "npm ci failed" }
npm run build
if ($LASTEXITCODE) { throw "npm run build failed" }
Pop-Location

"APP_VERSION=$env:APP_VERSION`nGIT_SHA=$env:GIT_SHA`nBUILD_TIME=$env:BUILD_TIME`n" |
  Set-Content -NoNewline -Encoding ascii desktop\version.txt

python -m PyInstaller --noconfirm --clean desktop\quadstick.spec `
  --distpath desktop\dist --workpath desktop\build
if ($LASTEXITCODE) { throw "PyInstaller failed" }

$out = "desktop\dist\QuadStickProfileStudio-$env:APP_VERSION-windows-x64.zip"
if (Test-Path $out) { Remove-Item $out }
Compress-Archive -Path "desktop\dist\QuadStick Profile Studio" -DestinationPath $out
Write-Host "built $out"
