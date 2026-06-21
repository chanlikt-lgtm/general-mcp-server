# Run this script ONCE as Administrator to register the MCP HTTP server as a startup task.
# Right-click PowerShell → "Run as administrator" → paste:
#   E:\claude\MCP\install_autostart.ps1

$action  = New-ScheduledTaskAction `
    -Execute "C:\WINDOWS\py.exe" `
    -Argument "E:\claude\MCP\server_http.py" `
    -WorkingDirectory "E:\claude\MCP"

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable $true

Register-ScheduledTask `
    -TaskName   "MCP-HTTP-Server" `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -Description "General MCP HTTP server on port 8080 — auto-start at login" `
    -RunLevel   Highest `
    -Force

# ── Dashboard on port 8081 ────────────────────────────────────────────────────
$action2 = New-ScheduledTaskAction `
    -Execute "C:\WINDOWS\py.exe" `
    -Argument "-m uvicorn dashboard.app:app --host 0.0.0.0 --port 8081" `
    -WorkingDirectory "E:\claude\MCP"

Register-ScheduledTask `
    -TaskName   "MCP-Dashboard" `
    -Action     $action2 `
    -Trigger    $trigger `
    -Settings   $settings `
    -Description "MCP Dashboard UI on port 8081 — auto-start at login" `
    -RunLevel   Highest `
    -Force

Write-Host ""
Write-Host "✅ Both servers scheduled to start at every login." -ForegroundColor Green
Write-Host "   MCP HTTP  : http://localhost:8080  (task: MCP-HTTP-Server)"
Write-Host "   Dashboard : http://localhost:8081  (task: MCP-Dashboard)"
Write-Host "   To verify : schtasks /query /tn MCP-HTTP-Server"
Write-Host "   To remove : Unregister-ScheduledTask -TaskName MCP-HTTP-Server -Confirm:`$false"
