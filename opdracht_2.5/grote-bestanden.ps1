# grote-bestanden.ps1 - toont de 10 grootste bestanden boven een opgegeven grootte
param(
    [string]$Pad = $HOME
)

$grootteMB = Read-Host "Geef een minimale grootte in MB"
$grensBytes = [double]$grootteMB * 1MB

Write-Host "`nZoeken in $Pad naar bestanden groter dan $grootteMB MB...`n"

$bestanden = Get-ChildItem -Path $Pad -File -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -gt $grensBytes } |
    Sort-Object Length -Descending |
    Select-Object -First 10

if (-not $bestanden) {
    Write-Host "Geen bestanden gevonden groter dan $grootteMB MB."
    return
}

$bestanden |
    Select-Object @{Name='Bestand'; Expression={$_.Name}},
                  @{Name='Grootte (MB)'; Expression={[math]::Round($_.Length / 1MB, 2)}},
                  @{Name='Gewijzigd'; Expression={$_.LastWriteTime.ToString('yyyy-MM-dd HH:mm')}},
                  @{Name='Map'; Expression={$_.DirectoryName}} |
    Format-Table -AutoSize
