$ErrorActionPreference = "Stop"

$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "OBS YouTube Thumbnailer Watcher.lnk"

if (Test-Path $ShortcutPath) {
  Remove-Item -LiteralPath $ShortcutPath
  Write-Host "Baslangic kisayolu kaldirildi:"
  Write-Host $ShortcutPath
} else {
  Write-Host "Baslangic kisayolu bulunamadi:"
  Write-Host $ShortcutPath
}
