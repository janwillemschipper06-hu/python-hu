# Opdracht 2.5 – PowerShell

Antwoorden op de weekopdracht. Alle commando's zijn getest in PowerShell op Windows 11.

---

## Deel 1 – PowerShell Oneliners

### 1. Noem 4 Linux/Unix commando's die ook werken onder PowerShell

`ls`, `cat`, `pwd` en `cp`. Dit zijn in PowerShell aliassen van cmdlets:

| Unix-commando | PowerShell cmdlet |
|---|---|
| `ls` | `Get-ChildItem` |
| `cat` | `Get-Content` |
| `pwd` | `Get-Location` |
| `cp` | `Copy-Item` |

Andere voorbeelden die ook werken: `mv`, `rm`, `man`, `echo`, `cd`, `clear`, `sort`.

### 2. Welk commando kan je ook gebruiken in plaats van "cd"?

`Set-Location` (het echte cmdlet). De aliassen `sl` en `chdir` werken ook.

```powershell
Set-Location C:\Windows
```

### 3. Welk commando kan je ook gebruiken in plaats van "dir"?

`Get-ChildItem`. De aliassen `ls` en `gci` verwijzen naar hetzelfde cmdlet.

```powershell
Get-ChildItem C:\Windows
```

### 4. "cls" is een alias van?

`Clear-Host`. Te controleren met:

```powershell
Get-Alias cls
# Alias  cls -> Clear-Host
```

### 5. Maak een alias aan met de naam "hier" dat verwijst naar "get-location"

```powershell
New-Alias -Name hier -Value Get-Location
```

Daarna geeft `hier` de huidige map terug.

### 6. "Werkt" de alias nog als je het window met PowerShell afsluit en weer opnieuw opstart?

**Nee.** Een alias die je met `New-Alias` of `Set-Alias` maakt bestaat alleen in de huidige sessie. Zodra je het venster sluit is hij weg.

Om hem permanent te maken zet je de regel in je PowerShell-profiel:

```powershell
Add-Content -Path $PROFILE -Value 'New-Alias -Name hier -Value Get-Location'
```

Het profiel (`$PROFILE`) wordt bij elke nieuwe sessie uitgevoerd, dus dan is de alias er altijd.

### 7. Geef het commando waarmee je voorbeelden kan opvragen van het gebruik van "stop-process"

```powershell
Get-Help Stop-Process -Examples
```

### 8. Met welk commando kan je alle help updaten tot de meest recente versie?

```powershell
Update-Help
```

Dit moet als administrator (eventueel met `-Force` om de 24-uursbeperking te omzeilen).

### 9. Met welk commando krijg je online hulp bij het commando "stop-computer"?

```powershell
Get-Help Stop-Computer -Online
```

Dit opent de Microsoft Learn-documentatiepagina in je browser.

### 10. Wat gebeurt er als je een verplichte optie niet opgeeft? Bijvoorbeeld bij "stop-process"?

PowerShell stopt niet met een foutmelding, maar **vraagt interactief om de ontbrekende parameter**. Bij `Stop-Process` zonder parameters krijg je:

```
cmdlet Stop-Process at command pipeline position 1
Supply values for the following parameters:
Id[0]:
```

Je typt dan de waarde in (of drukt op Enter bij een array-parameter om te stoppen met invoeren). Druk je Ctrl+C, dan wordt het commando afgebroken.

### 11. Laat alle processen zien met ps en geef deze weer in 4 kolommen

```powershell
ps | Format-Wide -Column 4
```

### 12. Laat alle processen zien met ps en geef deze weer als een lijst (label-waarde)

```powershell
ps | Format-List
```

### 13. Gebruik test-connection om een computer 4x te pingen met steeds 4 seconden tussenpauze

```powershell
Test-Connection -TargetName www.hu.nl -Count 4 -Delay 4
```

In Windows PowerShell 5.1 heet de parameter `-ComputerName`:

```powershell
Test-Connection -ComputerName www.hu.nl -Count 4 -Delay 4
```

### 14. Maak een lijstje met drie computernamen, sla op als "hosts.txt" en ping deze met test-connection EN get-content

Het bestand aanmaken:

```powershell
"www.hu.nl", "www.google.com", "8.8.8.8" | Set-Content hosts.txt
```

Alle hosts achtereenvolgens pingen:

```powershell
Get-Content hosts.txt | ForEach-Object { Test-Connection -TargetName $_ -Count 2 }
```

Korter kan ook, omdat `-TargetName` een array accepteert:

```powershell
Test-Connection -TargetName (Get-Content hosts.txt) -Count 2
```

### 15. Gebruik de pipeline om de nieuwste 10 errors in de eventlog van het systeem te bekijken

```powershell
Get-WinEvent -LogName System | Where-Object { $_.LevelDisplayName -eq 'Error' } | Select-Object -First 10
```

