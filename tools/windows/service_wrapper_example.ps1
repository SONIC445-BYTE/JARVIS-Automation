# Example wrapper for NSSM/sc.exe style hosting.
# Not executed by default; use with your preferred service manager.

$Root = "C:\path\to\J.A.R.V.I.S.1.0"
$Python = "python"
$Cmd = "$Python -m daemon.cli run-loop"

Write-Output "Example command:"
Write-Output "powershell -NoProfile -WindowStyle Hidden -Command `"Set-Location '$Root'; `$env:PYTHONPATH='$Root'; $Cmd`""
