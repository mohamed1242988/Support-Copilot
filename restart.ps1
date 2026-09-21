C:\nssm\nssm.exe stop SupportCopilot
Start-Sleep -Seconds 2
$busy = netstat -ano | findstr LISTENING | findstr :8000
if ($busy) { Write-Host "Port 8000 still in use:"; Write-Host $busy; exit 1 }
C:\nssm\nssm.exe start SupportCopilot
C:\nssm\nssm.exe status SupportCopilot