Sneller is filteren aan de bron met een filter-hashtable:

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Level=2} -MaxEvents 10
```

De klassieke variant (verouderd, alleen Windows PowerShell):

```powershell
Get-EventLog -LogName System -EntryType Error -Newest 10
```

### 16. Gebruik "ps" en converteer de output naar html

```powershell
ps | ConvertTo-Html | Out-File processen.html
Invoke-Item processen.html
```

### 17. Gebruik "ps" en converteer de output naar csv en sla deze op als file

```powershell
ps | Export-Csv -Path processen.csv -NoTypeInformation
```

Of met `ConvertTo-Csv` en een redirect:

```powershell
ps | ConvertTo-Csv -NoTypeInformation | Out-File processen.csv
```

### 18. Gebruik "ps" en selecteer verschillende kolommen waaronder TotalProcessorTime

```powershell
ps | Select-Object Name, Id, CPU, TotalProcessorTime, WorkingSet64
```

### 19. Gebruik "ps" en sorteer op TotalProcessorTime (aflopend). Welk proces gebruikt de meeste processortijd?

```powershell
ps | Sort-Object TotalProcessorTime -Descending | Select-Object -First 10 Name, Id, TotalProcessorTime
```

**Resultaat op mijn machine:** `OUTLOOK` gebruikte de meeste processortijd (00:06:48), gevolgd door `msedge` (00:03:24) en `explorer` (00:02:34). Dit is natuurlijk afhankelijk van wat er op dat moment draait en hoe lang de machine aan staat.

### 20. Idem nu voor het gebruik van virtueel geheugen

```powershell
ps | Sort-Object VirtualMemorySize64 -Descending | Select-Object -First 10 Name, Id, VirtualMemorySize64
```

Leesbaarder in MB:

```powershell
ps | Sort-Object VirtualMemorySize64 -Descending |
    Select-Object -First 10 Name, Id, @{Name='VM(MB)'; Expression={[math]::Round($_.VirtualMemorySize64/1MB)}}
```

**Resultaat op mijn machine:** `msedge` gebruikt het meeste virtuele geheugen. Browsers reserveren veel virtuele adresruimte per tabblad-proces, dus dat verklaart de hoge waarden.

### 21. Vraag een lijst met services op en groepeer op status. Hoeveel services zijn "running" en hoeveel "stopped"?

```powershell
Get-Service | Group-Object Status | Select-Object Name, Count
```

**Resultaat op mijn machine:**

| Status | Aantal |
|---|---|
| Running | 185 |
| Stopped | 180 |

### 22. Gebruik measure-object om het aantal entries in de c:\windows directory op te vragen

```powershell
Get-ChildItem C:\Windows | Measure-Object
```

Alleen het getal:

```powershell
(Get-ChildItem C:\Windows | Measure-Object).Count
```

**Resultaat op mijn machine:** 113 entries (bestanden + mappen in de root van `C:\Windows`).

### 23. Start "notepad" een paar keer. Gebruik nu ps met "where" en "like" om alle processen op te vragen die beginnen met een "n"

```powershell
notepad; notepad; notepad
ps | Where-Object { $_.Name -like "n*" }
```

### 24. Start notepad. Gebruik get-process en stop-process in een enkele pipeline om notepad te stoppen

```powershell
notepad
Get-Process notepad | Stop-Process
```

---

## Deel 2 – PowerShell Script

### 1. Zorg ervoor dat je executionpolicy zodanig is aangepast dat je scripts kunt starten

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Controleren:

```powershell
Get-ExecutionPolicy
```

`RemoteSigned` is de nette keuze: eigen lokale scripts mogen draaien, gedownloade scripts moeten gesigneerd zijn. Met `-Scope CurrentUser` heb je geen administrator-rechten nodig.

### 2. Script "np.ps1": start 3x notepad, slaapt 3 seconden, vraagt de proces-id's op en stopt alle notepads

Zie [`np.ps1`](np.ps1):

```powershell
# np.ps1 - start 3x notepad, wacht, toont de process-id's en stopt ze weer
1..3 | ForEach-Object { Start-Process notepad }

Start-Sleep -Seconds 3

Write-Host "Process-id's van notepad:"
Get-Process notepad | Select-Object Id, ProcessName, StartTime | Format-Table -AutoSize

