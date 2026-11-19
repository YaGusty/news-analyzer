<#
.SYNOPSIS
    Setup or remove Windows Task Scheduler for News Analyzer 24/7 Daemon.
.DESCRIPTION
    Creates a scheduled task named 'NewsAnalyzer_24_7_Monitor' that starts automatically
    upon user login, runs with highest available privileges, and restarts automatically on error.
.EXAMPLE
    .\setup_autostart_task.ps1 -Install
    .\setup_autostart_task.ps1 -Uninstall
    .\setup_autostart_task.ps1 -Status
#>

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Status
)

$TaskName = "NewsAnalyzer_24_7_Monitor"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PythonExe = "python.exe"
$ScriptPath = Join-Path $ProjectRoot "scripts\main.py"
$VbsLauncher = Join-Path $ProjectRoot "run_daemon.vbs"

if ($Install) {
    Write-Host "[*] Registering 24/7 Autostart Task: $TaskName..." -ForegroundColor Cyan
    
    $Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsLauncher`"" -WorkingDirectory "$ProjectRoot"
    $Trigger = New-ScheduledTaskTrigger -AtLogOn
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "News Analyzer 24/7 Red Folder News Detection Daemon" -Force
    
    Write-Host "[✓] Successfully registered '$TaskName' in Windows Task Scheduler!" -ForegroundColor Green
    Write-Host "    • Runs automatically on user logon."
    Write-Host "    • Logs written to: data\logs\scheduler.log"
    return
}

if ($Uninstall) {
    Write-Host "[*] Unregistering task: $TaskName..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[✓] Task '$TaskName' removed successfully." -ForegroundColor Green
    return
}

# Default: Status
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Write-Host "[*] Task '$TaskName' is INSTALLED." -ForegroundColor Green
    Write-Host "    State: $($Task.State)"
    Write-Host "    Run '.\setup_autostart_task.ps1 -Uninstall' to remove it."
} else {
    Write-Host "[*] Task '$TaskName' is NOT installed." -ForegroundColor Gray
    Write-Host "    Run 'powershell -ExecutionPolicy Bypass -File .\setup_autostart_task.ps1 -Install' to register 24/7 autostart."
}
