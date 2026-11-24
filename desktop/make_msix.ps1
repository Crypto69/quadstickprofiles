# The Microsoft Store package (.msix) from the Windows build desktop\build.ps1 made.
# From the repo root, in PowerShell, after build.ps1:
#   powershell -ExecutionPolicy Bypass -File desktop\make_msix.ps1 -Version 1.16
#   -> desktop\dist\QuadStickProfileStudio-1.16.0.0-store.msix
# With -Test it makes a package under a made-up identity instead, for checking the
# packaging before the Partner Center values are in store-identity.json; such a
# package can never be uploaded, and its name says so.
#
# The package is not signed: Partner Center signs it when it is submitted. Needs
# the Windows 10/11 SDK (makeappx.exe, makepri.exe), which GitHub's windows-latest
# runner has.
param(
  [Parameter(Mandatory = $true)][string]$Version,
  [string]$AppDir = "desktop\dist\QuadStick Profile Studio",
  [switch]$Test
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$pack = "packaging\windows"

# ---- identity: Partner Center's values, or a test one
$id = Get-Content "$pack\store-identity.json" -Raw | ConvertFrom-Json
$placeholder = ($id.identity_name + $id.publisher + $id.publisher_display_name) -match "REPLACE_WITH"
if ($Test) {
  $id = [pscustomobject]@{
    identity_name = "QuadStickProfileStudio.LocalTest"
    publisher = "CN=QuadStickProfileStudioTest"
    publisher_display_name = "Local test build"
  }
  $kind = "TEST-not-for-upload"
} elseif ($placeholder) {
  throw "packaging\windows\store-identity.json still has placeholders. Paste the three values from Partner Center > Product identity, or pass -Test."
} else {
  $kind = "store"
}

# ---- version: the app's 1.16 or 1.16.3 becomes 1.16.0.0 or 1.16.3.0. The Store wants
# four numbers, each 0-65535, the last one 0, and every upload higher than the one before.
$parts = @($Version.Split("."))
if ($parts.Count -lt 2 -or $parts.Count -gt 3) { throw "Version '$Version' is not like 1.16 or 1.16.3" }
while ($parts.Count -lt 3) { $parts += "0" }
foreach ($p in $parts) {
  if ($p -notmatch '^\d+$' -or [int]$p -gt 65535) { throw "Version '$Version' has a part that is not a number from 0 to 65535" }
}
$msixVersion = ($parts + "0") -join "."

if (-not (Test-Path "$AppDir\QuadStick Profile Studio.exe")) { throw "No build at $AppDir. Run desktop\build.ps1 first." }

# ---- the Windows SDK tools, newest first
function Find-SdkTool([string]$name) {
  $tool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter $name -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\x64\\' } | Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $tool) { throw "$name not found. Install the Windows 10/11 SDK." }
  return $tool.FullName
}
$makeappx = Find-SdkTool "makeappx.exe"
$makepri = Find-SdkTool "makepri.exe"

# ---- lay out the package: manifest and logos at the top, the app in its own folder
$stage = "desktop\build\msix"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item $AppDir "$stage\QuadStick Profile Studio" -Recurse
Copy-Item "$pack\Images" "$stage\Images" -Recurse
$manifest = (Get-Content "$pack\AppxManifest.xml" -Raw).
  Replace("@IDENTITY_NAME@", $id.identity_name).
  Replace("@PUBLISHER@", [Security.SecurityElement]::Escape($id.publisher)).
  Replace("@PUBLISHER_DISPLAY_NAME@", [Security.SecurityElement]::Escape($id.publisher_display_name)).
  Replace("@VERSION@", $msixVersion)
if ($manifest -match "@[A-Z_]+@") { throw "AppxManifest.xml still has a value nobody filled in: $($Matches[0])" }
[IO.File]::WriteAllText((Join-Path (Resolve-Path $stage) "AppxManifest.xml"), $manifest, (New-Object Text.UTF8Encoding $false))

# ---- resources.pri, so Windows picks the right logo size for each place it shows
# one. Indexed from a copy holding only the manifest and the logos: the app folder
# has thousands of files and none of them are resources.
$priRoot = "desktop\build\msix-pri"
if (Test-Path $priRoot) { Remove-Item $priRoot -Recurse -Force }
New-Item -ItemType Directory -Force $priRoot | Out-Null
Copy-Item "$stage\AppxManifest.xml" $priRoot
Copy-Item "$stage\Images" "$priRoot\Images" -Recurse
& $makepri createconfig /cf "$priRoot\..\priconfig.xml" /dq en-US /o | Out-Null
if ($LASTEXITCODE) { throw "makepri createconfig failed" }
& $makepri new /pr $priRoot /cf "$priRoot\..\priconfig.xml" /mn "$priRoot\AppxManifest.xml" /of "$stage\resources.pri" /o
if ($LASTEXITCODE) { throw "makepri new failed" }

# ---- pack
New-Item -ItemType Directory -Force "desktop\dist" | Out-Null
$out = "desktop\dist\QuadStickProfileStudio-$msixVersion-$kind.msix"
& $makeappx pack /d $stage /p $out /o
if ($LASTEXITCODE) { throw "makeappx pack failed" }
Write-Host "built $out ($($id.identity_name), $($id.publisher), version $msixVersion)"
"$out" | Set-Content -NoNewline -Encoding ascii "desktop\dist\msix-path.txt"