Get-Process notepad | Stop-Process
Write-Host "Alle notepad-processen zijn gestopt."
```

Uitvoeren:

```powershell
.\np.ps1
```

---

## Deel 3 – PowerShell vanaf verschillende plaatsen

### 5. Script: zoek bestanden groter dan een door de gebruiker opgegeven grootte

Zie [`grote-bestanden.ps1`](grote-bestanden.ps1):

```powershell
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
```

Belangrijke keuzes in dit script:

- `-ErrorAction SilentlyContinue` onderdrukt "access denied" op mappen waar je geen rechten hebt, zodat het zoeken niet afbreekt.
- `$HOME` werkt zowel onder Windows als onder Linux, dus hetzelfde script is cross-platform te gebruiken.
- `1MB` is een PowerShell-constante, daarom hoef je niet zelf met 1048576 te rekenen.
- Een berekende kolom (`@{Name=...; Expression=...}`) maakt de output leesbaar in MB in plaats van bytes.

### 6. Run dit script vanuit Visual Studio Code (Windows)

Open `grote-bestanden.ps1` in VS Code (met de PowerShell-extensie) en druk op **F5**, of typ in de geïntegreerde terminal:

```powershell
.\grote-bestanden.ps1
```

*(Screenshot van de uitvoer in de VS Code-terminal toevoegen.)*

### 7. Run dit commando vanaf een linux command prompt (pwsh onder linux)

PowerShell installeren en starten op Ubuntu:

```bash
sudo snap install powershell --classic
pwsh
```

En dan in `pwsh`:

```powershell
./grote-bestanden.ps1
```

Het script werkt ongewijzigd, omdat `$HOME`, `Get-ChildItem` en `Format-Table` ook onder Linux bestaan. Alleen de padnotatie verschilt (`/home/gebruiker` in plaats van `C:\Users\gebruiker`).

*(Screenshot van de uitvoer onder Linux toevoegen.)*

### 8. Run dit commando vanaf de cloudshell op een vm vanaf portal.azure.com

Open de Cloud Shell in portal.azure.com en kies **PowerShell** als shell. Upload het script met de knop *Upload/Download files*, of maak het aan met `code grote-bestanden.ps1`. Dan:

```powershell
./grote-bestanden.ps1
```

In Cloud Shell is je home directory `/home/<gebruiker>` en die wordt bewaard in een Azure File Share (`clouddrive`), dus je script blijft beschikbaar in een volgende sessie.

*(Screenshot van de uitvoer in Azure Cloud Shell toevoegen.)*

---

## Deel 4 – PowerShell in een Windows domein

Uitgangspunt: een domein (bijvoorbeeld `lab.local`) met minimaal twee Windows-machines, en PowerShell Remoting ingeschakeld op de remote machine:

```powershell
Enable-PSRemoting -Force
```

Binnen een domein gaat de authenticatie automatisch via Kerberos, dus je hoeft geen credentials mee te geven zolang je als domeinadministrator ingelogd bent.

### 1. Log als administrator in vanaf de ene computer op de andere (Enter-PSSession) en vraag een proceslijst op

```powershell
Enter-PSSession -ComputerName SRV02
[SRV02]: PS C:\> Get-Process
[SRV02]: PS C:\> Exit-PSSession
```

De prompt verandert in `[SRV02]: PS C:\>`: je zit nu in een interactieve sessie op de remote computer, dus `Get-Process` geeft de processen van SRV02.

### 2. Log weer uit en gebruik daarna "Invoke-Command" om de proceslijst van die tweede computer in één keer op te halen

```powershell
Exit-PSSession
Invoke-Command -ComputerName SRV02 -ScriptBlock { Get-Process }
```

Verschil met `Enter-PSSession`: `Invoke-Command` is niet interactief. Het script-block wordt remote uitgevoerd en alleen het resultaat komt terug (gedeserialiseerde objecten, met een extra kolom `PSComputerName`).

### 3. Vraag per computer de 5 processen op die het meeste memory gebruiken en sorteer de totaallijst op memoryverbruik

```powershell
$computers = 'SRV01', 'SRV02'

Invoke-Command -ComputerName $computers -ScriptBlock {
    Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5
} |
    Sort-Object WorkingSet64 -Descending |
    Select-Object @{Name='Computer'; Expression={$_.PSComputerName}},
                  @{Name='Proces'; Expression={$_.Name}},
                  Id,
                  @{Name='Memory (MB)'; Expression={[math]::Round($_.WorkingSet64 / 1MB, 2)}} |
    Format-Table -AutoSize
```

Hoe dit werkt:

1. `Invoke-Command` met meerdere computernamen draait het script-block **parallel** op elke machine.
2. Op elke machine worden eerst lokaal de top 5 processen op `WorkingSet64` (fysiek geheugen) geselecteerd — dat beperkt het dataverkeer over het netwerk.
3. Lokaal worden de resultaten van alle machines samengevoegd en opnieuw gesorteerd, zodat je één totaallijst krijgt.
4. `PSComputerName` wordt automatisch door remoting toegevoegd, dus je ziet per regel van welke machine het proces komt.

Voorbeeld van de uitvoer:

```
Computer Proces     Id Memory (MB)
-------- ------     -- -----------
SRV01    sqlservr 1234     2048.50
SRV02    msedge   4321      845.12
SRV01    explorer 2468      210.75
```

*(Screenshots van de commando's en de bijbehorende uitvoer toevoegen.)*
