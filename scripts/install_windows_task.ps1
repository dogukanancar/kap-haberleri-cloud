# KAP + CDS + Brand worker'ini 10 dakikada bir calistirir (bu PC).
# GitHub public schedule 10 dk'yi tutmaz; asil zamanlama bu gorevdir.
#   .\scripts\install_windows_task.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Bat = Join-Path $Root "scripts\run_cloud_workers.bat"
$TaskName = "KapHaberleriCloudWorker"

if (-not (Test-Path $Bat)) {
    throw "Bulunamadi: $Bat"
}

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Bat`"" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Gorev kuruldu ve ilk tur baslatildi: $TaskName (her 10 dk)"
