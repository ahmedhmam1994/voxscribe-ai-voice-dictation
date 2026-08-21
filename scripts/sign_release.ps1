# Signs the packaged VoxScribe.exe and the Inno Setup installer with a real
# code-signing certificate, removing the Windows SmartScreen "unknown
# publisher" warning. Requires a certificate this script cannot obtain for
# you -- see README.md's "Code signing" section for how to get one
# (a paid OV/EV cert from a CA, or Microsoft Trusted Signing via Azure).
#
# Usage (after both `pyinstaller` and `ISCC.exe` have already produced
# dist\VoxScribe\VoxScribe.exe and installer_output\VoxScribe-Setup.exe):
#
#   $env:VOXSCRIBE_CERT_PATH = "C:\path\to\cert.pfx"
#   $env:VOXSCRIBE_CERT_PASSWORD = "..."
#   .\scripts\sign_release.ps1
#
# For Microsoft Trusted Signing (no local .pfx file) use `signtool sign
# /fd SHA256 /tr ... /td SHA256 /dlib ... /dmdf ...` per Microsoft's Trusted
# Signing docs instead -- swap the signtool invocation below for that form.

$ErrorActionPreference = "Stop"

$certPath = $env:VOXSCRIBE_CERT_PATH
$certPassword = $env:VOXSCRIBE_CERT_PASSWORD

if (-not $certPath -or -not (Test-Path $certPath)) {
    Write-Host "VOXSCRIBE_CERT_PATH is not set or the file doesn't exist -- nothing to sign with."
    Write-Host "See README.md's Code signing section to get a certificate first."
    exit 1
}

$signtool = Get-ChildItem -Path "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -like "*x64*" } |
    Select-Object -First 1 -ExpandProperty FullName

if (-not $signtool) {
    Write-Host "signtool.exe not found -- install the Windows SDK (or Visual Studio's SDK component)."
    exit 1
}

$targets = @(
    "dist\VoxScribe\VoxScribe.exe",
    "installer_output\VoxScribe-Setup.exe"
) | Where-Object { Test-Path $_ }

if ($targets.Count -eq 0) {
    Write-Host "Nothing to sign -- build VoxScribe.exe and/or the installer first."
    exit 1
}

foreach ($target in $targets) {
    Write-Host "Signing $target..."
    & $signtool sign /f $certPath /p $certPassword /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $target
    if ($LASTEXITCODE -ne 0) {
        throw "signtool failed on $target"
    }
    & $signtool verify /pa $target
}

Write-Host "Done. Signed: $($targets -join ', ')"
