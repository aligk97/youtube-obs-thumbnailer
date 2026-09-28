$ErrorActionPreference = "Stop"

$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "OBS YouTube Thumbnailer Watcher.lnk"
$TargetPath = Join-Path $BaseDir "start_watcher_hidden.vbs"

if (!(Test-Path $TargetPath)) {
  throw "start_watcher_hidden.vbs bulunamadi: $TargetPath"
}

$WScript = New-Object -ComObject WScript.Shell
$Shortcut = $WScript.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $BaseDir
$Shortcut.WindowStyle = 7
$Shortcut.Description = "OBS acildiginda YouTube thumbnailer'i gizli baslatir."
$Shortcut.Save()

Write-Host "Baslangic kisayolu kuruldu:"
Write-Host $ShortcutPath
Write-Host ""
if (!(Test-Path (Join-Path $BaseDir "config.json"))) {
  Write-Warning "Bu klasorde config.json bulunamadi. Calisan config dosyanizi bu klasore koyun ya da installer'i programin asil klasorunde calistirin."
  Write-Host ""
}
Write-Host "Bundan sonra Windows oturum acilinca watcher gizli calisir."
Write-Host "OBS acildiginda thumbnailer baslar, OBS kapaninca durur."
