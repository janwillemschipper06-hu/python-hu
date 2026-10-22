# np.ps1 - start 3x notepad, wacht, toont de process-id's en stopt ze weer
1..3 | ForEach-Object { Start-Process notepad }

Start-Sleep -Seconds 3

Write-Host "Process-id's van notepad:"
Get-Process notepad | Select-Object Id, ProcessName, StartTime | Format-Table -AutoSize

Get-Process notepad | Stop-Process
Write-Host "Alle notepad-processen zijn gestopt."
