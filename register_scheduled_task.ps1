# Registers a Windows Scheduled Task that starts scheduler.py (the IST-aware
# continuous scheduler) at user logon, running hidden via pythonw.exe.
# scheduler.py itself decides when to actually run the job (daily 08:00
# Asia/Kolkata, with catch-up if the PC was off), so this task only needs
# to ensure the process is alive.
#
# Run this script once, in an elevated or normal PowerShell session:
#   powershell -ExecutionPolicy Bypass -File register_scheduled_task.ps1

$ErrorActionPreference = "Stop"

$pythonw = "C:\Users\Manas\AppData\Local\Python\bin\pythonw.exe"
$projectDir = $PSScriptRoot
$schedulerScript = Join-Path $projectDir "scheduler.py"
$taskName = "SOC_Job_Agent_Scheduler"

if (-not (Test-Path $pythonw)) {
    throw "pythonw.exe not found at $pythonw -- update the path in this script."
}
if (-not (Test-Path $schedulerScript)) {
    throw "scheduler.py not found at $schedulerScript"
}

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$schedulerScript`"" -WorkingDirectory $projectDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Runs the SOC Analyst fresher job digest scheduler (daily 08:00 IST email)." -Force

Write-Host "Registered scheduled task '$taskName'. It starts scheduler.py at logon."
Write-Host "Starting it now for the current session..."
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2
Get-ScheduledTaskInfo -TaskName $taskName | Format-List
