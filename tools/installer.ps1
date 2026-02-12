$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$TaskName = "JarvisAutomationDaemon"
$Command = "$Python -m daemon.cli run-loop"

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command `"Set-Location '$Root'; `$env:PYTHONPATH='$Root'; $Command`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

$Rollback = @"
`$ErrorActionPreference = 'SilentlyContinue'
Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false
Write-Output 'Rollback complete.'
"@
Set-Content -Path (Join-Path $Root "tools\rollback.ps1") -Value $Rollback -Encoding UTF8

Write-Output "Installed scheduled task $TaskName"
Write-Output "Rollback script created at tools\rollback.ps1"
